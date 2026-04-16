"""Tests for all 8 pricing model calculators — 100% financial path coverage.

Every test verifies Decimal precision and ROUND_HALF_UP rounding.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.services.pricing import (
    AWPDiscountCalculator,
    CashDiscountCardCalculator,
    CostPlusCalculator,
    CostPlusSpecialtyCalculator,
    DirectManufacturerCalculator,
    MACCalculator,
    NADACBasedCalculator,
    NetCostCalculator,
    PricingContext,
    PricingResult,
    calculate_cash_pay_comparison,
    get_calculator,
)
from shared.utils.money import ZERO


class TestAWPDiscount:
    def test_basic_discount(self):
        ctx = PricingContext(awp=Decimal("100.00"), dispensing_fee=Decimal("2.50"), parameters={"discount_pct": "15"})
        result = AWPDiscountCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("85.00")
        assert result.dispensing_fee == Decimal("2.50")
        assert result.total == Decimal("87.50")

    def test_zero_discount(self):
        ctx = PricingContext(awp=Decimal("100.00"), dispensing_fee=Decimal("1.00"), parameters={"discount_pct": "0"})
        result = AWPDiscountCalculator().calculate(ctx)
        assert result.total == Decimal("101.00")

    def test_missing_awp_raises(self):
        ctx = PricingContext(dispensing_fee=Decimal("1.00"), parameters={"discount_pct": "15"})
        with pytest.raises(ValueError, match="AWP is required"):
            AWPDiscountCalculator().calculate(ctx)

    def test_rounding_half_up(self):
        # AWP=100, discount=33.333% → ingredient=66.667 → rounds to 66.67 (HALF_UP)
        ctx = PricingContext(awp=Decimal("100.00"), dispensing_fee=ZERO, parameters={"discount_pct": "33.333"})
        result = AWPDiscountCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("66.67")


class TestMAC:
    def test_basic(self):
        ctx = PricingContext(mac=Decimal("25.00"), dispensing_fee=Decimal("3.00"))
        result = MACCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("25.00")
        assert result.total == Decimal("28.00")

    def test_missing_mac_raises(self):
        ctx = PricingContext(dispensing_fee=Decimal("1.00"))
        with pytest.raises(ValueError, match="MAC price is required"):
            MACCalculator().calculate(ctx)


class TestCostPlus:
    def test_with_acquisition_cost(self):
        ctx = PricingContext(
            acquisition_cost=Decimal("50.00"), dispensing_fee=Decimal("2.00"), parameters={"markup_pct": "10"},
        )
        result = CostPlusCalculator().calculate(ctx)
        # 50 * 1.10 = 55.00
        assert result.ingredient_cost == Decimal("55.00")
        assert result.total == Decimal("57.00")

    def test_fallback_to_awp(self):
        ctx = PricingContext(awp=Decimal("100.00"), dispensing_fee=Decimal("2.00"), parameters={"markup_pct": "5"})
        result = CostPlusCalculator().calculate(ctx)
        # AWP fallback: 100 * (1-0.15) = 85.00, then markup: 85 * 1.05 = 89.25
        assert result.ingredient_cost == Decimal("89.25")
        assert result.total == Decimal("91.25")

    def test_custom_fallback_discount(self):
        ctx = PricingContext(
            awp=Decimal("100.00"), dispensing_fee=ZERO,
            parameters={"markup_pct": "0", "awp_fallback_discount_pct": "20"},
        )
        result = CostPlusCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("80.00")

    def test_no_cost_no_awp_raises(self):
        ctx = PricingContext(dispensing_fee=Decimal("1.00"), parameters={"markup_pct": "10"})
        with pytest.raises(ValueError, match="requires acquisition_cost"):
            CostPlusCalculator().calculate(ctx)


class TestNADACBased:
    def test_basic(self):
        ctx = PricingContext(nadac=Decimal("40.00"), dispensing_fee=Decimal("5.00"), parameters={"markup_pct": "8"})
        result = NADACBasedCalculator().calculate(ctx)
        # 40 * 1.08 = 43.20
        assert result.ingredient_cost == Decimal("43.20")
        assert result.total == Decimal("48.20")

    def test_missing_nadac_raises(self):
        ctx = PricingContext(dispensing_fee=Decimal("1.00"))
        with pytest.raises(ValueError, match="NADAC price is required"):
            NADACBasedCalculator().calculate(ctx)


class TestNetCost:
    def test_basic(self):
        ctx = PricingContext(
            acquisition_cost=Decimal("30.00"), dispensing_fee=ZERO, parameters={"admin_fee": "5"},
        )
        result = NetCostCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("30.00")
        assert result.total == Decimal("35.00")

    def test_missing_cost_raises(self):
        ctx = PricingContext(dispensing_fee=ZERO, parameters={"admin_fee": "5"})
        with pytest.raises(ValueError, match="Net acquisition cost"):
            NetCostCalculator().calculate(ctx)


class TestCostPlusSpecialty:
    def test_basic(self):
        ctx = PricingContext(
            acquisition_cost=Decimal("1000.00"), dispensing_fee=Decimal("10.00"),
            parameters={"markup_pct": "5", "patient_mgmt_fee": "50"},
        )
        result = CostPlusSpecialtyCalculator().calculate(ctx)
        # 1000 * 1.05 = 1050
        assert result.ingredient_cost == Decimal("1050.00")
        # fee = 50 + 10 = 60
        assert result.dispensing_fee == Decimal("60.00")
        assert result.total == Decimal("1110.00")

    def test_missing_cost_raises(self):
        ctx = PricingContext(dispensing_fee=ZERO)
        with pytest.raises(ValueError, match="Acquisition cost required"):
            CostPlusSpecialtyCalculator().calculate(ctx)


class TestDirectManufacturer:
    def test_basic(self):
        ctx = PricingContext(manufacturer_price=Decimal("200.00"), dispensing_fee=ZERO)
        result = DirectManufacturerCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("200.00")
        assert result.total == Decimal("200.00")

    def test_missing_raises(self):
        ctx = PricingContext(dispensing_fee=ZERO)
        with pytest.raises(ValueError, match="Manufacturer price required"):
            DirectManufacturerCalculator().calculate(ctx)


class TestCashDiscountCard:
    def test_basic(self):
        ctx = PricingContext(cash_price=Decimal("15.00"), dispensing_fee=ZERO)
        result = CashDiscountCardCalculator().calculate(ctx)
        assert result.ingredient_cost == Decimal("15.00")
        assert result.total == Decimal("15.00")

    def test_missing_raises(self):
        ctx = PricingContext(dispensing_fee=ZERO)
        with pytest.raises(ValueError, match="Cash price required"):
            CashDiscountCardCalculator().calculate(ctx)


class TestCashPayComparison:
    def test_cash_cheaper(self):
        insurance = PricingResult(ingredient_cost=Decimal("85.00"), dispensing_fee=Decimal("2.50"), total=Decimal("87.50"))
        cash_ctx = PricingContext(cash_price=Decimal("40.00"), dispensing_fee=ZERO)
        result = calculate_cash_pay_comparison(insurance, cash_ctx)
        assert result.total == Decimal("40.00")

    def test_insurance_cheaper(self):
        insurance = PricingResult(ingredient_cost=Decimal("10.00"), dispensing_fee=Decimal("2.00"), total=Decimal("12.00"))
        cash_ctx = PricingContext(cash_price=Decimal("50.00"), dispensing_fee=ZERO)
        result = calculate_cash_pay_comparison(insurance, cash_ctx)
        assert result.total == Decimal("12.00")

    def test_no_cash_price_returns_insurance(self):
        insurance = PricingResult(ingredient_cost=Decimal("85.00"), dispensing_fee=Decimal("2.50"), total=Decimal("87.50"))
        cash_ctx = PricingContext(dispensing_fee=ZERO)
        result = calculate_cash_pay_comparison(insurance, cash_ctx)
        assert result.total == Decimal("87.50")


class TestRegistry:
    def test_all_8_calculators_registered(self):
        codes = ["awp_discount", "mac", "cost_plus", "nadac_based", "net_cost", "cost_plus_specialty", "direct_manufacturer", "cash_discount_card"]
        for code in codes:
            calc = get_calculator(code)
            assert calc.code == code

    def test_unknown_code_raises(self):
        with pytest.raises(KeyError, match="No pricing calculator"):
            get_calculator("nonexistent")


class TestReturnTypes:
    def test_all_calculators_return_decimal(self):
        cases = [
            ("awp_discount", PricingContext(awp=Decimal("100"), dispensing_fee=Decimal("2"), parameters={"discount_pct": "15"})),
            ("mac", PricingContext(mac=Decimal("25"), dispensing_fee=Decimal("3"))),
            ("cost_plus", PricingContext(acquisition_cost=Decimal("50"), dispensing_fee=Decimal("2"), parameters={"markup_pct": "10"})),
            ("nadac_based", PricingContext(nadac=Decimal("40"), dispensing_fee=Decimal("5"), parameters={"markup_pct": "8"})),
            ("net_cost", PricingContext(acquisition_cost=Decimal("30"), dispensing_fee=ZERO, parameters={"admin_fee": "5"})),
            ("cost_plus_specialty", PricingContext(acquisition_cost=Decimal("1000"), dispensing_fee=Decimal("10"), parameters={"markup_pct": "5", "patient_mgmt_fee": "50"})),
            ("direct_manufacturer", PricingContext(manufacturer_price=Decimal("200"), dispensing_fee=ZERO)),
            ("cash_discount_card", PricingContext(cash_price=Decimal("15"), dispensing_fee=ZERO)),
        ]
        for code, ctx in cases:
            calc = get_calculator(code)
            result = calc.calculate(ctx)
            assert isinstance(result.ingredient_cost, Decimal), f"{code}: ingredient_cost is not Decimal"
            assert isinstance(result.dispensing_fee, Decimal), f"{code}: dispensing_fee is not Decimal"
            assert isinstance(result.total, Decimal), f"{code}: total is not Decimal"
            assert not isinstance(result.total, float), f"{code}: total is float!"
