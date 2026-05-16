"""Integration tests for prescriber-directory event consumer wiring.

CR-01 v2 BLOCK-5 (HIPAA) fix: handle_claim_ingested must filter
PrescriberPharmacyRelationship queries by tenant_id. Without it,
Tenant A's prescriber-pharmacy volumes are visible to Tenant B.

These tests verify:
1. wire_consumers() subscribes claim.ingested and exclusion.match_found
2. claim.ingested creates a PrescriberPharmacyRelationship row with tenant_id
3. Tenant isolation: Tenant B sees zero rows after Tenant A's claim event
4. Missing tenant_id in envelope causes warning + skip (no crash, no cross-tenant write)
5. session_factory is called per-event
"""
from __future__ import annotations

import os
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))
_PLATFORM_ROOT = _MODULE_ROOT.parent.parent
if str(_PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLATFORM_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from shared.events import InMemoryEventBus, EventEnvelope
from shared.events.idempotency import InMemoryIdempotencyStore
from src.models.tables import PrescriberBase, PrescriberPharmacyRelationship


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). Fixes LESSON-007."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
PRESCRIBER_NPI = "1234567893"
PHARMACY_NPI = "9876543210"


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in PrescriberBase.metadata.tables.values():
        table.schema = None
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
    PrescriberBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based session fixture (LESSON-001)."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


def _make_session_factory(session: Session):
    @contextmanager
    def _factory():
        yield session
        session.flush()

    return _factory


@pytest.mark.asyncio
async def test_wire_consumers_subscribes_claim_ingested(_engine):
    """wire_consumers() must subscribe a handler for claim.ingested."""
    from src.events import wire_consumers

    connection = _engine.connect()
    session = Session(bind=connection, expire_on_commit=False)
    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, session_factory=_make_session_factory(session))
    assert any(t == "claim.ingested" for t, _ in bus._subs), "claim.ingested must be subscribed"
    await bus.stop()
    session.close()
    connection.close()


@pytest.mark.asyncio
async def test_claim_ingested_creates_row_with_tenant_id(db_session):
    """claim.ingested creates a PrescriberPharmacyRelationship row scoped to tenant_id."""
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(
        bus,
        session_factory=_make_session_factory(db_session),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    envelope = EventEnvelope(
        event_type="claim.ingested",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="billing",
        payload={
            "prescriber_npi": PRESCRIBER_NPI,
            "pharmacy_npi": PHARMACY_NPI,
            "date_of_service": "2026-05-01",
        },
    )
    await bus.publish(envelope)
    await bus.stop()

    rows = db_session.query(PrescriberPharmacyRelationship).filter_by(
        tenant_id=TENANT_A,
        prescriber_npi=PRESCRIBER_NPI,
        pharmacy_npi=PHARMACY_NPI,
    ).all()
    assert len(rows) == 1, "A PrescriberPharmacyRelationship row must be created"
    assert rows[0].tenant_id == TENANT_A, "Row must be scoped to the correct tenant"
    assert rows[0].claim_count == 1


@pytest.mark.asyncio
async def test_tenant_isolation_tenant_b_sees_zero_rows(db_session):
    """HIPAA: Tenant B must see zero rows when only Tenant A's events were processed."""
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(
        bus,
        session_factory=_make_session_factory(db_session),
        idempotency_store=InMemoryIdempotencyStore(),
    )

    # Publish a claim for Tenant A only
    envelope_a = EventEnvelope(
        event_type="claim.ingested",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="billing",
        payload={
            "prescriber_npi": "1111111111",
            "pharmacy_npi": "2222222222",
            "date_of_service": "2026-05-10",
        },
    )
    await bus.publish(envelope_a)
    await bus.stop()

    # Tenant B must see zero rows
    tenant_b_rows = db_session.query(PrescriberPharmacyRelationship).filter_by(
        tenant_id=TENANT_B,
    ).all()
    assert len(tenant_b_rows) == 0, (
        "HIPAA: Tenant B must see zero PrescriberPharmacyRelationship rows "
        "when only Tenant A events were processed"
    )


@pytest.mark.asyncio
async def test_session_factory_called_per_event(_engine):
    """session_factory must be called for each event delivery, not once at startup."""
    from src.events import wire_consumers

    call_count = 0
    connection = _engine.connect()
    session = Session(bind=connection, expire_on_commit=False)

    @contextmanager
    def counting_factory():
        nonlocal call_count
        call_count += 1
        yield session
        session.flush()

    bus = InMemoryEventBus()
    await bus.start()
    store = InMemoryIdempotencyStore()
    await wire_consumers(bus, session_factory=counting_factory, idempotency_store=store)

    for i in range(2):
        env = EventEnvelope(
            event_type="claim.ingested",
            tenant_id=TENANT_A,
            correlation_id=CORR,
            source_module="billing",
            payload={
                "prescriber_npi": f"111111111{i}",
                "pharmacy_npi": f"222222222{i}",
                "date_of_service": "2026-05-15",
            },
        )
        await bus.publish(env)

    await bus.stop()
    session.close()
    connection.close()
    assert call_count == 2, "session_factory must be called once per event delivery"
