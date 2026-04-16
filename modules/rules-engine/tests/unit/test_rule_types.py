"""Unit tests for all rule type executors.

Verifies:
- Correct RuleAction returned for each scenario
- All monetary results are Decimal, never float
- ROUND_HALF_UP precision
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.services.rule_types import (
    AgeRule,
    BillCostCalculator,
    BiosimilarSubstitutionRule,
    ClaimContext,
    CopayRule,
    DispenseFeeRule,
    PARequiredRule,
    QuantityLimitRule,
    RefillRule,
    RuleAction,
    StepTherapyRule,
    get_executor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_ctx(**overrides) -> ClaimContext:
    """Build a ClaimContext with sensible defaults, overriding as needed."""
    defaults = {
        "claim_id": "CLM-001",
        "member_id": "MEM-001",
        "member_age": 45,
        "member_state": "TX",
        "ndc": "12345678901",
        "drug_name": "TestDrug",
        "drug_type": "generic",
        "quantity": Decimal("30"),
        "days_supply": 30,
        "pharmacy_npi": "1234567890",
        "pharmacy_type": "retail",
        "plan_id": "PLAN-001",
        "ingredient_cost": Decimal("100.00"),
    }
    defaults.update(overrides)
    return ClaimContext(**defaults)


def _assert_decimal(value, msg=""):
    """Assert that a value is a Decimal, never a float."""
    assert isinstance(value, Decimal), f"Expected Decimal, got {type(value).__name__}: {value}. {msg}"


# ---------------------------------------------------------------------------
# BillCostCalculator
# ---------------------------------------------------------------------------


class TestBillCostCalculator:
    def test_basic_awp_cost(self):
        ctx = _base_ctx(quantity=Decimal("30"))
        params = {"pricing_source": "awp", "awp_unit_price": "2.50"}
        result = BillCostCalculator().execute(ctx, params)

        assert result.action == RuleAction.MODIFY
        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        assert cost == Decimal("75.00")

    def test_cost_with_discount(self):
        ctx = _base_ctx(quantity=Decimal("30"))
        params = {"pricing_source": "awp", "awp_unit_price": "2.50", "discount_pct": "10"}
        result = BillCostCalculator().execute(ctx, params)

        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        assert cost == Decimal("67.50")

    def test_cost_with_tiered_pricing(self):
        ctx = _base_ctx(quantity=Decimal("100"))
        params = {
            "pricing_source": "awp",
            "awp_unit_price": "1.00",
            "tier_rules": [
                {"min_quantity": "0", "max_quantity": "50", "discount_pct": "5"},
                {"min_quantity": "51", "max_quantity": "200", "discount_pct": "10"},
            ],
        }
        result = BillCostCalculator().execute(ctx, params)

        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        # 100 * 1.00 = 100.00, 10% discount = 90.00
        assert cost == Decimal("90.00")

    def test_mac_pricing_source(self):
        ctx = _base_ctx(quantity=Decimal("60"))
        params = {"pricing_source": "mac", "mac_unit_price": "0.75"}
        result = BillCostCalculator().execute(ctx, params)

        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        assert cost == Decimal("45.00")

    def test_decimal_precision_rounding(self):
        """Verify ROUND_HALF_UP on fractional costs."""
        ctx = _base_ctx(quantity=Decimal("7"))
        params = {"pricing_source": "awp", "awp_unit_price": "3.333"}
        result = BillCostCalculator().execute(ctx, params)

        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        # unit_price money(3.333) = 3.33, then 7 * 3.33 = 23.31
        assert cost == Decimal("23.31")

    def test_zero_quantity(self):
        ctx = _base_ctx(quantity=Decimal("0"))
        params = {"pricing_source": "awp", "awp_unit_price": "10.00"}
        result = BillCostCalculator().execute(ctx, params)

        cost = result.modified_values["ingredient_cost"]
        _assert_decimal(cost)
        assert cost == Decimal("0.00")


# ---------------------------------------------------------------------------
# CopayRule
# ---------------------------------------------------------------------------


class TestCopayRule:
    def test_flat_copay(self):
        ctx = _base_ctx()
        params = {"copay_type": "flat", "flat_amount": "25.00"}
        result = CopayRule().execute(ctx, params)

        assert result.action == RuleAction.MODIFY
        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("25.00")

    def test_percentage_copay(self):
        ctx = _base_ctx(ingredient_cost=Decimal("200.00"))
        params = {"copay_type": "percentage", "percentage": "20"}
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("40.00")

    def test_tiered_copay_generic(self):
        ctx = _base_ctx(drug_type="generic")
        params = {
            "copay_type": "tiered",
            "tier_map": {"generic": "10.00", "brand": "35.00", "specialty": "100.00"},
        }
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("10.00")

    def test_tiered_copay_brand(self):
        ctx = _base_ctx(drug_type="brand")
        params = {
            "copay_type": "tiered",
            "tier_map": {"generic": "10.00", "brand": "35.00", "specialty": "100.00"},
        }
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("35.00")

    def test_tiered_copay_specialty(self):
        ctx = _base_ctx(drug_type="specialty")
        params = {
            "copay_type": "tiered",
            "tier_map": {"generic": "10.00", "brand": "35.00", "specialty": "100.00"},
        }
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("100.00")

    def test_step_copay(self):
        ctx = _base_ctx(ingredient_cost=Decimal("150.00"))
        params = {
            "copay_type": "step",
            "step_tiers": [
                {"max_cost": "100", "copay": "15.00"},
                {"max_cost": "500", "copay": "30.00"},
                {"max_cost": "999999", "copay": "75.00"},
            ],
        }
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        assert copay == Decimal("30.00")

    def test_copay_min_bound(self):
        ctx = _base_ctx(ingredient_cost=Decimal("5.00"))
        params = {"copay_type": "percentage", "percentage": "10", "min_copay": "5.00"}
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        # 10% of 5.00 = 0.50, but min is 5.00
        assert copay == Decimal("5.00")

    def test_copay_max_bound(self):
        ctx = _base_ctx(ingredient_cost=Decimal("5000.00"))
        params = {"copay_type": "percentage", "percentage": "20", "max_copay": "200.00"}
        result = CopayRule().execute(ctx, params)

        copay = result.modified_values["copay"]
        _assert_decimal(copay)
        # 20% of 5000 = 1000, but max is 200
        assert copay == Decimal("200.00")

    def test_all_copay_results_are_decimal(self):
        """Sweep all copay types and verify Decimal output."""
        for copay_type, params in [
            ("flat", {"copay_type": "flat", "flat_amount": "10"}),
            ("percentage", {"copay_type": "percentage", "percentage": "15"}),
            ("tiered", {"copay_type": "tiered", "tier_map": {"generic": "5"}}),
            ("step", {"copay_type": "step", "step_tiers": [{"max_cost": "999999", "copay": "20"}]}),
        ]:
            result = CopayRule().execute(_base_ctx(), params)
            copay = result.modified_values["copay"]
            _assert_decimal(copay, f"copay_type={copay_type}")


# ---------------------------------------------------------------------------
# DispenseFeeRule
# ---------------------------------------------------------------------------


class TestDispenseFeeRule:
    def test_flat_fee(self):
        ctx = _base_ctx()
        params = {"fee_type": "flat", "flat_fee": "2.50"}
        result = DispenseFeeRule().execute(ctx, params)

        assert result.action == RuleAction.MODIFY
        fee = result.modified_values["dispensing_fee"]
        _assert_decimal(fee)
        assert fee == Decimal("2.50")

    def test_variable_by_pharmacy_type(self):
        ctx = _base_ctx(pharmacy_type="mail")
        params = {
            "fee_type": "variable",
            "pharmacy_fee_map": {"retail": "2.50", "mail": "0.50", "specialty": "5.00"},
        }
        result = DispenseFeeRule().execute(ctx, params)

        fee = result.modified_values["dispensing_fee"]
        _assert_decimal(fee)
        assert fee == Decimal("0.50")

    def test_variable_fallback_to_flat(self):
        ctx = _base_ctx(pharmacy_type="unknown")
        params = {
            "fee_type": "variable",
            "pharmacy_fee_map": {"retail": "2.50"},
            "flat_fee": "1.00",
        }
        result = DispenseFeeRule().execute(ctx, params)

        fee = result.modified_values["dispensing_fee"]
        _assert_decimal(fee)
        assert fee == Decimal("1.00")


# ---------------------------------------------------------------------------
# QuantityLimitRule
# ---------------------------------------------------------------------------


class TestQuantityLimitRule:
    def test_within_limit(self):
        ctx = _base_ctx(quantity=Decimal("30"))
        params = {"max_quantity": "90"}
        result = QuantityLimitRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_over_quantity_limit(self):
        ctx = _base_ctx(quantity=Decimal("100"))
        params = {"max_quantity": "90"}
        result = QuantityLimitRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "QL_EXCEEDED"

    def test_days_supply_exceeded(self):
        ctx = _base_ctx(days_supply=90)
        params = {"max_days_supply": 30}
        result = QuantityLimitRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "DS_EXCEEDED"

    def test_days_supply_within_limit(self):
        ctx = _base_ctx(days_supply=30)
        params = {"max_days_supply": 90}
        result = QuantityLimitRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_no_limits_configured(self):
        ctx = _base_ctx(quantity=Decimal("9999"))
        params = {}
        result = QuantityLimitRule().execute(ctx, params)

        assert result.action == RuleAction.PASS


# ---------------------------------------------------------------------------
# RefillRule
# ---------------------------------------------------------------------------


class TestRefillRule:
    def test_no_prior_fill(self):
        ctx = _base_ctx(last_fill_date=None)
        params = {"threshold_pct": "75"}
        result = RefillRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_early_refill_rejected(self):
        ctx = _base_ctx(
            last_fill_date=date.today() - timedelta(days=5),
            days_supply=30,
        )
        params = {"threshold_pct": "75"}
        result = RefillRule().execute(ctx, params)

        # 75% of 30 = 22.5 -> 23 days threshold. 5 < 23 -> reject
        assert result.action == RuleAction.REJECT
        assert result.reject_code == "EARLY_REFILL"

    def test_on_time_refill(self):
        ctx = _base_ctx(
            last_fill_date=date.today() - timedelta(days=25),
            days_supply=30,
        )
        params = {"threshold_pct": "75"}
        result = RefillRule().execute(ctx, params)

        # 75% of 30 = 22.5 -> 23. 25 >= 23 -> pass
        assert result.action == RuleAction.PASS

    def test_early_refill_vacation_override(self):
        ctx = _base_ctx(
            last_fill_date=date.today() - timedelta(days=5),
            days_supply=30,
        )
        params = {"threshold_pct": "75", "allow_vacation_override": True}
        result = RefillRule().execute(ctx, params)

        assert result.action == RuleAction.FLAG

    def test_threshold_by_days(self):
        ctx = _base_ctx(
            last_fill_date=date.today() - timedelta(days=10),
            days_supply=30,
        )
        params = {"threshold_days": 20}
        result = RefillRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "EARLY_REFILL"


# ---------------------------------------------------------------------------
# AgeRule
# ---------------------------------------------------------------------------


class TestAgeRule:
    def test_age_within_range(self):
        ctx = _base_ctx(member_age=25)
        params = {"min_age": 18, "max_age": 65}
        result = AgeRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_age_below_minimum(self):
        ctx = _base_ctx(member_age=12)
        params = {"min_age": 18}
        result = AgeRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "AGE_MIN"

    def test_age_above_maximum(self):
        ctx = _base_ctx(member_age=70)
        params = {"max_age": 65}
        result = AgeRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "AGE_MAX"

    def test_no_age_limits(self):
        ctx = _base_ctx(member_age=99)
        params = {}
        result = AgeRule().execute(ctx, params)

        assert result.action == RuleAction.PASS


# ---------------------------------------------------------------------------
# StepTherapyRule
# ---------------------------------------------------------------------------


class TestStepTherapyRule:
    def test_step_therapy_met(self):
        ctx = _base_ctx(prior_drug_trials=["DrugA", "DrugB"])
        params = {"required_prior_drugs": ["DrugA"]}
        result = StepTherapyRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_step_therapy_not_met(self):
        ctx = _base_ctx(prior_drug_trials=["DrugC"])
        params = {"required_prior_drugs": ["DrugA", "DrugB"]}
        result = StepTherapyRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "STEP_THERAPY"

    def test_step_therapy_no_requirements(self):
        ctx = _base_ctx(prior_drug_trials=[])
        params = {"required_prior_drugs": []}
        result = StepTherapyRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_step_therapy_partial_match(self):
        """If any one of the required drugs was tried, step therapy is met."""
        ctx = _base_ctx(prior_drug_trials=["DrugB"])
        params = {"required_prior_drugs": ["DrugA", "DrugB"]}
        result = StepTherapyRule().execute(ctx, params)

        assert result.action == RuleAction.PASS


# ---------------------------------------------------------------------------
# PARequiredRule
# ---------------------------------------------------------------------------


class TestPARequiredRule:
    def test_pa_not_required(self):
        ctx = _base_ctx()
        params = {"pa_required": False}
        result = PARequiredRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_pa_required_and_approved(self):
        ctx = _base_ctx(pa_on_file=True, pa_approved=True)
        params = {"pa_required": True}
        result = PARequiredRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_pa_required_not_on_file(self):
        ctx = _base_ctx(pa_on_file=False, pa_approved=False)
        params = {"pa_required": True, "pa_trigger_codes": ["GN01"]}
        result = PARequiredRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "PA_REQUIRED"

    def test_pa_on_file_but_not_approved(self):
        ctx = _base_ctx(pa_on_file=True, pa_approved=False)
        params = {"pa_required": True}
        result = PARequiredRule().execute(ctx, params)

        assert result.action == RuleAction.REJECT
        assert result.reject_code == "PA_REQUIRED"


# ---------------------------------------------------------------------------
# BiosimilarSubstitutionRule
# ---------------------------------------------------------------------------


class TestBiosimilarSubstitutionRule:
    def test_no_alternative_configured(self):
        ctx = _base_ctx()
        params = {"alternative_ndc": ""}
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.PASS

    def test_successful_substitution(self):
        ctx = _base_ctx(
            ndc="11111111111",
            member_state="TX",
            state_allows_biosimilar_sub=True,
            prescriber_daw="0",
        )
        params = {
            "alternative_ndc": "22222222222",
            "interchangeable": True,
        }
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.MODIFY
        assert result.modified_values["ndc"] == "22222222222"

    def test_state_blocks_substitution(self):
        ctx = _base_ctx(member_state="CA")
        params = {
            "alternative_ndc": "22222222222",
            "interchangeable": True,
            "state_law_overrides": {"CA": False},
        }
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.FLAG
        assert "CA" in result.message

    def test_daw_code_prevents_substitution(self):
        ctx = _base_ctx(prescriber_daw="1")
        params = {
            "alternative_ndc": "22222222222",
            "interchangeable": True,
        }
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.FLAG
        assert "DAW" in result.message

    def test_non_interchangeable_flags(self):
        ctx = _base_ctx(prescriber_daw="0")
        params = {
            "alternative_ndc": "22222222222",
            "interchangeable": False,
        }
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.FLAG
        assert "not FDA-interchangeable" in result.message

    def test_state_default_allows_substitution(self):
        """When no state override, use ctx.state_allows_biosimilar_sub."""
        ctx = _base_ctx(
            member_state="NY",
            state_allows_biosimilar_sub=True,
            prescriber_daw="0",
        )
        params = {
            "alternative_ndc": "22222222222",
            "interchangeable": True,
            "state_law_overrides": {},
        }
        result = BiosimilarSubstitutionRule().execute(ctx, params)

        assert result.action == RuleAction.MODIFY


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_get_known_executor(self):
        executor = get_executor("bill_cost_calculator")
        assert isinstance(executor, BillCostCalculator)

    def test_get_unknown_executor_raises(self):
        with pytest.raises(ValueError, match="Unknown rule type code"):
            get_executor("nonexistent_rule")


# ---------------------------------------------------------------------------
# Decimal invariant — sweep all rule types
# ---------------------------------------------------------------------------


class TestDecimalInvariant:
    """Verify no rule type ever returns float in modified_values."""

    def test_bill_cost_produces_decimal(self):
        result = BillCostCalculator().execute(
            _base_ctx(quantity=Decimal("10")),
            {"pricing_source": "awp", "awp_unit_price": "3.14159"},
        )
        for v in result.modified_values.values():
            _assert_decimal(v, "BillCostCalculator")

    def test_copay_produces_decimal(self):
        result = CopayRule().execute(
            _base_ctx(ingredient_cost=Decimal("123.456")),
            {"copay_type": "percentage", "percentage": "33.333"},
        )
        for v in result.modified_values.values():
            _assert_decimal(v, "CopayRule")

    def test_dispense_fee_produces_decimal(self):
        result = DispenseFeeRule().execute(
            _base_ctx(),
            {"fee_type": "flat", "flat_fee": "1.999"},
        )
        for v in result.modified_values.values():
            _assert_decimal(v, "DispenseFeeRule")
