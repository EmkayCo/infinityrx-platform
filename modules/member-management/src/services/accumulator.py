"""Accumulator calculation service.

All arithmetic uses Decimal with ROUND_HALF_UP. Zero floats anywhere.
100% branch coverage required on every calculation path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from shared.utils.money import TWO_PLACES, ZERO, money


class CopayAssistanceProgramType(str, Enum):
    STANDARD = "standard"
    ACCUMULATOR = "accumulator"
    MAXIMIZER = "maximizer"


class PartDBenefitPhase(str, Enum):
    DEDUCTIBLE = "deductible"
    INITIAL_COVERAGE = "initial_coverage"
    COVERAGE_GAP = "coverage_gap"
    CATASTROPHIC = "catastrophic"


@dataclass(frozen=True)
class ApplyResult:
    new_accumulated: Decimal
    applied: Decimal
    overflow: Decimal


@dataclass(frozen=True)
class ReverseResult:
    new_accumulated: Decimal
    reversed: Decimal


@dataclass(frozen=True)
class CopayAssistanceResult:
    new_accumulated: Decimal
    copay_assistance_applied: Decimal
    copay_assistance_counted: Decimal


@dataclass(frozen=True)
class ResetResult:
    new_accumulated: Decimal
    transaction_type: str


class AccumulatorService:
    """Stateless service — all inputs/outputs are Decimal."""

    def apply_claim(
        self,
        accumulated: Decimal,
        limit: Decimal,
        amount: Decimal,
    ) -> ApplyResult:
        """Apply *amount* toward accumulator, respecting *limit*.

        Returns how much was applied (≤ amount) and overflow (amount - applied).
        Rounds input amount to TWO_PLACES (ROUND_HALF_UP) before arithmetic.
        """
        amount = amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        remaining_capacity = (limit - accumulated).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if remaining_capacity <= ZERO:
            return ApplyResult(
                new_accumulated=accumulated,
                applied=ZERO,
                overflow=amount,
            )
        applied = min(amount, remaining_capacity).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        overflow = (amount - applied).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        new_accumulated = (accumulated + applied).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return ApplyResult(new_accumulated=new_accumulated, applied=applied, overflow=overflow)

    def reverse_claim(
        self,
        accumulated: Decimal,
        amount: Decimal,
    ) -> ReverseResult:
        """Reverse *amount* from accumulator. Clamps at zero."""
        amount = amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        reversed_amt = min(accumulated, amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        new_accumulated = (accumulated - reversed_amt).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        return ReverseResult(new_accumulated=new_accumulated, reversed=reversed_amt)

    def apply_copay_assistance(
        self,
        accumulated: Decimal,
        limit: Decimal,
        assistance_amount: Decimal,
        program_type: CopayAssistanceProgramType,
    ) -> CopayAssistanceResult:
        """Apply copay assistance and determine how much counts toward accumulator."""
        assistance_amount = assistance_amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

        if program_type == CopayAssistanceProgramType.ACCUMULATOR:
            # Assistance paid but does NOT count toward deductible/OOP
            return CopayAssistanceResult(
                new_accumulated=accumulated,
                copay_assistance_applied=assistance_amount,
                copay_assistance_counted=ZERO,
            )

        if program_type == CopayAssistanceProgramType.STANDARD:
            # Full assistance counts
            apply_result = self.apply_claim(accumulated, limit, assistance_amount)
            return CopayAssistanceResult(
                new_accumulated=apply_result.new_accumulated,
                copay_assistance_applied=assistance_amount,
                copay_assistance_counted=apply_result.applied,
            )

        # MAXIMIZER: counts until limit met
        apply_result = self.apply_claim(accumulated, limit, assistance_amount)
        return CopayAssistanceResult(
            new_accumulated=apply_result.new_accumulated,
            copay_assistance_applied=assistance_amount,
            copay_assistance_counted=apply_result.applied,
        )

    def reset_for_benefit_year(
        self,
        accumulated: Decimal,
        carryover_amount: Decimal = ZERO,
    ) -> ResetResult:
        """Reset accumulator at benefit year boundary.

        Carryover is capped at *accumulated* — cannot carry more than was earned.
        """
        carryover_amount = carryover_amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        effective_carryover = min(accumulated, carryover_amount).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        return ResetResult(
            new_accumulated=effective_carryover,
            transaction_type="benefit_year_reset",
        )


class PartDPhaseEngine:
    """Determines current Part D benefit phase from TrOOP and total drug cost."""

    def __init__(
        self,
        deductible_threshold: Decimal,
        initial_coverage_limit: Decimal,
        coverage_gap_limit: Decimal,
    ) -> None:
        self._deductible = deductible_threshold
        self._initial_coverage = initial_coverage_limit
        self._coverage_gap = coverage_gap_limit

    def determine_phase(
        self,
        troop: Decimal,
        total_drug_cost: Decimal,
    ) -> PartDBenefitPhase:
        """Return the current benefit phase based on TrOOP accumulation."""
        troop = troop.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if troop >= self._coverage_gap:
            return PartDBenefitPhase.CATASTROPHIC
        if troop >= self._initial_coverage:
            return PartDBenefitPhase.COVERAGE_GAP
        if troop >= self._deductible:
            return PartDBenefitPhase.INITIAL_COVERAGE
        return PartDBenefitPhase.DEDUCTIBLE


def calculate_lep(
    months_without_coverage: int,
    national_base_premium: Decimal,
) -> Decimal:
    """Calculate Part D Late Enrollment Penalty.

    LEP = 1% × national_base_premium × months_without_coverage
    Rounded ROUND_HALF_UP to 2 decimal places.
    """
    if months_without_coverage <= 0:
        return ZERO
    rate = Decimal("0.01")
    lep = rate * national_base_premium * Decimal(str(months_without_coverage))
    return lep.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
