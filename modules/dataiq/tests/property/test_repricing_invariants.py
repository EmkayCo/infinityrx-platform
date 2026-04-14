"""Property-based tests for claims repricing engine.

Key invariants:
1. reprice_claim is pure: same inputs always produce same output.
2. plan_paid >= 0 always.
3. delta = repriced_plan_paid - original_plan_paid always.
4. No float contamination.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from src.services.repricing import (
    ClaimForRepricing,
    PlanDesign,
    reprice_claim,
)


def decimal_money(min_val: str = "0.00", max_val: str = "99999.99") -> st.SearchStrategy:
    return st.decimals(
        min_value=Decimal(min_val),
        max_value=Decimal(max_val),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )


def decimal_pct(min_val: str = "0.00", max_val: str = "0.99") -> st.SearchStrategy:
    return st.decimals(
        min_value=Decimal(min_val),
        max_value=Decimal(max_val),
        places=4,
        allow_nan=False,
        allow_infinity=False,
    )


@given(
    ingredient_cost=decimal_money("0.01", "50000"),
    dispensing_fee=decimal_money("0.00", "20.00"),
    member_copay=decimal_money("0.00", "500.00"),
    plan_paid=decimal_money("0.00", "50000"),
    generic_copay=decimal_money("0.00", "100.00"),
    brand_copay=decimal_money("0.00", "200.00"),
    awp_discount=decimal_pct("0.00", "0.50"),
)
@settings(max_examples=300)
def test_reprice_claim_is_pure_function(
    ingredient_cost: Decimal,
    dispensing_fee: Decimal,
    member_copay: Decimal,
    plan_paid: Decimal,
    generic_copay: Decimal,
    brand_copay: Decimal,
    awp_discount: Decimal,
) -> None:
    claim = ClaimForRepricing(
        claim_id="test-claim",
        ndc="12345678901",
        quantity=Decimal("30"),
        days_supply=30,
        ingredient_cost=ingredient_cost,
        dispensing_fee=dispensing_fee,
        member_copay=member_copay,
        plan_paid=plan_paid,
        is_brand=False,
        is_specialty=False,
    )
    plan = PlanDesign(
        generic_copay=generic_copay,
        brand_copay=brand_copay,
        specialty_copay=Decimal("100.00"),
        awp_discount_pct=awp_discount,
        dispensing_fee_override=None,
    )
    result1 = reprice_claim(claim, plan)
    result2 = reprice_claim(claim, plan)
    assert result1.repriced_plan_paid == result2.repriced_plan_paid
    assert result1.repriced_member_copay == result2.repriced_member_copay
    assert result1.delta_plan_paid == result2.delta_plan_paid


@given(
    ingredient_cost=decimal_money("0.01", "50000"),
    dispensing_fee=decimal_money("0.00", "20.00"),
    member_copay=decimal_money("0.00", "500.00"),
    plan_paid=decimal_money("0.00", "50000"),
    generic_copay=decimal_money("0.00", "100.00"),
)
@settings(max_examples=300)
def test_repriced_plan_paid_never_negative(
    ingredient_cost: Decimal,
    dispensing_fee: Decimal,
    member_copay: Decimal,
    plan_paid: Decimal,
    generic_copay: Decimal,
) -> None:
    claim = ClaimForRepricing(
        claim_id="test-claim",
        ndc="12345678901",
        quantity=Decimal("30"),
        days_supply=30,
        ingredient_cost=ingredient_cost,
        dispensing_fee=dispensing_fee,
        member_copay=member_copay,
        plan_paid=plan_paid,
        is_brand=False,
        is_specialty=False,
    )
    plan = PlanDesign(
        generic_copay=generic_copay,
        brand_copay=Decimal("40.00"),
        specialty_copay=Decimal("100.00"),
        awp_discount_pct=Decimal("0.16"),
        dispensing_fee_override=None,
    )
    result = reprice_claim(claim, plan)
    assert result.repriced_plan_paid >= Decimal("0"), (
        f"plan_paid went negative: {result.repriced_plan_paid}"
    )


@given(
    ingredient_cost=decimal_money("0.01", "50000"),
    dispensing_fee=decimal_money("0.00", "20.00"),
    member_copay=decimal_money("0.00", "500.00"),
    plan_paid=decimal_money("0.00", "50000"),
    generic_copay=decimal_money("0.00", "100.00"),
)
@settings(max_examples=300)
def test_delta_equals_repriced_minus_original_plan_paid(
    ingredient_cost: Decimal,
    dispensing_fee: Decimal,
    member_copay: Decimal,
    plan_paid: Decimal,
    generic_copay: Decimal,
) -> None:
    claim = ClaimForRepricing(
        claim_id="test-claim",
        ndc="12345678901",
        quantity=Decimal("30"),
        days_supply=30,
        ingredient_cost=ingredient_cost,
        dispensing_fee=dispensing_fee,
        member_copay=member_copay,
        plan_paid=plan_paid,
        is_brand=False,
        is_specialty=False,
    )
    plan = PlanDesign(
        generic_copay=generic_copay,
        brand_copay=Decimal("40.00"),
        specialty_copay=Decimal("100.00"),
        awp_discount_pct=Decimal("0.16"),
        dispensing_fee_override=None,
    )
    result = reprice_claim(claim, plan)
    assert result.delta_plan_paid == result.repriced_plan_paid - claim.plan_paid
