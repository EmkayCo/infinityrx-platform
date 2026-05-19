"""Integration test: two concurrent dispatchers cannot publish the same row.

R1 BLOCK 3 fix: proves the atomic claim semantics work end-to-end.
SQLite cannot model FOR UPDATE SKIP LOCKED behavior; this test is
gated on a real Postgres connection (RECLAIMRX_TEST_PG_URL env var).
"""
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.outbox.event_outbox import OutboxService
from src.outbox.outbox_dispatcher import OutboxDispatcher


pytestmark = pytest.mark.skipif(
    not os.environ.get("RECLAIMRX_TEST_PG_URL"),
    reason="Concurrent claim test requires Postgres (set RECLAIMRX_TEST_PG_URL)",
)


@pytest.mark.asyncio
async def test_two_dispatchers_each_claim_disjoint_rows():
    """Seed 10 pending rows; run 2 dispatchers concurrently.

    Postcondition: every row is published exactly once. The sets of rows
    published by dispatcher A and dispatcher B are disjoint and their
    union equals the seeded set.
    """
    pg_url = os.environ["RECLAIMRX_TEST_PG_URL"]
    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)

    tenant_id = uuid.uuid4()
    with Session() as session:
        svc = OutboxService(session)
        for i in range(10):
            svc.write(
                event_type=f"test.event_{i}",
                tenant_id=tenant_id,
                payload={"n": i},
                ordering_key=str(i),
                idempotency_key=f"test:{i}",
            )
        session.commit()

    published_a: list[str] = []
    published_b: list[str] = []

    class CollectingBus:
        def __init__(self, sink: list[str]):
            self._sink = sink

        async def publish(self, envelope):
            self._sink.append(envelope.idempotency_key)

    disp_a = OutboxDispatcher(
        session_factory=Session, bus=CollectingBus(published_a),
        batch_size=5, poll_interval_seconds=0.01,
    )
    disp_b = OutboxDispatcher(
        session_factory=Session, bus=CollectingBus(published_b),
        batch_size=5, poll_interval_seconds=0.01,
    )

    await asyncio.gather(disp_a._poll_once(), disp_b._poll_once())

    seen = set(published_a) | set(published_b)
    assert len(seen) == 10, f"expected 10 distinct rows, got {len(seen)}"
    assert set(published_a).isdisjoint(set(published_b)), (
        f"dispatchers published overlapping rows: A={published_a}, B={published_b}"
    )


@pytest.mark.asyncio
async def test_dispatcher_publishes_all_tenants():
    """R6 BLOCK-14: dispatcher is system-wide; rows from all tenants must be published.

    Seed 3 rows under tenant_a + 3 rows under tenant_b. One dispatcher
    poll publishes ALL 6 rows.
    """
    pg_url = os.environ["RECLAIMRX_TEST_PG_URL"]
    engine = create_engine(pg_url)
    Session = sessionmaker(bind=engine)

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    with Session() as session:
        svc = OutboxService(session)
        for tid in (tenant_a, tenant_b):
            for i in range(3):
                svc.write(
                    event_type="payment.hold_released",
                    tenant_id=tid,
                    payload={"hold_id": f"{tid}:{i}"},
                    ordering_key=f"{tid}:{i}",
                    idempotency_key=f"cross:{tid}:{i}",
                )
        session.commit()

    published_envelopes: list = []

    class CollectingBus:
        async def publish(self, envelope):
            published_envelopes.append(envelope)

    dispatcher = OutboxDispatcher(
        session_factory=Session, bus=CollectingBus(),
        batch_size=10, poll_interval_seconds=0.01,
    )
    await dispatcher._poll_once()

    tenant_ids_published = {env.tenant_id for env in published_envelopes}
    assert len(published_envelopes) == 6, (
        f"expected 6 rows published, got {len(published_envelopes)}"
    )
    assert tenant_ids_published == {tenant_a, tenant_b}, (
        f"expected both tenants represented, got {tenant_ids_published}"
    )
