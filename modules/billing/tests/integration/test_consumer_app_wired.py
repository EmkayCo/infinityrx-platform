"""End-to-end test: the real billing app persists a ClaimRecord + APRecord
when a claim.adjudicated event is published on the bus.

Prior to this wiring, `wire_consumers()` passed ``db=None`` in production
so every event fell through the log-only path. This test starts the actual
FastAPI app (exercising the lifespan → ``wire_consumers`` code path), then
publishes one envelope and asserts persistence.

The test stitches three things together:
  1. The billing SQLite test engine (session-scoped) is installed into
     billing's ``src.db.session`` via ``set_engine`` so
     ``get_db_session()`` yields a real session against the test DB.
  2. ``set_event_bus`` swaps in a fresh InMemoryEventBus for this test.
  3. Starting the TestClient triggers the lifespan, which calls
     ``wire_consumers(bus)`` and subscribes all four handlers.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from shared.events.factory import reset_event_bus, set_event_bus
from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.types import EventEnvelope
from src.db import session as billing_session
from src.main import create_app
from src.models.tables import APRecord, ClaimRecord
from tests.conftest import TENANT_A


TENANT = TENANT_A


@pytest.fixture()
def wired_app(monkeypatch):
    """Build a real app wired to a private SQLite engine + a fresh bus.

    Uses its own engine (not the shared session-scoped ``_engine``) because
    ``get_db_session()`` issues real commits which would leak into the
    SAVEPOINT-isolated tests sharing that engine.
    """
    from sqlalchemy import create_engine

    private_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, future=True)

    # Patch the `src.models.tables` metadata (used by conftest-imported
    # symbols) AND the fully-qualified `modules.billing.src.models.tables`
    # metadata (the one consumers import via relative `..models.tables`).
    # They are TWO distinct module objects under the sys.path shim, so each
    # carries its own Table objects.
    from src.models.tables import BillingBase as ShortBase
    import modules.billing.src.models.tables as billing_models_full

    for base in (ShortBase, billing_models_full.BillingBase):
        for table in base.metadata.tables.values():
            table.schema = None
        base.metadata.create_all(private_engine)

    assert ClaimRecord.__table__.schema is None, "schema strip did not run"
    billing_session.set_engine(private_engine)

    # Use a fresh InMemoryEventBus for this test. Without reset_event_bus()
    # the module-level singleton could carry subscribers across tests.
    reset_event_bus()
    bus = InMemoryEventBus()
    set_event_bus(bus)

    # Reset the idempotency store so a repeated-test key doesn't short-circuit.
    from src.events import _idempotency_store
    _idempotency_store._store.clear()

    # Make BILLING_DATABASE_URL non-empty so `_get_engine()` doesn't
    # complain if it somehow skips the override path.
    monkeypatch.setenv("BILLING_DATABASE_URL", "sqlite:///:memory:")

    app = create_app()
    with TestClient(app) as client:
        yield client, bus

    reset_event_bus()
    billing_session._engine = None  # type: ignore[attr-defined]
    billing_session._SessionFactory = None  # type: ignore[attr-defined]
    private_engine.dispose()


def _envelope() -> EventEnvelope:
    return EventEnvelope(
        event_type="claim.adjudicated",
        tenant_id=TENANT,
        correlation_id=uuid.uuid4(),
        source_module="adjudication-engine",
        schema_version="1.0",
        ordering_key="AUTH-E2E",
        idempotency_key=f"claim.adjudicated:{uuid.uuid4()}",
        payload={
            "auth_number": "AUTH-E2E-1",
            "claim_type": "new",
            "net_amount": "42.50",
            "pharmacy_npi": "1234567890",
            "date_of_service": "2026-04-01",
            "client_id": str(uuid.uuid4()),
            "program_id": str(uuid.uuid4()),
            "pay_to_entity_id": str(uuid.uuid4()),
            "pay_to_entity_name": "Main St Rx",
            "payment_route": "ach",
        },
    )


@pytest.mark.asyncio
async def test_claim_adjudicated_persists_through_real_app(wired_app) -> None:
    client, bus = wired_app
    # TestClient context starts the lifespan; a health call proves it's up.
    assert client.get("/health").status_code in (200, 503)

    await bus.publish(_envelope())

    # Surface any wrapper-side error so the test failure is informative.
    assert not bus.handler_errors, f"handler errors: {bus.handler_errors}"

    # Read back through the SAME ORM classes the consumer used (the
    # fully-qualified module path), against the engine that's now wired.
    import modules.billing.src.models.tables as t
    SessionLocal = sessionmaker(bind=billing_session._get_engine(), expire_on_commit=False)
    session = SessionLocal()
    try:
        claim = session.query(t.ClaimRecord).filter_by(auth_number="AUTH-E2E-1").one()
        assert claim.tenant_id == TENANT
        ap = session.query(t.APRecord).filter_by(claim_record_id=claim.id).one()
        assert ap.status == "created"
        assert str(ap.amount) == "42.50"
    finally:
        session.close()
