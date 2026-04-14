"""RED tests for accumulator math — written BEFORE implementation.

100% branch coverage required on every accumulator calculation path.
All amounts Decimal with ROUND_HALF_UP. Zero floats. Penny-perfect.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from src.services.accumulator import (
    AccumulatorService,
    CopayAssistanceProgramType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(s: str) -> Decimal:
    return Decimal(s)


# ---------------------------------------------------------------------------
# Basic apply / reverse
# ---------------------------------------------------------------------------

class TestApplyClaimToAccumulator:
    def test_apply_increases_accumulated_amount(self):
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("0.00"),
            limit=_dec("500.00"),
            amount=_dec("150.00"),
        )
        assert result.new_accumulated == _dec("150.00")
        assert result.applied == _dec("150.00")
        assert result.overflow == _dec("0.00")

    def test_apply_partial_when_near_limit(self):
        """Accumulator at $490, limit $500, apply $25 → only $10 applied, $15 overflow."""
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("490.00"),
            limit=_dec("500.00"),
            amount=_dec("25.00"),
        )
        assert result.new_accumulated == _dec("500.00")
        assert result.applied == _dec("10.00")
        assert result.overflow == _dec("15.00")

    def test_apply_zero_when_limit_already_met(self):
        """Limit already met — nothing more accumulates."""
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("500.00"),
            limit=_dec("500.00"),
            amount=_dec("50.00"),
        )
        assert result.new_accumulated == _dec("500.00")
        assert result.applied == _dec("0.00")
        assert result.overflow == _dec("50.00")

    def test_apply_exactly_one_cent_below_limit(self):
        """$0.01 below limit — exactly $0.01 applied."""
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("499.99"),
            limit=_dec("500.00"),
            amount=_dec("50.00"),
        )
        assert result.new_accumulated == _dec("500.00")
        assert result.applied == _dec("0.01")
        assert result.overflow == _dec("49.99")

    def test_reverse_decreases_accumulated_amount(self):
        svc = AccumulatorService()
        result = svc.reverse_claim(
            accumulated=_dec("150.00"),
            amount=_dec("150.00"),
        )
        assert result.new_accumulated == _dec("0.00")
        assert result.reversed == _dec("150.00")

    def test_reverse_cannot_go_below_zero(self):
        """Reversing more than accumulated clamps at zero."""
        svc = AccumulatorService()
        result = svc.reverse_claim(
            accumulated=_dec("50.00"),
            amount=_dec("100.00"),
        )
        assert result.new_accumulated == _dec("0.00")
        assert result.reversed == _dec("50.00")

    def test_amounts_are_decimal_not_float(self):
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("0.00"),
            limit=_dec("1000.00"),
            amount=_dec("123.45"),
        )
        assert isinstance(result.new_accumulated, Decimal)
        assert isinstance(result.applied, Decimal)
        assert isinstance(result.overflow, Decimal)

    def test_apply_penny_precision(self):
        """$0.005 should round to $0.01 (ROUND_HALF_UP)."""
        svc = AccumulatorService()
        result = svc.apply_claim(
            accumulated=_dec("0.00"),
            limit=_dec("1000.00"),
            amount=_dec("0.005"),
        )
        assert result.applied == _dec("0.01")

    def test_sum_invariant_applied_plus_overflow_equals_input(self):
        svc = AccumulatorService()
        amount = _dec("73.33")
        result = svc.apply_claim(
            accumulated=_dec("450.00"),
            limit=_dec("500.00"),
            amount=amount,
        )
        # applied + overflow must equal the original amount (penny-perfect)
        assert result.applied + result.overflow == amount


# ---------------------------------------------------------------------------
# Copay assistance — standard vs accumulator vs maximizer
# ---------------------------------------------------------------------------

class TestCopayAssistanceCounting:
    def test_standard_program_counts_full_assistance(self):
        """Standard: all copay assistance counted toward deductible."""
        svc = AccumulatorService()
        result = svc.apply_copay_assistance(
            accumulated=_dec("0.00"),
            limit=_dec("500.00"),
            assistance_amount=_dec("100.00"),
            program_type=CopayAssistanceProgramType.STANDARD,
        )
        assert result.copay_assistance_counted == _dec("100.00")
        assert result.new_accumulated == _dec("100.00")

    def test_accumulator_program_does_not_count_assistance(self):
        """Accumulator: copay assistance applied but NOT counted toward deductible."""
        svc = AccumulatorService()
        result = svc.apply_copay_assistance(
            accumulated=_dec("0.00"),
            limit=_dec("500.00"),
            assistance_amount=_dec("100.00"),
            program_type=CopayAssistanceProgramType.ACCUMULATOR,
        )
        assert result.copay_assistance_counted == _dec("0.00")
        assert result.new_accumulated == _dec("0.00")  # accumulator unchanged

    def test_maximizer_program_counts_assistance_until_limit(self):
        """Maximizer: assistance counted until limit met, then benefit shifts."""
        svc = AccumulatorService()
        result = svc.apply_copay_assistance(
            accumulated=_dec("450.00"),
            limit=_dec("500.00"),
            assistance_amount=_dec("100.00"),
            program_type=CopayAssistanceProgramType.MAXIMIZER,
        )
        # Only $50 can be counted (limit is $500, accumulated is $450)
        assert result.copay_assistance_counted == _dec("50.00")
        assert result.new_accumulated == _dec("500.00")

    def test_applied_tracked_separately_from_counted(self):
        """applied field always reflects total assistance paid, regardless of counting."""
        svc = AccumulatorService()
        result = svc.apply_copay_assistance(
            accumulated=_dec("0.00"),
            limit=_dec("500.00"),
            assistance_amount=_dec("75.00"),
            program_type=CopayAssistanceProgramType.ACCUMULATOR,
        )
        assert result.copay_assistance_applied == _dec("75.00")
        assert result.copay_assistance_counted == _dec("0.00")


# ---------------------------------------------------------------------------
# Part D benefit phase transitions
# ---------------------------------------------------------------------------

class TestPartDPhaseEngine:
    """Part D: deductible → initial_coverage → coverage_gap → catastrophic."""

    def test_deductible_phase_while_troop_below_deductible_threshold(self):
        from src.services.accumulator import (
            PartDPhaseEngine,
            PartDBenefitPhase,
        )
        engine = PartDPhaseEngine(
            deductible_threshold=_dec("590.00"),
            initial_coverage_limit=_dec("5030.00"),
            coverage_gap_limit=_dec("8000.00"),  # TrOOP threshold for catastrophic
        )
        phase = engine.determine_phase(troop=_dec("0.00"), total_drug_cost=_dec("0.00"))
        assert phase == PartDBenefitPhase.DEDUCTIBLE

    def test_transitions_to_initial_coverage_after_deductible_met(self):
        from src.services.accumulator import (
            PartDPhaseEngine,
            PartDBenefitPhase,
        )
        engine = PartDPhaseEngine(
            deductible_threshold=_dec("590.00"),
            initial_coverage_limit=_dec("5030.00"),
            coverage_gap_limit=_dec("8000.00"),
        )
        phase = engine.determine_phase(troop=_dec("590.00"), total_drug_cost=_dec("590.00"))
        assert phase == PartDBenefitPhase.INITIAL_COVERAGE

    def test_transitions_to_coverage_gap(self):
        from src.services.accumulator import (
            PartDPhaseEngine,
            PartDBenefitPhase,
        )
        engine = PartDPhaseEngine(
            deductible_threshold=_dec("590.00"),
            initial_coverage_limit=_dec("5030.00"),
            coverage_gap_limit=_dec("8000.00"),
        )
        phase = engine.determine_phase(troop=_dec("5030.00"), total_drug_cost=_dec("5030.00"))
        assert phase == PartDBenefitPhase.COVERAGE_GAP

    def test_transitions_to_catastrophic(self):
        from src.services.accumulator import (
            PartDPhaseEngine,
            PartDBenefitPhase,
        )
        engine = PartDPhaseEngine(
            deductible_threshold=_dec("590.00"),
            initial_coverage_limit=_dec("5030.00"),
            coverage_gap_limit=_dec("8000.00"),
        )
        phase = engine.determine_phase(troop=_dec("8000.00"), total_drug_cost=_dec("10000.00"))
        assert phase == PartDBenefitPhase.CATASTROPHIC

    def test_phase_at_exact_boundary_deductible_to_initial(self):
        """Exactly at deductible → initial_coverage (not deductible)."""
        from src.services.accumulator import (
            PartDPhaseEngine,
            PartDBenefitPhase,
        )
        engine = PartDPhaseEngine(
            deductible_threshold=_dec("590.00"),
            initial_coverage_limit=_dec("5030.00"),
            coverage_gap_limit=_dec("8000.00"),
        )
        phase = engine.determine_phase(troop=_dec("590.00"), total_drug_cost=_dec("590.00"))
        assert phase == PartDBenefitPhase.INITIAL_COVERAGE


# ---------------------------------------------------------------------------
# Benefit year reset
# ---------------------------------------------------------------------------

class TestBenefitYearReset:
    def test_reset_returns_zero_accumulated(self):
        from src.services.accumulator import (
            AccumulatorService,
        )
        svc = AccumulatorService()
        result = svc.reset_for_benefit_year(accumulated=_dec("450.00"))
        assert result.new_accumulated == _dec("0.00")
        assert result.transaction_type == "benefit_year_reset"

    def test_reset_with_carryover(self):
        """Carryover: some credit carries to next benefit year."""
        from src.services.accumulator import (
            AccumulatorService,
        )
        svc = AccumulatorService()
        result = svc.reset_for_benefit_year(
            accumulated=_dec("450.00"),
            carryover_amount=_dec("50.00"),
        )
        assert result.new_accumulated == _dec("50.00")
        assert result.transaction_type == "benefit_year_reset"

    def test_reset_carryover_capped_at_accumulated(self):
        """Cannot carry over more than what was accumulated."""
        from src.services.accumulator import (
            AccumulatorService,
        )
        svc = AccumulatorService()
        result = svc.reset_for_benefit_year(
            accumulated=_dec("30.00"),
            carryover_amount=_dec("100.00"),
        )
        assert result.new_accumulated == _dec("30.00")


# ---------------------------------------------------------------------------
# LEP calculation (Part D Late Enrollment Penalty)
# ---------------------------------------------------------------------------

class TestLEPCalculation:
    def test_lep_zero_when_no_gap_months(self):
        from src.services.accumulator import calculate_lep
        lep = calculate_lep(
            months_without_coverage=0,
            national_base_premium=_dec("36.78"),
        )
        assert lep == _dec("0.00")

    def test_lep_one_percent_per_month(self):
        """LEP = 1% × base_premium × months, rounded ROUND_HALF_UP."""
        from src.services.accumulator import calculate_lep
        lep = calculate_lep(
            months_without_coverage=12,
            national_base_premium=_dec("36.78"),
        )
        # 0.01 × 36.78 × 12 = 4.4136 → rounds to 4.41
        assert lep == _dec("4.41")

    def test_lep_result_is_decimal(self):
        from src.services.accumulator import calculate_lep
        lep = calculate_lep(
            months_without_coverage=6,
            national_base_premium=_dec("36.78"),
        )
        assert isinstance(lep, Decimal)
