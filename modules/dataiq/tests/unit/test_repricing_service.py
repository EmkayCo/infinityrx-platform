"""Unit tests for claims repricing engine.

TDD: tests written before implementation.
reprice_claim is a pure function — same inputs always produce same outputs.
All money uses Decimal + ROUND_HALF_UP.
"""

from __future__ import annotations

from decimal import Decimal

from src.services.repricing import (
    ClaimForRepricing,
    PlanDesign,
    RepricedClaim,
    reprice_claim,
)


class TestRepriceClaim:
    def test_basic_repricing_returns_repriced_claim(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=Decimal("2.50"),
        )
        result = reprice_claim(claim, plan)
        assert isinstance(result, RepricedClaim)
        assert isinstance(result.repriced_plan_paid, Decimal)
        assert isinstance(result.repriced_member_copay, Decimal)

    def test_pure_function_same_inputs_same_outputs(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=Decimal("2.50"),
        )
        result1 = reprice_claim(claim, plan)
        result2 = reprice_claim(claim, plan)
        assert result1.repriced_plan_paid == result2.repriced_plan_paid
        assert result1.repriced_member_copay == result2.repriced_member_copay
        assert result1.delta_plan_paid == result2.delta_plan_paid

    def test_generic_uses_generic_copay(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert result.repriced_member_copay == Decimal("15.00")

    def test_brand_uses_brand_copay(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("200.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("30.00"),
            plan_paid=Decimal("172.00"),
            is_brand=True,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("45.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert result.repriced_member_copay == Decimal("45.00")

    def test_specialty_uses_specialty_copay(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("1"),
            days_supply=30,
            ingredient_cost=Decimal("5000.00"),
            dispensing_fee=Decimal("5.00"),
            member_copay=Decimal("100.00"),
            plan_paid=Decimal("4905.00"),
            is_brand=True,
            is_specialty=True,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("45.00"),
            specialty_copay=Decimal("150.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert result.repriced_member_copay == Decimal("150.00")

    def test_delta_is_repriced_minus_original(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert result.delta_plan_paid == result.repriced_plan_paid - claim.plan_paid

    def test_dispensing_fee_override_applied(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan_with_override = PlanDesign(
            generic_copay=Decimal("10.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=Decimal("3.00"),
        )
        plan_without_override = PlanDesign(
            generic_copay=Decimal("10.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result_with = reprice_claim(claim, plan_with_override)
        result_without = reprice_claim(claim, plan_without_override)
        # With higher dispensing fee, plan paid should be higher
        assert result_with.repriced_plan_paid > result_without.repriced_plan_paid

    def test_no_float_in_outputs(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("15.00"),
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert not isinstance(result.repriced_plan_paid, float)
        assert not isinstance(result.repriced_member_copay, float)
        assert not isinstance(result.delta_plan_paid, float)
        assert not isinstance(result.repriced_ingredient_cost, float)

    def test_plan_paid_never_negative(self) -> None:
        claim = ClaimForRepricing(
            claim_id="claim-001",
            ndc="12345678901",
            quantity=Decimal("30"),
            days_supply=30,
            ingredient_cost=Decimal("100.00"),
            dispensing_fee=Decimal("2.00"),
            member_copay=Decimal("10.00"),
            plan_paid=Decimal("92.00"),
            is_brand=False,
            is_specialty=False,
        )
        plan = PlanDesign(
            generic_copay=Decimal("200.00"),  # copay > total cost
            brand_copay=Decimal("40.00"),
            specialty_copay=Decimal("100.00"),
            awp_discount_pct=Decimal("0.16"),
            dispensing_fee_override=None,
        )
        result = reprice_claim(claim, plan)
        assert result.repriced_plan_paid >= Decimal("0")
