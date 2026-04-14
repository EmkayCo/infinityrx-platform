"""Claims repricing engine.

Pure function: reprice_claim(claim, plan_design) -> RepricedClaim.
No DB writes; no side effects. Same inputs always produce same output.

All money uses Decimal + ROUND_HALF_UP. No float anywhere.

Repricing logic:
  1. Apply AWP discount to get repriced ingredient cost.
  2. Apply dispensing fee (override if present, else original).
  3. Determine member copay based on drug tier (specialty > brand > generic).
  4. Plan paid = total_cost - member_copay, clamped to >= 0.
  5. Delta = repriced_plan_paid - original_plan_paid.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class ClaimForRepricing:
    claim_id: str
    ndc: str
    quantity: Decimal
    days_supply: int
    ingredient_cost: Decimal
    dispensing_fee: Decimal
    member_copay: Decimal
    plan_paid: Decimal
    is_brand: bool
    is_specialty: bool


@dataclass(frozen=True)
class PlanDesign:
    generic_copay: Decimal
    brand_copay: Decimal
    specialty_copay: Decimal
    awp_discount_pct: Decimal
    dispensing_fee_override: Decimal | None


@dataclass(frozen=True)
class RepricedClaim:
    claim_id: str
    repriced_ingredient_cost: Decimal
    repriced_dispensing_fee: Decimal
    repriced_member_copay: Decimal
    repriced_plan_paid: Decimal
    delta_plan_paid: Decimal


def reprice_claim(claim: ClaimForRepricing, plan: PlanDesign) -> RepricedClaim:
    """Apply plan design to a claim and compute the repriced cost.

    Pure function: no I/O, no side effects.
    """
    two_places = Decimal("0.01")

    # Apply AWP discount to ingredient cost
    discount_factor = Decimal("1") - plan.awp_discount_pct
    repriced_ingredient_cost = (claim.ingredient_cost * discount_factor).quantize(
        two_places, rounding=ROUND_HALF_UP
    )

    # Dispensing fee: use override if present
    repriced_dispensing_fee = (
        plan.dispensing_fee_override
        if plan.dispensing_fee_override is not None
        else claim.dispensing_fee
    ).quantize(two_places, rounding=ROUND_HALF_UP)

    total_repriced_cost = repriced_ingredient_cost + repriced_dispensing_fee

    # Member copay based on drug tier
    if claim.is_specialty:
        repriced_member_copay = plan.specialty_copay
    elif claim.is_brand:
        repriced_member_copay = plan.brand_copay
    else:
        repriced_member_copay = plan.generic_copay

    repriced_member_copay = repriced_member_copay.quantize(two_places, rounding=ROUND_HALF_UP)

    # Plan paid = total cost - member copay, never negative
    raw_plan_paid = total_repriced_cost - repriced_member_copay
    repriced_plan_paid = max(raw_plan_paid, Decimal("0.00")).quantize(
        two_places, rounding=ROUND_HALF_UP
    )

    delta_plan_paid = repriced_plan_paid - claim.plan_paid

    return RepricedClaim(
        claim_id=claim.claim_id,
        repriced_ingredient_cost=repriced_ingredient_cost,
        repriced_dispensing_fee=repriced_dispensing_fee,
        repriced_member_copay=repriced_member_copay,
        repriced_plan_paid=repriced_plan_paid,
        delta_plan_paid=delta_plan_paid,
    )
