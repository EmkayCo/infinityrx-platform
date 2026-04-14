"""Tests for member merge workflow (Session 3).

RED tests written before implementation (TDD).
Cross-tenant isolation: merge must never touch another tenant's rows.
100% coverage on all merge paths.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.merge_service import (
    MergeConflictError,
    MergeService,
    MergeServiceError,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
SURVIVING_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
DUPLICATE_UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
COVERAGE_UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _add_member(db, id, tenant_id, member_id, status="active"):
    from src.models.tables import Member
    m = Member(
        id=id, tenant_id=tenant_id, member_id=member_id,
        rx_bin="610014", first_name_encrypted="Jane",
        last_name_encrypted="Smith", dob_encrypted="1980-01-01",
        gender="F", status=status,
    )
    db.add(m)
    return m


def _add_coverage(db, member_id, tenant_id):
    from src.models.tables import CoveragePeriod
    c = CoveragePeriod(
        id=uuid.uuid4(), tenant_id=tenant_id, member_id=member_id,
        coverage_type="pharmacy", effective_date=date(2026, 1, 1),
        benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31),
    )
    db.add(c)
    return c


def _add_accumulator(db, member_id, coverage_id, tenant_id, amount=Decimal("100.00")):
    from src.models.tables import Accumulator
    a = Accumulator(
        id=uuid.uuid4(), tenant_id=tenant_id, member_id=member_id,
        coverage_period_id=coverage_id,
        accumulator_type="individual_deductible",
        limit_amount=Decimal("500.00"), accumulated_amount=amount,
    )
    db.add(a)
    return a


def _add_cob(db, member_id, tenant_id):
    from src.models.tables import CobRecord
    c = CobRecord(
        id=uuid.uuid4(), tenant_id=tenant_id, member_id=member_id,
        payer_sequence="secondary", other_payer_name="BlueCross",
        effective_date=date(2026, 1, 1),
    )
    db.add(c)
    return c


# ---------------------------------------------------------------------------
# Basic merge flow
# ---------------------------------------------------------------------------

class TestMergeService:
    def test_merge_marks_duplicate_as_merged(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session,
            tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID,
            duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import Member
        dup = db_session.query(Member).filter_by(id=DUPLICATE_UUID).first()
        assert dup.status == "merged"
        assert dup.merged_into_id == SURVIVING_UUID

    def test_merge_transfers_coverage_periods(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        dup = _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        cov = _add_coverage(db_session, DUPLICATE_UUID, TENANT_ID)
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session, tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import CoveragePeriod
        db_session.refresh(cov)
        assert cov.member_id == SURVIVING_UUID

    def test_merge_transfers_accumulators(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        cov = _add_coverage(db_session, DUPLICATE_UUID, TENANT_ID)
        acc = _add_accumulator(db_session, DUPLICATE_UUID, cov.id, TENANT_ID)
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session, tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import Accumulator
        db_session.refresh(acc)
        assert acc.member_id == SURVIVING_UUID

    def test_merge_transfers_cob_records(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        cob = _add_cob(db_session, DUPLICATE_UUID, TENANT_ID)
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session, tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import CobRecord
        db_session.refresh(cob)
        assert cob.member_id == SURVIVING_UUID

    def test_merge_surviving_member_unchanged(self, db_session):
        surviving = _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session, tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import Member
        db_session.refresh(surviving)
        assert surviving.status == "active"
        assert surviving.member_id == "M001"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestMergeServiceErrors:
    def test_cannot_merge_member_with_itself(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        db_session.flush()

        svc = MergeService()
        with pytest.raises(MergeServiceError, match="same"):
            svc.merge(
                db=db_session, tenant_id=TENANT_ID,
                surviving_id=SURVIVING_UUID, duplicate_id=SURVIVING_UUID,
                operator_id=uuid.uuid4(),
            )

    def test_surviving_not_found_raises(self, db_session):
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")
        db_session.flush()

        svc = MergeService()
        with pytest.raises(MergeServiceError, match="not found"):
            svc.merge(
                db=db_session, tenant_id=TENANT_ID,
                surviving_id=uuid.uuid4(), duplicate_id=DUPLICATE_UUID,
                operator_id=uuid.uuid4(),
            )

    def test_duplicate_not_found_raises(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        db_session.flush()

        svc = MergeService()
        with pytest.raises(MergeServiceError, match="not found"):
            svc.merge(
                db=db_session, tenant_id=TENANT_ID,
                surviving_id=SURVIVING_UUID, duplicate_id=uuid.uuid4(),
                operator_id=uuid.uuid4(),
            )

    def test_cannot_merge_already_merged_member(self, db_session):
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002", status="merged")
        db_session.flush()

        svc = MergeService()
        with pytest.raises(MergeServiceError, match="already merged"):
            svc.merge(
                db=db_session, tenant_id=TENANT_ID,
                surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
                operator_id=uuid.uuid4(),
            )


# ---------------------------------------------------------------------------
# Cross-tenant isolation — CRITICAL
# ---------------------------------------------------------------------------

class TestMergeCrossTenantIsolation:
    def test_cannot_merge_members_from_different_tenants(self, db_session):
        """Tenant A member cannot be used as surviving/duplicate for Tenant B member."""
        tenant_a_id = uuid.uuid4()
        tenant_b_id = uuid.uuid4()
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        other_id = uuid.uuid4()
        _add_member(db_session, other_id, TENANT_B, "M999")
        db_session.flush()

        svc = MergeService()
        with pytest.raises(MergeServiceError):
            svc.merge(
                db=db_session, tenant_id=TENANT_ID,
                surviving_id=SURVIVING_UUID, duplicate_id=other_id,
                operator_id=uuid.uuid4(),
            )

    def test_merge_does_not_touch_other_tenant_rows(self, db_session):
        """After merge, Tenant B rows are completely untouched."""
        # Tenant A members
        _add_member(db_session, SURVIVING_UUID, TENANT_ID, "M001")
        _add_member(db_session, DUPLICATE_UUID, TENANT_ID, "M002")

        # Tenant B unrelated member with coverage
        tenant_b_mbr_id = uuid.uuid4()
        _add_member(db_session, tenant_b_mbr_id, TENANT_B, "MB001")
        cov_b = _add_coverage(db_session, tenant_b_mbr_id, TENANT_B)
        db_session.flush()

        svc = MergeService()
        svc.merge(
            db=db_session, tenant_id=TENANT_ID,
            surviving_id=SURVIVING_UUID, duplicate_id=DUPLICATE_UUID,
            operator_id=uuid.uuid4(),
        )

        from src.models.tables import CoveragePeriod
        db_session.refresh(cov_b)
        assert cov_b.member_id == tenant_b_mbr_id  # unchanged


# ---------------------------------------------------------------------------
# Member model needs merged_into_id field — test it exists
# ---------------------------------------------------------------------------

class TestMemberMergedIntoField:
    def test_member_has_merged_into_id_field(self, db_session):
        from src.models.tables import Member
        m = Member(
            id=uuid.uuid4(), tenant_id=TENANT_ID, member_id="M_CHECK",
            rx_bin="610014", first_name_encrypted="A",
            last_name_encrypted="B", dob_encrypted="1990-01-01",
            gender="F",
        )
        db_session.add(m)
        db_session.flush()
        assert hasattr(m, "merged_into_id")
