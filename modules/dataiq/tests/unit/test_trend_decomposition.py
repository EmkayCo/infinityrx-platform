"""Unit tests for drug trend decomposition service.

TDD: tests written before implementation.
CRITICAL: util + price + mix must EXACTLY equal total_delta (Decimal).
"""

from __future__ import annotations

from decimal import Decimal

from src.services.trend_decomposition import (
    DecompositionResult,
    decompose_drug_trend,
)


class TestDecomposeDrugTrend:
    def test_basic_decomposition_sums_to_total(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1100"),
            p_old=Decimal("50.00"),
            p_new=Decimal("55.00"),
        )
        total_delta = result.total_delta
        component_sum = result.utilization_effect + result.price_effect + result.mix_effect
        assert component_sum == total_delta

    def test_utilization_effect_formula(self) -> None:
        # util = (Q_new - Q_old) * P_old
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1100"),
            p_old=Decimal("50.00"),
            p_new=Decimal("50.00"),
        )
        expected_util = (Decimal("1100") - Decimal("1000")) * Decimal("50.00")
        assert result.utilization_effect == expected_util

    def test_price_effect_formula(self) -> None:
        # price = (P_new - P_old) * Q_old
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1000"),
            p_old=Decimal("50.00"),
            p_new=Decimal("55.00"),
        )
        expected_price = (Decimal("55.00") - Decimal("50.00")) * Decimal("1000")
        assert result.price_effect == expected_price

    def test_mix_effect_formula(self) -> None:
        # mix = (Q_new - Q_old) * (P_new - P_old)
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1100"),
            p_old=Decimal("50.00"),
            p_new=Decimal("55.00"),
        )
        expected_mix = (Decimal("1100") - Decimal("1000")) * (Decimal("55.00") - Decimal("50.00"))
        assert result.mix_effect == expected_mix

    def test_no_change_all_effects_zero(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1000"),
            p_old=Decimal("50.00"),
            p_new=Decimal("50.00"),
        )
        assert result.utilization_effect == Decimal("0")
        assert result.price_effect == Decimal("0")
        assert result.mix_effect == Decimal("0")
        assert result.total_delta == Decimal("0")

    def test_total_delta_is_new_spend_minus_old_spend(self) -> None:
        q_old, q_new = Decimal("1000"), Decimal("1100")
        p_old, p_new = Decimal("50.00"), Decimal("55.00")
        result = decompose_drug_trend(q_old=q_old, q_new=q_new, p_old=p_old, p_new=p_new)
        expected_delta = (q_new * p_new) - (q_old * p_old)
        assert result.total_delta == expected_delta

    def test_negative_utilization_effect(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("1100"),
            q_new=Decimal("1000"),
            p_old=Decimal("50.00"),
            p_new=Decimal("50.00"),
        )
        assert result.utilization_effect < Decimal("0")
        component_sum = result.utilization_effect + result.price_effect + result.mix_effect
        assert component_sum == result.total_delta

    def test_negative_price_effect(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1000"),
            p_old=Decimal("55.00"),
            p_new=Decimal("50.00"),
        )
        assert result.price_effect < Decimal("0")
        component_sum = result.utilization_effect + result.price_effect + result.mix_effect
        assert component_sum == result.total_delta

    def test_all_components_are_decimal(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("1000"),
            q_new=Decimal("1100"),
            p_old=Decimal("50.00"),
            p_new=Decimal("55.00"),
        )
        assert isinstance(result.utilization_effect, Decimal)
        assert isinstance(result.price_effect, Decimal)
        assert isinstance(result.mix_effect, Decimal)
        assert isinstance(result.total_delta, Decimal)

    def test_known_hand_calculated_values(self) -> None:
        # Q_old=100, Q_new=110, P_old=10.00, P_new=12.00
        # Old spend = 100 * 10 = 1000
        # New spend = 110 * 12 = 1320
        # Total delta = 320
        # Util effect = (110-100)*10 = 100
        # Price effect = (12-10)*100 = 200
        # Mix effect = (110-100)*(12-10) = 20
        # Sum = 100 + 200 + 20 = 320 ✓
        result = decompose_drug_trend(
            q_old=Decimal("100"),
            q_new=Decimal("110"),
            p_old=Decimal("10.00"),
            p_new=Decimal("12.00"),
        )
        assert result.utilization_effect == Decimal("100")
        assert result.price_effect == Decimal("200")
        assert result.mix_effect == Decimal("20")
        assert result.total_delta == Decimal("320")
        assert result.utilization_effect + result.price_effect + result.mix_effect == result.total_delta

    def test_result_is_decomposition_result_type(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("100"),
            q_new=Decimal("110"),
            p_old=Decimal("10.00"),
            p_new=Decimal("12.00"),
        )
        assert isinstance(result, DecompositionResult)

    def test_zero_quantity_old(self) -> None:
        result = decompose_drug_trend(
            q_old=Decimal("0"),
            q_new=Decimal("100"),
            p_old=Decimal("10.00"),
            p_new=Decimal("10.00"),
        )
        assert result.utilization_effect == Decimal("1000")
        assert result.price_effect == Decimal("0")
        assert result.mix_effect == Decimal("0")
        component_sum = result.utilization_effect + result.price_effect + result.mix_effect
        assert component_sum == result.total_delta
