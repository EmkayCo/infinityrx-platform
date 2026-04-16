"""Unit tests for the PA lifecycle management service.

Tests cover: creation from different sources, auto-approve transitions,
review priority, appeal workflow, copay ePA first-fill, expiration,
and duplicate detection.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.models.tables import (
    CopayEPARecord,
    PAAppeal,
    PACriteriaSet,
    PADecision,
    PARequest,
)
from src.services.pa_lifecycle import (
    PA_EXPIRATION_DAYS,
    PALifecycleError,
    check_pa_status,
    create_copay_epa_first_fill,
    create_pa,
    decide_pa,
    evaluate_pa,
    expire_pas,
    submit_appeal,
)

# Reuse conftest UUIDs
from tests.conftest import MEMBER_1, PLAN_1, TENANT_A, TENANT_B, USER_A


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_criteria(
    db: Session,
    tenant_id: uuid.UUID,
    plan_id: uuid.UUID,
    drug_ndc: str = "12345678901",
    criteria: dict | None = None,
    version: int = 1,
) -> PACriteriaSet:
    cs = PACriteriaSet(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        drug_ndc=drug_ndc,
        drug_class=None,
        plan_id=plan_id,
        criteria=criteria or {"diagnosis_codes": ["E11"]},
        version=version,
        effective_date=date(2026, 1, 1),
    )
    db.add(cs)
    db.flush()
    return cs


def _create_test_pa(
    db: Session,
    tenant_id: uuid.UUID = TENANT_A,
    source: str = "manual",
    drug_ndc: str = "12345678901",
    priority: str = "routine",
) -> PARequest:
    return create_pa(
        db,
        tenant_id=tenant_id,
        member_id=MEMBER_1,
        prescriber_npi="1234567890",
        drug_ndc=drug_ndc,
        drug_name="Test Drug 100mg",
        source=source,
        plan_id=PLAN_1,
        priority=priority,
        clinical_data={"notes": "test"},
    )


# ---------------------------------------------------------------------------
# Test: Create PA from different sources
# ---------------------------------------------------------------------------


class TestCreatePA:
    def test_create_pa_from_pharmacy_reject(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, source="pharmacy_reject")

        assert pa.id is not None
        assert pa.source == "pharmacy_reject"
        assert pa.status == "submitted"
        assert pa.tenant_id == tenant_id

    def test_create_pa_from_epa(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, source="epa")

        assert pa.source == "epa"
        assert pa.status == "submitted"

    def test_create_pa_from_manual(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, source="manual")

        assert pa.source == "manual"

    def test_create_pa_from_phone(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, source="phone")

        assert pa.source == "phone"

    def test_create_pa_from_fhir(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, source="fhir")

        assert pa.source == "fhir"

    def test_invalid_source_raises(self, db_session, tenant_id):
        with pytest.raises(PALifecycleError, match="Invalid PA source"):
            _create_test_pa(db_session, tenant_id, source="invalid")

    def test_invalid_priority_raises(self, db_session, tenant_id):
        with pytest.raises(PALifecycleError, match="Invalid priority"):
            create_pa(
                db_session,
                tenant_id=tenant_id,
                member_id=MEMBER_1,
                prescriber_npi="1234567890",
                drug_ndc="12345678901",
                drug_name="Test Drug",
                source="manual",
                plan_id=PLAN_1,
                priority="super_urgent",
            )

    def test_criteria_version_captured_at_creation(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1, version=3)
        pa = _create_test_pa(db_session, tenant_id)

        assert pa.criteria_set_version == 3


# ---------------------------------------------------------------------------
# Test: PA auto-approved transitions
# ---------------------------------------------------------------------------


class TestEvaluatePA:
    def test_auto_approved_transitions_to_approved(self, db_session, tenant_id):
        _seed_criteria(
            db_session, tenant_id, PLAN_1,
            criteria={"diagnosis_codes": ["E11"]},
        )
        pa = _create_test_pa(db_session, tenant_id)

        result = evaluate_pa(
            db_session, pa.id, tenant_id,
            member_diagnoses=["E11.9"],
        )

        assert result.auto_approve is True
        assert pa.status == "approved"

    def test_no_criteria_set_routes_to_review(self, db_session, tenant_id):
        # No criteria seeded -- manual review required
        pa = create_pa(
            db_session,
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="99999999999",  # No criteria for this NDC
            drug_name="Unknown Drug",
            source="manual",
            plan_id=PLAN_1,
        )

        result = evaluate_pa(db_session, pa.id, tenant_id)

        assert result.auto_approve is False
        assert pa.status == "in_review"

    def test_missing_info_routes_to_review(self, db_session, tenant_id):
        _seed_criteria(
            db_session, tenant_id, PLAN_1,
            criteria={"diagnosis_codes": ["E11"]},
        )
        pa = _create_test_pa(db_session, tenant_id)

        result = evaluate_pa(
            db_session, pa.id, tenant_id,
            member_diagnoses=None,  # Missing
        )

        assert result.auto_approve is False
        assert pa.status == "in_review"


# ---------------------------------------------------------------------------
# Test: PA queued for review with correct priority
# ---------------------------------------------------------------------------


class TestReviewPriority:
    def test_urgent_pa_has_urgent_priority(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, priority="urgent")

        assert pa.priority == "urgent"

    def test_routine_pa_has_routine_priority(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id, priority="routine")

        assert pa.priority == "routine"


# ---------------------------------------------------------------------------
# Test: Appeal workflow
# ---------------------------------------------------------------------------


class TestAppealWorkflow:
    def test_deny_then_appeal_then_decision(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        # Deny the PA
        decision = decide_pa(
            db_session, pa.id, tenant_id,
            decision="denied",
            reviewer_id=USER_A,
            review_notes="Does not meet criteria",
        )
        assert decision.decision == "denied"
        assert pa.status == "denied"

        # Submit appeal
        appeal = submit_appeal(
            db_session, pa.id, tenant_id,
            appeal_level=1,
            appeal_type="clinical_reviewer",
            regulatory_deadline=date(2026, 5, 16),
        )
        assert appeal.appeal_level == 1
        assert appeal.status == "submitted"
        assert pa.status == "appealed"

    def test_cannot_appeal_non_denied_pa(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        with pytest.raises(PALifecycleError, match="Must be denied"):
            submit_appeal(
                db_session, pa.id, tenant_id,
                appeal_level=1,
                appeal_type="clinical_reviewer",
            )

    def test_invalid_appeal_type_raises(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)
        decide_pa(
            db_session, pa.id, tenant_id,
            decision="denied",
            reviewer_id=USER_A,
        )

        with pytest.raises(PALifecycleError, match="Invalid appeal type"):
            submit_appeal(
                db_session, pa.id, tenant_id,
                appeal_level=1,
                appeal_type="peer_to_peer",  # Invalid
            )


# ---------------------------------------------------------------------------
# Test: Decide PA
# ---------------------------------------------------------------------------


class TestDecidePA:
    def test_approve_with_duration(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        decision = decide_pa(
            db_session, pa.id, tenant_id,
            decision="approved",
            reviewer_id=USER_A,
            approved_duration_days=365,
            approved_quantity=Decimal("90.00"),
            review_notes="Criteria met after review",
        )

        assert decision.decision == "approved"
        assert decision.approved_duration_days == 365
        assert decision.approved_quantity == Decimal("90.00")
        assert pa.status == "approved"

    def test_pend_keeps_in_review(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        decide_pa(
            db_session, pa.id, tenant_id,
            decision="pend",
            reviewer_id=USER_A,
            review_notes="Awaiting lab results",
        )

        assert pa.status == "in_review"

    def test_request_info_keeps_in_review(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        decide_pa(
            db_session, pa.id, tenant_id,
            decision="request_info",
            reviewer_id=USER_A,
        )

        assert pa.status == "in_review"

    def test_invalid_decision_raises(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        with pytest.raises(PALifecycleError, match="Invalid decision"):
            decide_pa(
                db_session, pa.id, tenant_id,
                decision="maybe",
                reviewer_id=USER_A,
            )

    def test_cannot_decide_already_approved(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)
        decide_pa(
            db_session, pa.id, tenant_id,
            decision="approved",
            reviewer_id=USER_A,
        )

        with pytest.raises(PALifecycleError, match="Cannot decide PA"):
            decide_pa(
                db_session, pa.id, tenant_id,
                decision="denied",
                reviewer_id=USER_A,
            )


# ---------------------------------------------------------------------------
# Test: Copay ePA first-fill
# ---------------------------------------------------------------------------


class TestCopayEPAFirstFill:
    def test_creates_copay_epa_record(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        record = create_copay_epa_first_fill(
            db_session, pa.id, tenant_id,
            manufacturer_program_id="MFR-001",
            first_fill_amount=Decimal("25.50"),
            first_fill_date=date(2026, 4, 16),
        )

        assert record.manufacturer_program_id == "MFR-001"
        assert record.first_fill_amount == Decimal("25.50")
        assert record.first_fill_date == date(2026, 4, 16)
        assert record.pa_outcome == "submitted"
        assert record.manufacturer_absorbed_cost == Decimal("0.00")

    def test_first_fill_amount_rounded_correctly(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        pa = _create_test_pa(db_session, tenant_id)

        record = create_copay_epa_first_fill(
            db_session, pa.id, tenant_id,
            manufacturer_program_id="MFR-002",
            first_fill_amount=Decimal("25.555"),
            first_fill_date=date(2026, 4, 16),
        )

        # ROUND_HALF_UP: 25.555 -> 25.56
        assert record.first_fill_amount == Decimal("25.56")


# ---------------------------------------------------------------------------
# Test: PA expiration
# ---------------------------------------------------------------------------


class TestExpirePA:
    def test_expire_overdue_pas(self, db_session, tenant_id):
        # Manually create an old PA
        old_pa = PARequest(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="55555555555",
            drug_name="Old Drug",
            source="manual",
            status="submitted",
            priority="routine",
            plan_id=PLAN_1,
            created_at=datetime.now(UTC) - timedelta(days=PA_EXPIRATION_DAYS + 1),
        )
        db_session.add(old_pa)
        db_session.flush()

        count = expire_pas(db_session, tenant_id)

        assert count >= 1
        assert old_pa.status == "expired"

    def test_approved_pas_not_expired(self, db_session, tenant_id):
        old_approved = PARequest(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="66666666666",
            drug_name="Approved Drug",
            source="manual",
            status="approved",
            priority="routine",
            plan_id=PLAN_1,
            created_at=datetime.now(UTC) - timedelta(days=PA_EXPIRATION_DAYS + 1),
        )
        db_session.add(old_approved)
        db_session.flush()

        expire_pas(db_session, tenant_id)

        assert old_approved.status == "approved"

    def test_recent_pas_not_expired(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1, drug_ndc="77777777777")
        recent_pa = create_pa(
            db_session,
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="77777777777",
            drug_name="New Drug",
            source="manual",
            plan_id=PLAN_1,
        )

        expire_pas(db_session, tenant_id)

        assert recent_pa.status == "submitted"


# ---------------------------------------------------------------------------
# Test: Duplicate PA detection
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    def test_duplicate_active_pa_raises(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1)
        _create_test_pa(db_session, tenant_id)

        with pytest.raises(PALifecycleError, match="Active PA already exists"):
            _create_test_pa(db_session, tenant_id)

    def test_different_drug_allows_creation(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1, drug_ndc="11111111111")
        _seed_criteria(db_session, tenant_id, PLAN_1, drug_ndc="22222222222")

        pa1 = _create_test_pa(db_session, tenant_id, drug_ndc="11111111111")
        pa2 = _create_test_pa(db_session, tenant_id, drug_ndc="22222222222")

        assert pa1.drug_ndc != pa2.drug_ndc

    def test_expired_pa_allows_new_creation(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1, drug_ndc="33333333333")
        pa1 = create_pa(
            db_session,
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="33333333333",
            drug_name="Test Drug",
            source="manual",
            plan_id=PLAN_1,
        )
        pa1.status = "expired"
        db_session.flush()

        # Now can create a new one
        pa2 = create_pa(
            db_session,
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="33333333333",
            drug_name="Test Drug",
            source="manual",
            plan_id=PLAN_1,
        )
        assert pa2.status == "submitted"


# ---------------------------------------------------------------------------
# Test: Check PA status
# ---------------------------------------------------------------------------


class TestCheckPAStatus:
    def test_no_pa_returns_not_found(self, db_session, tenant_id):
        result = check_pa_status(
            db_session, tenant_id, MEMBER_1, "99999999999",
        )

        assert result["pa_exists"] is False
        assert result["status"] is None

    def test_submitted_pa_returns_status(self, db_session, tenant_id):
        _seed_criteria(db_session, tenant_id, PLAN_1, drug_ndc="44444444444")
        pa = create_pa(
            db_session,
            tenant_id=tenant_id,
            member_id=MEMBER_1,
            prescriber_npi="1234567890",
            drug_ndc="44444444444",
            drug_name="Status Drug",
            source="manual",
            plan_id=PLAN_1,
        )

        result = check_pa_status(
            db_session, tenant_id, MEMBER_1, "44444444444",
        )

        assert result["pa_exists"] is True
        assert result["status"] == "submitted"
        assert result["pa_id"] == str(pa.id)


# ---------------------------------------------------------------------------
# Test: PA not found
# ---------------------------------------------------------------------------


class TestPANotFound:
    def test_evaluate_nonexistent_pa_raises(self, db_session, tenant_id):
        with pytest.raises(PALifecycleError, match="not found"):
            evaluate_pa(db_session, uuid.uuid4(), tenant_id)

    def test_decide_nonexistent_pa_raises(self, db_session, tenant_id):
        with pytest.raises(PALifecycleError, match="not found"):
            decide_pa(
                db_session, uuid.uuid4(), tenant_id,
                decision="approved",
                reviewer_id=USER_A,
            )
