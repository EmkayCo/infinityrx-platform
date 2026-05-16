"""Integration tests for medical-claims event consumer wiring.

CR-01 v2 BLOCK-2 fix: wire_consumers() must receive real ClaimService and
UnifiedDrugSpendService backed by a real (in-memory) DB session —
not None stubs that silently no-op every event.

These tests use InMemoryEventBus and SQLite sessions to verify:
1. edi.837_received → ClaimService.ingest_from_edi_payload creates real rows
2. claim.adjudicated → UnifiedDrugSpendService.record_pharmacy_claim creates real rows
3. Idempotency: duplicate envelopes are dropped
4. session_factory is called per-event (per-delivery session pattern)
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
from sqlalchemy import JSON, LargeBinary, String, Text, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from shared.events import InMemoryEventBus, EventEnvelope
from shared.events.idempotency import InMemoryIdempotencyStore
from src.models.tables import MedicalClaimsBase, ClaimRecord, UnifiedDrugSpend


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36). Fixes LESSON-007."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


class _EncryptedStringStub(TypeDecorator):
    """SQLite-compatible stub for EncryptedString (LargeBinary → Text).

    EncryptedString encrypts in process_bind_param and decrypts in
    process_result_value — those methods are still called. We only swap the
    underlying impl so SQLite can store the ciphertext as TEXT rather than BLOB,
    which avoids the 'no such type BLOB' error on SQLite table creation.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # EncryptedString returns bytes; Text requires str — base64 encode for storage
        if isinstance(value, bytes):
            import base64
            return base64.b64encode(value).decode("ascii")
        return value

    def process_result_value(self, value, dialect):
        if isinstance(value, str):
            import base64
            return base64.b64decode(value)
        return value


TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORR = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="module")
def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Patch column types for SQLite compatibility (LESSON-007)
    # EncryptedString wraps LargeBinary — swap to Text-backed stub so SQLite
    # can store the ciphertext without the 'no such type BLOB' error.
    for table in MedicalClaimsBase.metadata.tables.values():
        table.schema = None
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            elif isinstance(col.type, LargeBinary):
                col.type = _EncryptedStringStub()
    MedicalClaimsBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(_engine) -> Iterator[Session]:
    """SAVEPOINT-based session fixture (LESSON-001)."""
    connection = _engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

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
    """Return a per-event session factory that yields the shared test session."""
    @contextmanager
    def _factory():
        yield session
        session.flush()

    return _factory


def _fresh_store() -> InMemoryIdempotencyStore:
    """Fresh idempotency store per test — avoids cross-test seen() state."""
    return InMemoryIdempotencyStore()


@pytest.mark.asyncio
async def test_edi_837_received_creates_claim_record(db_session):
    """edi.837_received with real session creates a ClaimRecord row."""
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()

    session_factory = _make_session_factory(db_session)
    await wire_consumers(bus, session_factory=session_factory, idempotency_store=_fresh_store())

    envelope = EventEnvelope(
        event_type="edi.837_received",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="edi-compliance",
        payload={
            "transaction_type": "837P",
            "transaction_record_id": str(uuid.uuid4()),
            "claim_lines": [
                {
                    "claim_number": "CR01-INTEG-001",
                    "claim_line_number": 1,
                    "procedure_code": "J0135",
                    "patient_member_id": "MBR-CR01",
                    "rendering_provider_npi": "1234567890",
                    "date_of_service": "2026-05-01",
                    "billed_amount": "350.00",
                }
            ],
        },
    )
    await bus.publish(envelope)
    await bus.stop()

    rows = db_session.query(ClaimRecord).filter_by(
        tenant_id=TENANT_A, claim_number="CR01-INTEG-001"
    ).all()
    assert len(rows) == 1, "ClaimService.ingest_from_edi_payload must create a real row"
    assert rows[0].procedure_code == "J0135"


@pytest.mark.asyncio
async def test_claim_adjudicated_creates_unified_spend_row(db_session):
    """claim.adjudicated with real session creates a UnifiedDrugSpend row."""
    from src.events import wire_consumers

    bus = InMemoryEventBus()
    await bus.start()

    session_factory = _make_session_factory(db_session)
    await wire_consumers(bus, session_factory=session_factory, idempotency_store=_fresh_store())

    pharm_claim_id = uuid.uuid4()
    member_id = uuid.uuid4()
    envelope = EventEnvelope(
        event_type="claim.adjudicated",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="billing",
        payload={
            "claim_id": str(pharm_claim_id),
            "member_id": str(member_id),
            "member_id_display": "MBR-CR01-ADJ",
            "ndc": "12345678901",
            "drug_name": "TestDrug",
            "date_of_service": "2026-05-01",
            "billed_amount": "600.00",
            "allowed_amount": "550.00",
            "paid_amount": "500.00",
            "patient_pay": "50.00",
            "quantity": "1.0",
            "days_supply": 30,
            "therapeutic_class": "Biologic",
        },
    )
    await bus.publish(envelope)
    await bus.stop()

    rows = db_session.query(UnifiedDrugSpend).filter_by(
        tenant_id=TENANT_A, pharmacy_claim_id=pharm_claim_id
    ).all()
    assert len(rows) == 1, "UnifiedDrugSpendService.record_pharmacy_claim must create a real row"
    assert rows[0].drug_name == "TestDrug"


@pytest.mark.asyncio
async def test_idempotency_duplicate_edi_event_not_reprocessed(db_session):
    """Duplicate edi.837_received envelopes must not create duplicate claim rows."""
    from src.events import wire_consumers

    store = _fresh_store()
    bus = InMemoryEventBus()
    await bus.start()

    session_factory = _make_session_factory(db_session)
    await wire_consumers(bus, session_factory=session_factory, idempotency_store=store)

    idempotency_key = f"edi.837_received:dedup-test-{uuid.uuid4()}"
    envelope = EventEnvelope(
        event_type="edi.837_received",
        tenant_id=TENANT_A,
        correlation_id=CORR,
        source_module="edi-compliance",
        idempotency_key=idempotency_key,
        payload={
            "transaction_type": "837P",
            "transaction_record_id": str(uuid.uuid4()),
            "claim_lines": [
                {
                    "claim_number": "CR01-DEDUP-001",
                    "claim_line_number": 1,
                    "procedure_code": "J0135",
                    "patient_member_id": "MBR-DEDUP",
                    "rendering_provider_npi": "1234567890",
                    "date_of_service": "2026-05-02",
                    "billed_amount": "200.00",
                }
            ],
        },
    )
    # Publish twice with same idempotency key — second must be dropped
    await bus.publish(envelope)
    await bus.publish(envelope)
    await bus.stop()

    rows = db_session.query(ClaimRecord).filter_by(
        tenant_id=TENANT_A, claim_number="CR01-DEDUP-001"
    ).all()
    assert len(rows) == 1, "Idempotent: duplicate event must produce only 1 claim row"


@pytest.mark.asyncio
async def test_session_factory_called_per_event(db_session):
    """session_factory must be called for each event delivery, not once at startup."""
    from src.events import wire_consumers

    call_count = 0

    @contextmanager
    def counting_factory():
        nonlocal call_count
        call_count += 1
        yield db_session
        db_session.flush()

    bus = InMemoryEventBus()
    await bus.start()
    await wire_consumers(bus, session_factory=counting_factory, idempotency_store=_fresh_store())

    pharm_id_1 = uuid.uuid4()
    pharm_id_2 = uuid.uuid4()

    for pharm_id in [pharm_id_1, pharm_id_2]:
        env = EventEnvelope(
            event_type="claim.adjudicated",
            tenant_id=TENANT_A,
            correlation_id=CORR,
            source_module="billing",
            payload={
                "claim_id": str(pharm_id),
                "member_id": str(uuid.uuid4()),
                "ndc": "11111111111",
                "drug_name": "SessCountDrug",
                "date_of_service": "2026-05-03",
                "billed_amount": "100.00",
                "paid_amount": "90.00",
            },
        )
        await bus.publish(env)

    await bus.stop()
    assert call_count == 2, "session_factory must be invoked once per event delivery"
