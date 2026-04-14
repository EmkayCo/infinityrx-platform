"""Tests for DB-integrated accumulator service (Session 3).

RED tests written before implementation (TDD).
100% branch coverage required on ALL financial paths.

Anchor test: apply_claim writes a ledger row with running_total = accumulated_amount.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.services.accumulator_db import (
    AccumulatorDbService,
    AccumulatorNotFoundError,
    LedgerInvariantError,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
MEMBER_UUID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
COVERAGE_UUID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ACC_UUID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CLAIM_UUID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


def _make_accumulator(
    *,
    id: uuid.UUID = ACC_UUID,
    tenant_id: uuid.UUID = TENANT_ID,
    member_id: uuid.UUID = MEMBER_UUID,
    coverage_period_id: uuid.UUID = COVERAGE_UUID,
    accumulator_type: str = "individual_deductible",
    limit_amount: Decimal = Decimal("500.00"),
    accumulated_amount: Decimal = Decimal("0.00"),
    benefit_phase: str | None = None,
) -> dict:
    return {
        "id": id,
        "tenant_id": tenant_id,
        "member_id": member_id,
        "coverage_period_id": coverage_period_id,
        "accumulator_type": accumulator_type,
        "limit_amount": limit_amount,
        "accumulated_amount": accumulated_amount,
        "remaining_amount": limit_amount - accumulated_amount,
        "copay_assistance_applied": Decimal("0.00"),
        "copay_assistance_counted": Decimal("0.00"),
        "benefit_phase": benefit_phase,
        "last_updated_claim_id": None,
        "last_updated_at": None,
    }


# ---------------------------------------------------------------------------
# ANCHOR TEST: apply writes ledger row with running_total = accumulated_amount
# ---------------------------------------------------------------------------

class TestApplyClaimWritesLedger:
    def test_apply_claim_ledger_row_created(self, db_session):
        """Anchor: apply_claim writes a ledger row; running_total == new accumulated_amount."""
        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group

        # Seed group → member → coverage → accumulator
        grp = Group(
            id=uuid.uuid4(), tenant_id=TENANT_ID,
            group_number="G001", group_name="Test Group",
            effective_date=date(2026, 1, 1),
        )
        db_session.add(grp)

        mbr = Member(
            id=MEMBER_UUID, tenant_id=TENANT_ID,
            member_id="M001", rx_bin="610014",
            first_name_encrypted="Jane",
            last_name_encrypted="Smith",
            dob_encrypted="1980-01-01",
            gender="F",
        )
        db_session.add(mbr)

        cov = CoveragePeriod(
            id=COVERAGE_UUID, tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            coverage_type="pharmacy",
            effective_date=date(2026, 1, 1),
            benefit_year_start=date(2026, 1, 1),
            benefit_year_end=date(2026, 12, 31),
        )
        db_session.add(cov)

        acc = Accumulator(
            id=ACC_UUID, tenant_id=TENANT_ID,
            member_id=MEMBER_UUID,
            coverage_period_id=COVERAGE_UUID,
            accumulator_type="individual_deductible",
            limit_amount=Decimal("500.00"),
            accumulated_amount=Decimal("100.00"),
        )
        db_session.add(acc)
        db_session.flush()

        svc = AccumulatorDbService()
        result = svc.apply_claim(
            db=db_session,
            tenant_id=TENANT_ID,
            accumulator_id=ACC_UUID,
            amount=Decimal("75.00"),
            claim_id=CLAIM_UUID,
            claim_auth_number="AUTH001",
        )

        # accumulator updated
        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("175.00")

        # ledger row written
        ledger_rows = db_session.query(AccumulatorLedger).filter_by(
            accumulator_id=ACC_UUID
        ).all()
        assert len(ledger_rows) == 1
        row = ledger_rows[0]
        assert row.amount == Decimal("75.00")
        assert row.running_total == Decimal("175.00")
        assert row.running_total == acc.accumulated_amount  # INVARIANT
        assert row.claim_id == CLAIM_UUID
        assert row.transaction_type == "claim_applied"

    def test_apply_claim_at_limit_writes_zero_ledger_row(self, db_session):
        """When accumulator is already at limit, ledger row shows amount=0.00."""
        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="G002",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id="M002",
                     rx_bin="610014", first_name_encrypted="A",
                     last_name_encrypted="B", dob_encrypted="1990-01-01", gender="M")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        cov_id = cov.id
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov_id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("500.00"))
        db_session.add(acc)
        db_session.flush()

        svc = AccumulatorDbService()
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("50.00"), claim_id=uuid.uuid4())

        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row is not None
        assert row.amount == Decimal("0.00")
        assert row.running_total == Decimal("500.00")

    def test_apply_claim_partial_at_boundary(self, db_session):
        """Amount exceeds remaining capacity — only remaining applied, overflow not in ledger."""
        from src.models.tables import Accumulator, AccumulatorLedger, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number="G003",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id="M003", rx_bin="610014",
                     first_name_encrypted="A", last_name_encrypted="B",
                     dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        cov_id = cov.id
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov_id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=Decimal("499.99"))
        db_session.add(acc)
        db_session.flush()

        svc = AccumulatorDbService()
        result = svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                                 amount=Decimal("50.00"), claim_id=uuid.uuid4())

        db_session.refresh(acc)
        assert acc.accumulated_amount == Decimal("500.00")
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row.amount == Decimal("0.01")
        assert row.running_total == Decimal("500.00")

    def test_apply_claim_wrong_tenant_raises(self, db_session):
        """Cannot apply to accumulator owned by a different tenant."""
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group

        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_B, group_number="G004",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_B, member_id="M004", rx_bin="610014",
                     first_name_encrypted="A", last_name_encrypted="B",
                     dob_encrypted="1990-01-01", gender="M")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_B, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        cov_id = cov.id
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_B, member_id=mbr_id,
                          coverage_period_id=cov_id, accumulator_type="individual_oop_max",
                          limit_amount=Decimal("1000.00"), accumulated_amount=Decimal("0.00"))
        db_session.add(acc)
        db_session.flush()

        svc = AccumulatorDbService()
        with pytest.raises(AccumulatorNotFoundError):
            svc.apply_claim(db=db_session, tenant_id=TENANT_ID,
                            accumulator_id=acc_id, amount=Decimal("50.00"))

    def test_apply_claim_nonexistent_accumulator_raises(self, db_session):
        svc = AccumulatorDbService()
        with pytest.raises(AccumulatorNotFoundError):
            svc.apply_claim(db=db_session, tenant_id=TENANT_ID,
                            accumulator_id=uuid.uuid4(), amount=Decimal("50.00"))


# ---------------------------------------------------------------------------
# reverse_claim — writes ledger row of type claim_reversed
# ---------------------------------------------------------------------------

class TestReverseClaimWritesLedger:
    def _seed_accumulator(self, db_session, accumulated: Decimal = Decimal("200.00")) -> uuid.UUID:
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number=f"G{uuid.uuid4().hex[:4]}",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=f"M{uuid.uuid4().hex[:6]}",
                     rx_bin="610014", first_name_encrypted="A", last_name_encrypted="B",
                     dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        cov_id = cov.id
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov_id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=accumulated)
        db_session.add(acc)
        db_session.flush()
        return acc_id

    def test_reverse_claim_reduces_accumulated(self, db_session):
        from src.models.tables import Accumulator, AccumulatorLedger
        acc_id = self._seed_accumulator(db_session, Decimal("200.00"))
        svc = AccumulatorDbService()
        svc.reverse_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                          amount=Decimal("75.00"), claim_id=CLAIM_UUID)
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("125.00")
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row.transaction_type == "claim_reversed"
        assert row.amount == Decimal("-75.00")
        assert row.running_total == Decimal("125.00")

    def test_reverse_claim_clamps_at_zero(self, db_session):
        from src.models.tables import Accumulator, AccumulatorLedger
        acc_id = self._seed_accumulator(db_session, Decimal("30.00"))
        svc = AccumulatorDbService()
        svc.reverse_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                          amount=Decimal("100.00"), claim_id=CLAIM_UUID)
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("0.00")
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row.amount == Decimal("-30.00")
        assert row.running_total == Decimal("0.00")

    def test_reverse_wrong_tenant_raises(self, db_session):
        acc_id = self._seed_accumulator(db_session, Decimal("100.00"))
        svc = AccumulatorDbService()
        with pytest.raises(AccumulatorNotFoundError):
            svc.reverse_claim(db=db_session, tenant_id=TENANT_B,
                              accumulator_id=acc_id, amount=Decimal("50.00"))


# ---------------------------------------------------------------------------
# Ledger invariant: running_total == sum of all prior amounts
# ---------------------------------------------------------------------------

class TestLedgerInvariant:
    def _seed_acc(self, db_session) -> uuid.UUID:
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number=f"GI{uuid.uuid4().hex[:4]}",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=f"MI{uuid.uuid4().hex[:6]}",
                     rx_bin="610014", first_name_encrypted="A", last_name_encrypted="B",
                     dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("1000.00"), accumulated_amount=Decimal("0.00"))
        db_session.add(acc)
        db_session.flush()
        return acc_id

    def test_running_total_equals_cumulative_sum(self, db_session):
        """running_total on final ledger row == sum of all ledger amounts."""
        from src.models.tables import AccumulatorLedger
        acc_id = self._seed_acc(db_session)
        svc = AccumulatorDbService()
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("100.00"), claim_id=uuid.uuid4())
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("50.00"), claim_id=uuid.uuid4())
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("25.00"), claim_id=uuid.uuid4())

        rows = db_session.query(AccumulatorLedger).filter_by(
            accumulator_id=acc_id
        ).order_by(AccumulatorLedger.created_at).all()

        assert len(rows) == 3
        cumulative = Decimal("0.00")
        for row in rows:
            cumulative += row.amount
            assert row.running_total == cumulative, (
                f"running_total {row.running_total} != cumulative {cumulative}"
            )

    def test_verify_ledger_invariant_passes_for_valid_ledger(self, db_session):
        acc_id = self._seed_acc(db_session)
        svc = AccumulatorDbService()
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("200.00"), claim_id=uuid.uuid4())
        svc.verify_ledger_invariant(db=db_session, accumulator_id=acc_id)  # should not raise

    def test_verify_ledger_invariant_raises_on_corruption(self, db_session):
        from src.models.tables import AccumulatorLedger
        acc_id = self._seed_acc(db_session)
        svc = AccumulatorDbService()
        svc.apply_claim(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                        amount=Decimal("200.00"), claim_id=uuid.uuid4())
        # Corrupt running_total directly
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        row.running_total = Decimal("999.00")
        db_session.flush()
        with pytest.raises(LedgerInvariantError):
            svc.verify_ledger_invariant(db=db_session, accumulator_id=acc_id)


# ---------------------------------------------------------------------------
# reset_for_benefit_year — writes benefit_year_reset ledger rows
# ---------------------------------------------------------------------------

class TestBenefitYearReset:
    def _seed_acc(self, db_session, accumulated: Decimal = Decimal("300.00")) -> uuid.UUID:
        from src.models.tables import Accumulator, CoveragePeriod, Member, Group
        grp = Group(id=uuid.uuid4(), tenant_id=TENANT_ID, group_number=f"GR{uuid.uuid4().hex[:4]}",
                    group_name="G", effective_date=date(2026, 1, 1))
        db_session.add(grp)
        mbr = Member(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=f"MR{uuid.uuid4().hex[:6]}",
                     rx_bin="610014", first_name_encrypted="A", last_name_encrypted="B",
                     dob_encrypted="1990-01-01", gender="F")
        db_session.add(mbr)
        mbr_id = mbr.id
        cov = CoveragePeriod(id=uuid.uuid4(), tenant_id=TENANT_ID, member_id=mbr_id,
                             coverage_type="pharmacy", effective_date=date(2026, 1, 1),
                             benefit_year_start=date(2026, 1, 1), benefit_year_end=date(2026, 12, 31))
        db_session.add(cov)
        acc_id = uuid.uuid4()
        acc = Accumulator(id=acc_id, tenant_id=TENANT_ID, member_id=mbr_id,
                          coverage_period_id=cov.id, accumulator_type="individual_deductible",
                          limit_amount=Decimal("500.00"), accumulated_amount=accumulated)
        db_session.add(acc)
        db_session.flush()
        return acc_id

    def test_reset_zeroes_accumulated(self, db_session):
        from src.models.tables import Accumulator, AccumulatorLedger
        acc_id = self._seed_acc(db_session, Decimal("300.00"))
        svc = AccumulatorDbService()
        svc.reset_benefit_year(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                               carryover_amount=Decimal("0.00"))
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("0.00")
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row.transaction_type == "benefit_year_reset"
        assert row.amount == Decimal("-300.00")
        assert row.running_total == Decimal("0.00")

    def test_reset_with_carryover_retains_carryover_amount(self, db_session):
        from src.models.tables import Accumulator
        acc_id = self._seed_acc(db_session, Decimal("300.00"))
        svc = AccumulatorDbService()
        svc.reset_benefit_year(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                               carryover_amount=Decimal("50.00"))
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("50.00")

    def test_reset_carryover_capped_at_accumulated(self, db_session):
        """Cannot carry over more than was accumulated."""
        from src.models.tables import Accumulator
        acc_id = self._seed_acc(db_session, Decimal("30.00"))
        svc = AccumulatorDbService()
        svc.reset_benefit_year(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                               carryover_amount=Decimal("100.00"))
        acc = db_session.query(Accumulator).filter_by(id=acc_id).first()
        assert acc.accumulated_amount == Decimal("30.00")

    def test_reset_zero_accumulated_writes_zero_amount_ledger(self, db_session):
        from src.models.tables import AccumulatorLedger
        acc_id = self._seed_acc(db_session, Decimal("0.00"))
        svc = AccumulatorDbService()
        svc.reset_benefit_year(db=db_session, tenant_id=TENANT_ID, accumulator_id=acc_id,
                               carryover_amount=Decimal("0.00"))
        row = db_session.query(AccumulatorLedger).filter_by(accumulator_id=acc_id).first()
        assert row.amount == Decimal("0.00")
        assert row.running_total == Decimal("0.00")

    def test_reset_wrong_tenant_raises(self, db_session):
        acc_id = self._seed_acc(db_session, Decimal("100.00"))
        svc = AccumulatorDbService()
        with pytest.raises(AccumulatorNotFoundError):
            svc.reset_benefit_year(db=db_session, tenant_id=TENANT_B,
                                   accumulator_id=acc_id, carryover_amount=Decimal("0.00"))
