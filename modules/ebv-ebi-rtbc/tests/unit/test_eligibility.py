"""Tests for eligibility verification service.

Covers: active/inactive/terminated members, benefit phase detection,
deductible/OOP progress calculation (Decimal precision), coverage date
boundaries, future effective dates.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from unittest.mock import AsyncMock

import pytest

from src.services.eligibility import (
    AccumulatorProgress,
    BenefitPhase,
    CopayTier,
    EligibilityResult,
    EligibilityService,
    EligibilityStatus,
    MemberDataProvider,
    MemberRecord,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _make_member(
    *,
    status: str = "active",
    coverage_start: date | None = date(2026, 1, 1),
    coverage_end: date | None = date(2026, 12, 31),
    deductible_limit: Decimal = Decimal("500.00"),
    deductible_met: Decimal = Decimal("200.00"),
    oop_limit: Decimal = Decimal("5000.00"),
    oop_met: Decimal = Decimal("1200.00"),
    copay_tiers: list | None = None,
    plan_id: uuid.UUID | None = None,
    group_id: uuid.UUID | None = None,
) -> MemberRecord:
    return MemberRecord(
        member_id="M123456",
        status=status,
        plan_id=plan_id or uuid.uuid4(),
        plan_name="Basic Rx Plan",
        group_id=group_id or uuid.uuid4(),
        group_name="Acme Corp",
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        copay_tiers=copay_tiers or [{"tier": "1", "copay": "10.00"}],
        deductible_limit=deductible_limit,
        deductible_met=deductible_met,
        oop_limit=oop_limit,
        oop_met=oop_met,
    )


def _mock_provider(member: MemberRecord | None = None) -> MemberDataProvider:
    provider = MemberDataProvider()
    provider.get_member = AsyncMock(return_value=member)
    provider.get_members = AsyncMock(return_value=[member] if member else [])
    return provider


# ---------------------------------------------------------------------------
# Active member returns correct details
# ---------------------------------------------------------------------------


class TestActiveEligibility:
    @pytest.mark.asyncio
    async def test_active_member_returns_active_status(self):
        member = _make_member()
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.ACTIVE
        assert result.member_id == "M123456"
        assert result.plan_name == "Basic Rx Plan"
        assert result.group_name == "Acme Corp"
        assert result.coverage_start == date(2026, 1, 1)
        assert result.coverage_end == date(2026, 12, 31)

    @pytest.mark.asyncio
    async def test_active_member_has_copay_summary(self):
        member = _make_member(copay_tiers=[
            {"tier": "1", "copay": "10.00"},
            {"tier": "2", "copay": "35.00"},
        ])
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert len(result.copay_summary) == 2
        assert result.copay_summary[0].copay == Decimal("10.00")
        assert result.copay_summary[1].copay == Decimal("35.00")

    @pytest.mark.asyncio
    async def test_response_time_is_populated(self):
        member = _make_member()
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456")

        assert result.response_time_ms >= 0


# ---------------------------------------------------------------------------
# Inactive / terminated member returns inactive
# ---------------------------------------------------------------------------


class TestInactiveEligibility:
    @pytest.mark.asyncio
    async def test_member_not_found_returns_inactive(self):
        svc = EligibilityService(data_provider=_mock_provider(None))
        result = await svc.verify_eligibility(TENANT_ID, "MISSING")

        assert result.status == EligibilityStatus.INACTIVE
        assert result.member_id == "MISSING"

    @pytest.mark.asyncio
    async def test_terminated_member_returns_terminated(self):
        member = _make_member(status="terminated")
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.TERMINATED

    @pytest.mark.asyncio
    async def test_inactive_status_member(self):
        member = _make_member(status="suspended")
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_past_coverage_end_returns_inactive(self):
        member = _make_member(coverage_end=date(2026, 3, 31))
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.INACTIVE


# ---------------------------------------------------------------------------
# Benefit phase detection
# ---------------------------------------------------------------------------


class TestBenefitPhaseDetection:
    @pytest.mark.asyncio
    async def test_deductible_phase_when_deductible_not_met(self):
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("100.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase == BenefitPhase.DEDUCTIBLE

    @pytest.mark.asyncio
    async def test_initial_coverage_when_deductible_met(self):
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("500.00"),
            oop_limit=Decimal("5000.00"),
            oop_met=Decimal("1000.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase == BenefitPhase.INITIAL_COVERAGE

    @pytest.mark.asyncio
    async def test_catastrophic_phase_when_oop_met(self):
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("500.00"),
            oop_limit=Decimal("5000.00"),
            oop_met=Decimal("5000.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase == BenefitPhase.CATASTROPHIC

    @pytest.mark.asyncio
    async def test_coverage_gap_when_oop_above_threshold(self):
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("500.00"),
            oop_limit=Decimal("5000.00"),
            oop_met=Decimal("3800.00"),  # 76% > 75% threshold
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase == BenefitPhase.COVERAGE_GAP

    @pytest.mark.asyncio
    async def test_no_benefit_phase_for_inactive_member(self):
        member = _make_member(status="terminated")
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase is None

    @pytest.mark.asyncio
    async def test_initial_coverage_with_zero_deductible(self):
        """Plans with no deductible go straight to initial coverage."""
        member = _make_member(
            deductible_limit=Decimal("0.00"),
            deductible_met=Decimal("0.00"),
            oop_limit=Decimal("3000.00"),
            oop_met=Decimal("500.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase == BenefitPhase.INITIAL_COVERAGE


# ---------------------------------------------------------------------------
# Deductible / OOP progress calculation (Decimal precision)
# ---------------------------------------------------------------------------


class TestAccumulatorProgress:
    @pytest.mark.asyncio
    async def test_deductible_progress_values(self):
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("200.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.deductible is not None
        assert result.deductible.limit == Decimal("500.00")
        assert result.deductible.met == Decimal("200.00")
        assert result.deductible.remaining == Decimal("300.00")
        assert result.deductible.pct_met == Decimal("40.00")

    @pytest.mark.asyncio
    async def test_oop_progress_values(self):
        member = _make_member(
            oop_limit=Decimal("5000.00"),
            oop_met=Decimal("1200.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.oop is not None
        assert result.oop.limit == Decimal("5000.00")
        assert result.oop.met == Decimal("1200.00")
        assert result.oop.remaining == Decimal("3800.00")
        assert result.oop.pct_met == Decimal("24.00")

    @pytest.mark.asyncio
    async def test_all_progress_values_are_decimal(self):
        member = _make_member()
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        if result.deductible:
            assert isinstance(result.deductible.limit, Decimal)
            assert isinstance(result.deductible.met, Decimal)
            assert isinstance(result.deductible.remaining, Decimal)
            assert isinstance(result.deductible.pct_met, Decimal)

        if result.oop:
            assert isinstance(result.oop.limit, Decimal)
            assert isinstance(result.oop.met, Decimal)
            assert isinstance(result.oop.remaining, Decimal)
            assert isinstance(result.oop.pct_met, Decimal)

    @pytest.mark.asyncio
    async def test_no_accumulator_when_limit_zero(self):
        member = _make_member(
            deductible_limit=Decimal("0.00"),
            deductible_met=Decimal("0.00"),
            oop_limit=Decimal("0.00"),
            oop_met=Decimal("0.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.deductible is None
        assert result.oop is None

    @pytest.mark.asyncio
    async def test_pct_caps_at_100(self):
        """If met > limit (overshoot), pct is capped at 100."""
        member = _make_member(
            deductible_limit=Decimal("500.00"),
            deductible_met=Decimal("600.00"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.deductible is not None
        assert result.deductible.pct_met == Decimal("100.00")
        assert result.deductible.remaining == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_precise_decimal_rounding(self):
        """Test that accumulator math uses ROUND_HALF_UP."""
        member = _make_member(
            deductible_limit=Decimal("333.33"),
            deductible_met=Decimal("111.11"),
        )
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.deductible is not None
        assert result.deductible.remaining == Decimal("222.22")
        # 111.11 / 333.33 * 100 = 33.333...% -> rounds to 33.33
        assert result.deductible.pct_met == Decimal("33.33")


# ---------------------------------------------------------------------------
# Coverage date boundary (effective date = today)
# ---------------------------------------------------------------------------


class TestCoverageDateBoundary:
    @pytest.mark.asyncio
    async def test_effective_date_equals_today_is_active(self):
        """Member whose coverage starts today is active."""
        today = date(2026, 4, 15)
        member = _make_member(coverage_start=today)
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=today)

        assert result.status == EligibilityStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_coverage_end_equals_today_is_active(self):
        """Member whose coverage ends today is still active (inclusive)."""
        today = date(2026, 4, 15)
        member = _make_member(coverage_end=today)
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=today)

        assert result.status == EligibilityStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_day_after_coverage_end_is_inactive(self):
        member = _make_member(coverage_end=date(2026, 4, 14))
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.INACTIVE


# ---------------------------------------------------------------------------
# Future effective date member not yet active
# ---------------------------------------------------------------------------


class TestFutureEffectiveDate:
    @pytest.mark.asyncio
    async def test_future_effective_date_returns_future_status(self):
        member = _make_member(coverage_start=date(2026, 5, 1))
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.status == EligibilityStatus.FUTURE_EFFECTIVE

    @pytest.mark.asyncio
    async def test_future_effective_no_benefit_phase(self):
        member = _make_member(coverage_start=date(2026, 5, 1))
        svc = EligibilityService(data_provider=_mock_provider(member))
        result = await svc.verify_eligibility(TENANT_ID, "M123456", as_of_date=date(2026, 4, 15))

        assert result.benefit_phase is None


# ---------------------------------------------------------------------------
# Batch verify
# ---------------------------------------------------------------------------


class TestBatchVerify:
    @pytest.mark.asyncio
    async def test_batch_returns_results_for_all_members(self):
        m1 = _make_member()
        m2 = MemberRecord(
            member_id="M999999",
            status="active",
            coverage_start=date(2026, 1, 1),
            coverage_end=date(2026, 12, 31),
            deductible_limit=Decimal("0"),
            deductible_met=Decimal("0"),
            oop_limit=Decimal("0"),
            oop_met=Decimal("0"),
        )
        provider = MemberDataProvider()
        provider.get_members = AsyncMock(return_value=[m1, m2])

        svc = EligibilityService(data_provider=provider)
        results = await svc.batch_verify(
            TENANT_ID,
            ["M123456", "M999999", "MISSING"],
            as_of_date=date(2026, 4, 15),
        )

        assert len(results) == 3
        assert results[0].status == EligibilityStatus.ACTIVE
        assert results[1].status == EligibilityStatus.ACTIVE
        assert results[2].status == EligibilityStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_batch_missing_member_is_inactive(self):
        provider = MemberDataProvider()
        provider.get_members = AsyncMock(return_value=[])

        svc = EligibilityService(data_provider=provider)
        results = await svc.batch_verify(TENANT_ID, ["MISSING"], as_of_date=date(2026, 4, 15))

        assert len(results) == 1
        assert results[0].status == EligibilityStatus.INACTIVE
