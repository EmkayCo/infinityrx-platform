"""Tests for investigation service — TDD first."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session
from src.services.investigation_service import InvestigationService

from tests.conftest import OTHER_TENANT_ID, TEST_TENANT_ID, TEST_USER_ID


class TestInvestigationCreation:
    def test_creates_investigation_with_number(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Test Pharmacy",
            investigation_type="desk_audit",
            title="Test Investigation",
            priority="high",
            user_id=TEST_USER_ID,
        )
        db.flush()
        assert inv.investigation_number.startswith("INV-")
        assert inv.status == "open"
        assert inv.tenant_id == str(TEST_TENANT_ID)

    def test_creates_with_unique_investigation_number(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv1 = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1111111111",
            subject_name="Pharmacy A",
            investigation_type="desk_audit",
            title="Investigation A",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        inv2 = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="2222222222",
            subject_name="Pharmacy B",
            investigation_type="desk_audit",
            title="Investigation B",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        db.flush()
        assert inv1.investigation_number != inv2.investigation_number

    def test_tenant_isolation_on_list(self, db: Session) -> None:
        svc = InvestigationService(db)
        svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="My Pharmacy",
            investigation_type="fraud_investigation",
            title="My Investigation",
            priority="high",
            user_id=TEST_USER_ID,
        )
        db.flush()
        results = svc.list_investigations(tenant_id=OTHER_TENANT_ID)
        assert len(results) == 0

    def test_list_investigations_returns_own_tenant(self, db: Session) -> None:
        svc = InvestigationService(db)
        svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="5555555555",
            subject_name="Filtered Pharmacy",
            investigation_type="desk_audit",
            title="Visible Investigation",
            priority="low",
            user_id=TEST_USER_ID,
        )
        db.flush()
        results = svc.list_investigations(tenant_id=TEST_TENANT_ID)
        assert any(i.title == "Visible Investigation" for i in results)


class TestInvestigationStatusTransition:
    def test_valid_status_transition(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Status Test",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        db.flush()
        updated = svc.update_status(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            new_status="in_progress",
            user_id=TEST_USER_ID,
            notes="Starting review",
        )
        assert updated.status == "in_progress"

    def test_invalid_status_transition_raises(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Bad Transition Test",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        db.flush()
        with pytest.raises(ValueError, match="Invalid status transition"):
            svc.update_status(
                tenant_id=TEST_TENANT_ID,
                investigation_id=inv.id,
                new_status="recovered",
                user_id=TEST_USER_ID,
            )

    def test_cannot_update_other_tenant_investigation(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Cross Tenant Test",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        db.flush()
        with pytest.raises(ValueError, match="not found"):
            svc.update_status(
                tenant_id=OTHER_TENANT_ID,
                investigation_id=inv.id,
                new_status="in_progress",
                user_id=TEST_USER_ID,
            )


class TestRecoveryEstimation:
    def test_create_recovery_record(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Recovery Test",
            priority="high",
            user_id=TEST_USER_ID,
        )
        db.flush()
        recovery = svc.create_recovery(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            recovery_method="offset_from_payment",
            amount=Decimal("1500.75"),
            confidence_tier="high",
            methodology_tag="NQ excess over 110% WAC x quantity across 47 claims",
            user_id=TEST_USER_ID,
        )
        db.flush()
        assert recovery.amount == Decimal("1500.75")
        assert recovery.status == "estimated"
        assert recovery.methodology_tag == "NQ excess over 110% WAC x quantity across 47 claims"

    def test_recovery_amount_is_decimal(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Decimal Test",
            priority="medium",
            user_id=TEST_USER_ID,
        )
        db.flush()
        recovery = svc.create_recovery(
            tenant_id=TEST_TENANT_ID,
            investigation_id=inv.id,
            recovery_method="direct_payment",
            amount=Decimal("999.99"),
            confidence_tier="medium",
            methodology_tag="Statistical estimate",
            user_id=TEST_USER_ID,
        )
        db.flush()
        assert isinstance(recovery.amount, Decimal)

    def test_activity_logged_on_creation(self, db: Session) -> None:
        svc = InvestigationService(db)
        inv = svc.create_investigation(
            tenant_id=TEST_TENANT_ID,
            subject_type="pharmacy",
            subject_entity_id="1234567890",
            subject_name="Pharmacy",
            investigation_type="desk_audit",
            title="Activity Log Test",
            priority="low",
            user_id=TEST_USER_ID,
        )
        db.flush()
        activities = svc.get_timeline(tenant_id=TEST_TENANT_ID, investigation_id=inv.id)
        assert len(activities) >= 1
        assert activities[0].activity_type == "investigation_opened"
