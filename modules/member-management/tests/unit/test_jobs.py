"""Tests for scheduled jobs: benefit year reset, dependent aging-out, retroactive enrollment.

RED tests written before implementation (TDD).
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal


from src.jobs.benefit_year_reset import BenefitYearResetJob
from src.jobs.dependent_aging import DependentAgingJob
from src.jobs.retroactive_enrollment import RetroactiveEnrollmentDetector

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COVERAGE_UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def _seed_member_with_accumulator(
    db,
    *,
    tenant_id=TENANT_ID,
    member_id_str: str = "M001",
    accumulated: Decimal = Decimal("300.00"),
    benefit_year_end: date = date(2025, 12, 31),
    status: str = "active",
):
    from src.models.tables import Accumulator, CoveragePeriod, Member, Group
    grp = Group(id=uuid.uuid4(), tenant_id=tenant_id,
                group_number=f"G{uuid.uuid4().hex[:4]}", group_name="G",
                effective_date=date(2025, 1, 1))
    db.add(grp)
    mbr = Member(id=uuid.uuid4(), tenant_id=tenant_id, member_id=member_id_str,
                 rx_bin="610014", first_name_encrypted="A",
                 last_name_encrypted="B", dob_encrypted="1990-01-01",
                 gender="F", status=status)
    db.add(mbr)
    mbr_id = mbr.id
    cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=tenant_id, member_id=mbr_id,
                         coverage_type="pharmacy", effective_date=date(2025, 1, 1),
                         benefit_year_start=date(2025, 1, 1), benefit_year_end=benefit_year_end)
    db.add(cov)
    acc = Accumulator(id=uuid.uuid4(), tenant_id=tenant_id, member_id=mbr_id,
                      coverage_period_id=cov.id, accumulator_type="individual_deductible",
                      limit_amount=Decimal("500.00"), accumulated_amount=accumulated)
    db.add(acc)
    db.flush()
    return mbr_id, acc.id


# ---------------------------------------------------------------------------
# BenefitYearResetJob
# ---------------------------------------------------------------------------

class TestBenefitYearResetJob:
    def test_reset_job_zeroes_expired_accumulators(self, db_session):
        """Job resets accumulators where benefit_year_end < today."""
        mbr_id, acc_id = _seed_member_with_accumulator(
            db_session, accumulated=Decimal("300.00"),
            benefit_year_end=date(2025, 12, 31),
        )
        job = BenefitYearResetJob()
        results = job.run(
            db=db_session,
            tenant_id=TENANT_ID,
            as_of_date=date(2026, 1, 2),
            carryover_rules={},
        )
        from src.models.tables import Accumulator
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("0.00")
        assert results.reset_count >= 1

    def test_reset_job_writes_ledger_entries(self, db_session):
        """Job writes benefit_year_reset ledger entry for each reset."""
        mbr_id, acc_id = _seed_member_with_accumulator(
            db_session, accumulated=Decimal("200.00"),
            benefit_year_end=date(2025, 12, 31),
        )
        job = BenefitYearResetJob()
        job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 1, 2), carryover_rules={},
        )
        from src.models.tables import AccumulatorLedger
        rows = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).all()
        assert len(rows) == 1
        assert rows[0].transaction_type == "benefit_year_reset"

    def test_reset_job_skips_current_year_accumulators(self, db_session):
        """Accumulators for current benefit year are NOT reset."""
        mbr_id, acc_id = _seed_member_with_accumulator(
            db_session, accumulated=Decimal("300.00"),
            benefit_year_end=date(2026, 12, 31),
        )
        job = BenefitYearResetJob()
        job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 1, 2), carryover_rules={},
        )
        from src.models.tables import Accumulator
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("300.00")  # unchanged

    def test_reset_job_honors_carryover_rules(self, db_session):
        """Carryover rules map accumulator_type → carryover_amount."""
        mbr_id, acc_id = _seed_member_with_accumulator(
            db_session, accumulated=Decimal("300.00"),
            benefit_year_end=date(2025, 12, 31),
        )
        job = BenefitYearResetJob()
        job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 1, 2),
            carryover_rules={"individual_deductible": Decimal("50.00")},
        )
        from src.models.tables import Accumulator
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("50.00")

    def test_reset_job_returns_count(self, db_session):
        _seed_member_with_accumulator(db_session, benefit_year_end=date(2025, 12, 31),
                                       member_id_str="MR01")
        _seed_member_with_accumulator(db_session, benefit_year_end=date(2025, 12, 31),
                                       member_id_str="MR02")
        job = BenefitYearResetJob()
        results = job.run(db=db_session, tenant_id=TENANT_ID,
                          as_of_date=date(2026, 1, 2), carryover_rules={})
        assert results.reset_count == 2


# ---------------------------------------------------------------------------
# DependentAgingJob
# ---------------------------------------------------------------------------

class TestDependentAgingJob:
    def _seed_dependent(self, db, age_years: int, plan_age_limit: int = 26,
                         tenant_id=TENANT_ID):
        from src.models.tables import Member, CoveragePeriod
        from datetime import date as d
        today = date(2026, 4, 13)
        # DOB such that dependent is exactly age_years old
        dob = d(today.year - age_years, today.month, today.day)
        dob_str = dob.isoformat()
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=tenant_id, member_id=f"DEP{uuid.uuid4().hex[:4]}",
                     rx_bin="610014", first_name_encrypted="Child",
                     last_name_encrypted="Doe", dob_encrypted=dob_str,
                     gender="F", status="active", person_code="03")
        db.add(mbr)
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=tenant_id, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2020, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db.add(cov)
        db.flush()
        return mbr_id, dob

    def test_aging_out_dependent_gets_terminated(self, db_session):
        mbr_id, dob = self._seed_dependent(db_session, age_years=26)
        job = DependentAgingJob()
        result = job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 4, 13), age_limit=26,
        )
        from src.models.tables import Member
        mbr = db_session.query(Member).filter_by(id=mbr_id).first()
        assert mbr.status == "terminated"
        assert mbr.termination_reason == "dependent_aged_out"

    def test_young_dependent_not_terminated(self, db_session):
        mbr_id, dob = self._seed_dependent(db_session, age_years=24)
        job = DependentAgingJob()
        job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 4, 13), age_limit=26,
        )
        from src.models.tables import Member
        mbr = db_session.query(Member).filter_by(id=mbr_id).first()
        assert mbr.status == "active"

    def test_run_returns_terminated_count(self, db_session):
        self._seed_dependent(db_session, age_years=26)
        self._seed_dependent(db_session, age_years=24)
        job = DependentAgingJob()
        result = job.run(
            db=db_session, tenant_id=TENANT_ID,
            as_of_date=date(2026, 4, 13), age_limit=26,
        )
        assert result.terminated_count == 1

    def test_decode_dob_returns_none_for_none(self):
        """_decode_dob returns None when given None."""
        job = DependentAgingJob()
        assert job._decode_dob(None) is None

    def test_dependent_with_invalid_dob_skipped(self, db_session):
        """Dependents with invalid DOB are skipped gracefully."""
        from src.models.tables import Member
        mbr_id = uuid.uuid4()
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id=f"DEP{uuid.uuid4().hex[:4]}",
                     rx_bin="610014", first_name_encrypted="Child",
                     last_name_encrypted="Doe", dob_encrypted="not-a-date",
                     gender="F", status="active", person_code="03")
        db_session.add(mbr)
        db_session.flush()
        job = DependentAgingJob()
        result = job.run(db=db_session, tenant_id=TENANT_ID,
                         as_of_date=date(2026, 4, 13), age_limit=26)
        mbr = db_session.query(Member).filter_by(id=mbr_id).first()
        assert mbr.status == "active"

    def test_birthday_not_yet_reached_this_year(self, db_session):
        """If birthday is later this year, age is one less (pre-birthday)."""
        from src.models.tables import Member
        mbr_id = uuid.uuid4()
        # DOB = 2000-12-31: on 2026-04-13, age is 25 (birthday in Dec)
        mbr = Member(id=mbr_id, tenant_id=TENANT_ID, member_id=f"DEP{uuid.uuid4().hex[:4]}",
                     rx_bin="610014", first_name_encrypted="Child",
                     last_name_encrypted="Doe", dob_encrypted="2000-12-31",
                     gender="F", status="active", person_code="03")
        db_session.add(mbr)
        db_session.flush()
        job = DependentAgingJob()
        result = job.run(db=db_session, tenant_id=TENANT_ID,
                         as_of_date=date(2026, 4, 13), age_limit=26)
        mbr = db_session.query(Member).filter_by(id=mbr_id).first()
        assert mbr.status == "active"  # 25, not yet 26


# ---------------------------------------------------------------------------
# RetroactiveEnrollmentDetector
# ---------------------------------------------------------------------------

class TestRetroactiveEnrollmentDetector:
    def test_past_effective_date_flagged_as_retroactive(self):
        detector = RetroactiveEnrollmentDetector(max_retroactive_days=90)
        result = detector.check(
            effective_date=date(2026, 1, 15),
            enrollment_date=date(2026, 4, 13),
        )
        assert result.is_retroactive is True
        assert result.retroactive_days == (date(2026, 4, 13) - date(2026, 1, 15)).days

    def test_future_effective_date_not_retroactive(self):
        detector = RetroactiveEnrollmentDetector(max_retroactive_days=90)
        result = detector.check(
            effective_date=date(2026, 4, 13),
            enrollment_date=date(2026, 4, 13),
        )
        assert result.is_retroactive is False

    def test_retroactive_exceeding_max_still_flagged(self):
        """Even if > max days, is_retroactive=True (caller decides whether to reject)."""
        detector = RetroactiveEnrollmentDetector(max_retroactive_days=90)
        result = detector.check(
            effective_date=date(2025, 12, 1),
            enrollment_date=date(2026, 4, 13),
        )
        assert result.is_retroactive is True
        assert result.exceeds_max is True

    def test_retroactive_within_max_exceeds_is_false(self):
        detector = RetroactiveEnrollmentDetector(max_retroactive_days=90)
        result = detector.check(
            effective_date=date(2026, 1, 15),
            enrollment_date=date(2026, 4, 13),
        )
        assert result.is_retroactive is True
        assert result.exceeds_max is False

    def test_zero_day_retroactive_not_retroactive(self):
        detector = RetroactiveEnrollmentDetector(max_retroactive_days=90)
        result = detector.check(
            effective_date=date(2026, 4, 13),
            enrollment_date=date(2026, 4, 13),
        )
        assert result.is_retroactive is False
        assert result.retroactive_days == 0
