"""Tests for the transactional outbox pattern.

Critical: verifies crash-safe event publishing behaviour.
Tests use SQLite in-memory for isolation (no real Postgres required).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.types import TypeDecorator

from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.outbox import (
    MAX_RELAY_ATTEMPTS,
    OutboxEntry,
    OutboxRelay,
    _OutboxBase,
    enqueue_event,
)
from shared.events.types import EventEnvelope


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return uuid.UUID(value) if value is not None else None

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _envelope(event_type: str = "claim.ingested", **kwargs) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=TENANT,
        correlation_id=CORR,
        source_module="billing",
        schema_version="1.0",
        ordering_key=str(uuid.uuid4()),
        idempotency_key=f"{event_type}:{uuid.uuid4()}",
        **kwargs,
    )


@pytest.fixture
async def engine():
    """SQLite in-memory async engine with outbox schema.

    SQLite does not support PostgreSQL schemas. We strip the schema from
    OutboxEntry's table_args for test purposes, and swap PG_UUID columns
    for _UUIDString per LESSON-007.
    """
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    # Strip the schema from OutboxEntry for SQLite compatibility
    OutboxEntry.__table__.schema = None  # type: ignore[attr-defined]
    # Swap PG_UUID columns for SQLite-compatible string UUIDs (LESSON-007)
    for col in OutboxEntry.__table__.columns:
        if isinstance(col.type, PG_UUID):
            col.type = _UUIDString()
    async with eng.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: _OutboxBase.metadata.create_all(sync_conn)
        )
    yield eng
    # Restore schema and types for production code
    OutboxEntry.__table__.schema = "shared_events"  # type: ignore[attr-defined]
    for col in OutboxEntry.__table__.columns:
        if isinstance(col.type, _UUIDString):
            col.type = PG_UUID(as_uuid=True)
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """AsyncSession bound to the test engine."""
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s


class TestEnqueueEvent:
    async def test_enqueue_writes_outbox_entry_in_same_transaction(self, session) -> None:
        """enqueue_event writes to outbox atomically with business data."""
        env = _envelope("payment_batch.submitted")
        async with session.begin():
            entry = await enqueue_event(session, env)

        assert entry.event_type == "payment_batch.submitted"
        assert entry.tenant_id == TENANT
        assert entry.idempotency_key == env.idempotency_key
        assert entry.published_at is None
        assert entry.attempts == 0

    async def test_enqueue_serializes_envelope_as_wire_json(self, session) -> None:
        """enqueue_event stores the to_wire() representation."""
        env = _envelope("claim.ingested", payload={"claim_id": "abc123"})
        async with session.begin():
            entry = await enqueue_event(session, env)

        wire = json.loads(entry.payload_json)
        assert wire["event_type"] == "claim.ingested"
        assert wire["payload"]["claim_id"] == "abc123"
        assert wire["tenant_id"] == str(TENANT)

    async def test_rollback_removes_outbox_entry(self, engine) -> None:
        """If the transaction rolls back, the outbox entry is also removed."""
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        env = _envelope("payment_batch.submitted")

        async with factory() as session:
            try:
                async with session.begin():
                    await enqueue_event(session, env)
                    raise RuntimeError("Simulated crash before commit")
            except RuntimeError:
                pass  # transaction rolled back

        # Verify no rows in outbox
        async with factory() as session:
            result = await session.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(OutboxEntry)
            )
            rows = result.scalars().all()
        assert rows == [], "Outbox must be empty after rollback"

    async def test_commit_persists_outbox_entry(self, engine) -> None:
        """After a successful commit, the outbox entry is retrievable."""
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        env = _envelope("claim.ingested")

        async with factory() as session:
            async with session.begin():
                await enqueue_event(session, env)

        async with factory() as session:
            from sqlalchemy import select
            result = await session.execute(
                select(OutboxEntry).where(OutboxEntry.idempotency_key == env.idempotency_key)
            )
            row = result.scalar_one_or_none()

        assert row is not None
        assert row.event_type == "claim.ingested"
        assert row.published_at is None


class TestOutboxRelay:
    async def test_relay_publishes_unpublished_entries(self, engine) -> None:
        """Relay picks up unpublished entries and publishes them to the bus."""
        bus = InMemoryEventBus()
        await bus.start()
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        env = _envelope("claim.ingested")
        async with factory() as session:
            async with session.begin():
                await enqueue_event(session, env)

        relay = OutboxRelay(engine=engine, bus=bus, poll_interval=0.0, batch_size=10)
        await relay._relay_batch()

        assert len(bus.published) == 1
        assert bus.published[0].event_type == "claim.ingested"

    async def test_relay_marks_published_at_on_success(self, engine) -> None:
        """After successful publish, published_at is set."""
        from sqlalchemy import select

        bus = InMemoryEventBus()
        await bus.start()
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        env = _envelope("payment.settled")
        async with factory() as session:
            async with session.begin():
                await enqueue_event(session, env)

        relay = OutboxRelay(engine=engine, bus=bus)
        await relay._relay_batch()

        async with factory() as session:
            result = await session.execute(
                select(OutboxEntry).where(OutboxEntry.idempotency_key == env.idempotency_key)
            )
            row = result.scalar_one()

        assert row.published_at is not None

    async def test_relay_does_not_republish_already_published(self, engine) -> None:
        """Relay skips entries with published_at already set."""
        bus = InMemoryEventBus()
        await bus.start()
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        env = _envelope("claim.ingested")
        async with factory() as session:
            async with session.begin():
                await enqueue_event(session, env)

        relay = OutboxRelay(engine=engine, bus=bus)
        await relay._relay_batch()  # First pass — publishes
        await relay._relay_batch()  # Second pass — skips (already published)

        assert len(bus.published) == 1  # Only one publish, not two

    async def test_relay_increments_attempts_on_publish_failure(self, engine) -> None:
        """If publish fails, attempts counter increments (entry not marked published)."""
        from sqlalchemy import select

        failing_bus = InMemoryEventBus()
        await failing_bus.start()
        original_publish = failing_bus.publish

        async def _fail_publish(envelope: EventEnvelope) -> None:
            raise RuntimeError("Bus unavailable")

        failing_bus.publish = _fail_publish  # type: ignore[method-assign]
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        env = _envelope("payment_batch.submitted")
        async with factory() as session:
            async with session.begin():
                await enqueue_event(session, env)

        relay = OutboxRelay(engine=engine, bus=failing_bus)
        await relay._relay_batch()

        async with factory() as session:
            result = await session.execute(
                select(OutboxEntry).where(OutboxEntry.idempotency_key == env.idempotency_key)
            )
            row = result.scalar_one()

        assert row.published_at is None
        assert row.attempts == 1

    async def test_relay_skips_entries_exceeding_max_attempts(self, engine) -> None:
        """Entries with attempts >= MAX_RELAY_ATTEMPTS are skipped by relay."""
        bus = InMemoryEventBus()
        await bus.start()
        factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        env = _envelope("claim.ingested")
        async with factory() as session:
            async with session.begin():
                entry = await enqueue_event(session, env)
                # Force attempts to MAX
                entry.attempts = MAX_RELAY_ATTEMPTS

        relay = OutboxRelay(engine=engine, bus=bus)
        count = await relay._relay_batch()

        assert count == 0  # Skipped
        assert len(bus.published) == 0
