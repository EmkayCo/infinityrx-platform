"""Unit tests for InvestigationService.transition().

Uses in-memory SQLite + SAVEPOINT isolation per LESSON-001 + LESSON-007.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import String, create_engine, event
from sqlalchemy.orm import Session

# LESSON-007: remap PG_UUID to VARCHAR for SQLite
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator

from src.models.tables import Base, Investigation, InvestigationActivity
from src.services.investigation_service import InvestigationService
from src.utils.constants import InvalidTransitionError


class _UUIDString(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(value) if value is not None else None


@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    with eng.begin() as conn:
        for tbl in Base.metadata.sorted_tables:
            for col in tbl.columns:
                if isinstance(col.type, PG_UUID):
                    col.type = _UUIDString()
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


def _make_investigation(db: Session, status: str = "open") -> Investigation:
    tid = uuid.uuid4()
    inv = Investigation(
        id=str(uuid.uuid4()),
        tenant_id=str(tid),
        investigation_number="INV-2026-TEST",
        title="Test investigation",
        subject_type="pharmacy",
        subject_entity_id="pharmacy-123",
        investigation_type="rule_firing",
        status=status,
    )
    db.add(inv)
    db.flush()
    return inv


class TestTransitionMethod:
    def test_valid_transition_updates_status(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="in_progress",
            role="reclaimrx.investigator",
            user_id=uuid.uuid4(),
            reason="Starting review",
        )
        db.refresh(inv)
        assert inv.status == "in_progress"

    def test_transition_writes_audit_activity(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        user = uuid.uuid4()
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="in_progress",
            role="reclaimrx.investigator",
            user_id=user,
            reason="Starting review",
        )
        activities = db.query(InvestigationActivity).filter_by(investigation_id=inv.id).all()
        # Filter to status_transition activities only (skip creation activity if any)
        transition_acts = [a for a in activities if a.activity_type == "status_transition"]
        assert len(transition_acts) >= 1
        act = transition_acts[0]
        assert "open" in (act.description or "")
        assert "in_progress" in (act.description or "")

    def test_invalid_transition_raises_invalid_transition_error(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="closed_confirmed",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="skip to close",
            )
        assert exc_info.value.code == "INVALID_TRANSITION"
        # investigation status must be unchanged
        db.refresh(inv)
        assert inv.status == "open"

    def test_missing_reason_raises(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="",
            )
        assert exc_info.value.code == "MISSING_REQUIRED_FIELD"

    def test_escalated_to_in_progress_requires_admin(self, db):
        inv = _make_investigation(db, status="escalated")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="re-open",
            )
        assert exc_info.value.code == "INSUFFICIENT_ROLE"

    def test_closed_confirmed_to_in_progress_requires_admin(self, db):
        inv = _make_investigation(db, status="closed_confirmed")
        svc = InvestigationService(db)
        with pytest.raises(InvalidTransitionError) as exc_info:
            svc.transition(
                tenant_id=uuid.UUID(inv.tenant_id),
                investigation_id=inv.id,
                to_state="in_progress",  # not in allowed list for closed_confirmed
                role="reclaimrx.admin",
                user_id=uuid.uuid4(),
                reason="re-open",
            )
        assert exc_info.value.code == "INVALID_TRANSITION"

    def test_closed_to_open_succeeds_for_admin(self, db):
        inv = _make_investigation(db, status="closed_confirmed")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="open",
            role="reclaimrx.admin",
            user_id=uuid.uuid4(),
            reason="new evidence",
        )
        db.refresh(inv)
        assert inv.status == "open"

    def test_closed_confirmed_sets_outcome_and_recovered(self, db):
        inv = _make_investigation(db, status="in_progress")
        svc = InvestigationService(db)
        svc.transition(
            tenant_id=uuid.UUID(inv.tenant_id),
            investigation_id=inv.id,
            to_state="closed_confirmed",
            role="reclaimrx.investigator",
            user_id=uuid.uuid4(),
            reason="Confirmed billing fraud",
            outcome_label="confirmed",
            recovered_amount=Decimal("2500.00"),
        )
        db.refresh(inv)
        assert inv.status == "closed_confirmed"
        # actual_recovered updated
        assert Decimal(str(inv.actual_recovered)) == Decimal("2500.00")

    def test_investigation_not_found_raises(self, db):
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="NOT_FOUND"):
            svc.transition(
                tenant_id=uuid.uuid4(),
                investigation_id="nonexistent-id",
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="test",
            )

    def test_cross_tenant_not_found(self, db):
        inv = _make_investigation(db, status="open")
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="NOT_FOUND"):
            svc.transition(
                tenant_id=uuid.uuid4(),   # different tenant
                investigation_id=inv.id,
                to_state="in_progress",
                role="reclaimrx.investigator",
                user_id=uuid.uuid4(),
                reason="cross-tenant attempt",
            )
