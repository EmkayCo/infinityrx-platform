"""Extended tests for investigation service — covering uncovered branches."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from src.models.tables import Investigation
from src.services.investigation_service import InvestigationService

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _make_inv(db: Session, svc: InvestigationService, **kwargs) -> Investigation:
    defaults = dict(
        tenant_id=TEST_TENANT_ID,
        subject_type="pharmacy",
        subject_entity_id="1234567890",
        subject_name="Test Pharmacy",
        investigation_type="desk_audit",
        title="Test Investigation",
        priority="high",
        user_id=TEST_USER_ID,
    )
    defaults.update(kwargs)
    inv = svc.create_investigation(**defaults)
    db.flush()
    return inv


class TestStatusTransitionResolved:
    def test_status_transition_to_closed_confirmed_sets_resolved_at(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        # open -> in_progress -> closed_confirmed (spec §5.5.1 terminal state)
        svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="in_progress",
            user_id=TEST_USER_ID,
        )
        svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="closed_confirmed",
            user_id=TEST_USER_ID,
        )
        assert inv.resolved_at is not None
        assert inv.status == "closed_confirmed"

    def test_status_transition_to_closed_false_positive_sets_resolved_at(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        # open -> in_progress -> closed_false_positive (spec §5.5.1 terminal state)
        svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="in_progress",
            user_id=TEST_USER_ID,
        )
        svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="closed_false_positive",
            user_id=TEST_USER_ID,
        )
        assert inv.resolved_at is not None

    def test_status_change_without_notes(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        updated = svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="in_progress",
            user_id=TEST_USER_ID,
        )
        assert updated.status == "in_progress"


class TestAssign:
    def test_assign_investigation(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        assignee_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
        updated = svc.assign(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            assignee_id=assignee_id,
            user_id=TEST_USER_ID,
        )
        assert updated.assigned_to == str(assignee_id)
        assert updated.assigned_at is not None

    def test_assign_logs_activity(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        assignee_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
        svc.assign(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            assignee_id=assignee_id,
            user_id=TEST_USER_ID,
        )
        timeline = svc.get_timeline(tenant_id=TEST_TENANT_ID, investigation_id=inv.id)
        types = [a.activity_type for a in timeline]
        assert "assigned" in types


class TestUpdateRecoveryStatus:
    def test_update_recovery_status(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        recovery = svc.create_recovery(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            recovery_method="offset_from_payment",
            amount=Decimal("500.00"),
            confidence_tier="high",
            methodology_tag="Test",
            user_id=TEST_USER_ID,
        )
        db.flush()
        updated = svc.update_recovery_status(
            tenant_id=TEST_TENANT_ID,
            recovery_id=recovery.id,
            new_status="collected",
            user_id=TEST_USER_ID,
        )
        assert updated.status == "collected"

    def test_update_nonexistent_recovery_raises(self, db: Session) -> None:
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="not found"):
            svc.update_recovery_status(
                tenant_id=TEST_TENANT_ID,
                recovery_id=str(uuid.uuid4()),
                new_status="collected",
                user_id=TEST_USER_ID,
            )


class TestAddActivity:
    def test_add_activity_public_method(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        activity = svc.add_activity(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            activity_type="document_reviewed",
            description="Reviewed pharmacy dispensing logs",
            user_id=TEST_USER_ID,
            file_id="file-123",
        )
        assert activity.activity_type == "document_reviewed"
        assert activity.file_id == "file-123"

    def test_add_activity_invalid_investigation_raises(self, db: Session) -> None:
        svc = InvestigationService(db)
        with pytest.raises(ValueError, match="not found"):
            svc.add_activity(
                tenant_id=TEST_TENANT_ID,
                investigation_id=str(uuid.uuid4()),
                activity_type="note",
                description="Some note",
                user_id=TEST_USER_ID,
            )


class TestListInvestigationsFilters:
    def test_list_filter_by_status(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc, title="Open Inv")
        svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="in_progress",
            user_id=TEST_USER_ID,
        )
        open_results = svc.list_investigations(tenant_id=TEST_TENANT_ID, status="open")
        in_progress_results = svc.list_investigations(tenant_id=TEST_TENANT_ID, status="in_progress")
        assert all(i.status == "open" for i in open_results)
        assert any(i.id == inv.id for i in in_progress_results)

    def test_list_filter_by_subject_type(self, db: Session) -> None:
        svc = InvestigationService(db)
        _make_inv(db, svc, subject_type="pharmacy", title="Pharmacy Inv")
        _make_inv(db, svc, subject_type="prescriber", title="Prescriber Inv", subject_entity_id="9999999999")
        pharmacy_results = svc.list_investigations(tenant_id=TEST_TENANT_ID, subject_type="pharmacy")
        assert all(i.subject_type == "pharmacy" for i in pharmacy_results)


class TestLitigationHold:
    def test_set_litigation_hold(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        updated = svc.set_litigation_hold(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            placed_by=TEST_USER_ID,
        )
        assert updated.litigation_hold is True
        assert updated.litigation_hold_placed_by == str(TEST_USER_ID)
        assert updated.litigation_hold_placed_at is not None

    def test_litigation_hold_logs_activity(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = _make_inv(db, svc)
        svc.set_litigation_hold(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            placed_by=TEST_USER_ID,
        )
        timeline = svc.get_timeline(tenant_id=TEST_TENANT_ID, investigation_id=inv.id)
        types = [a.activity_type for a in timeline]
        assert "litigation_hold_placed" in types
