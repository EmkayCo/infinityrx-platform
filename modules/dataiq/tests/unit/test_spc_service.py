"""Unit tests for Statistical Process Control service.

TDD: these tests are written BEFORE the implementation.
All SPC calculations use Decimal to avoid float drift.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from src.services.spc import (
    SPCResult,
    WesternElectricViolation,
    calculate_control_limits,
    check_western_electric_rules,
    detect_anomaly,
)


class TestCalculateControlLimits:
    def test_basic_three_sigma_limits(self) -> None:
        values = [Decimal(str(v)) for v in [10, 12, 11, 13, 10, 11, 12, 10, 11, 12]]
        result = calculate_control_limits(values, sigma_multiplier=Decimal("3"))
        # mean = 11.2, std ≈ 0.9798
        assert result.mean == Decimal("11.2")
        assert result.ucl > result.mean
        assert result.lcl < result.mean
        assert result.ucl - result.mean == result.mean - result.lcl  # symmetric

    def test_control_limits_are_decimal(self) -> None:
        values = [Decimal("100.00"), Decimal("102.00"), Decimal("98.00")]
        result = calculate_control_limits(values, sigma_multiplier=Decimal("2"))
        assert isinstance(result.mean, Decimal)
        assert isinstance(result.ucl, Decimal)
        assert isinstance(result.lcl, Decimal)
        assert isinstance(result.std_dev, Decimal)

    def test_two_sigma_limits_narrower_than_three(self) -> None:
        values = [Decimal(str(v)) for v in [10, 12, 11, 13, 10, 11, 12, 10, 11, 12]]
        result_2 = calculate_control_limits(values, sigma_multiplier=Decimal("2"))
        result_3 = calculate_control_limits(values, sigma_multiplier=Decimal("3"))
        assert result_2.ucl < result_3.ucl
        assert result_2.lcl > result_3.lcl

    def test_zero_variance_data(self) -> None:
        values = [Decimal("5.00")] * 10
        result = calculate_control_limits(values, sigma_multiplier=Decimal("3"))
        assert result.mean == Decimal("5.00")
        assert result.std_dev == Decimal("0")
        assert result.ucl == Decimal("5.00")
        assert result.lcl == Decimal("5.00")

    def test_single_value_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            calculate_control_limits([Decimal("5.00")], sigma_multiplier=Decimal("3"))

    def test_empty_values_raises(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            calculate_control_limits([], sigma_multiplier=Decimal("3"))

    def test_known_fixture_values(self) -> None:
        # Hand-calculated: values = [2, 4, 4, 4, 5, 5, 7, 9], mean=5, std=2
        values = [Decimal(str(v)) for v in [2, 4, 4, 4, 5, 5, 7, 9]]
        result = calculate_control_limits(values, sigma_multiplier=Decimal("3"))
        assert result.mean == Decimal("5")
        assert result.std_dev == Decimal("2")
        assert result.ucl == Decimal("11")  # 5 + 3*2
        assert result.lcl == Decimal("-1")  # 5 - 3*2


class TestDetectAnomaly:
    def test_value_above_ucl_is_anomalous(self) -> None:
        result = detect_anomaly(
            value=Decimal("15.0"),
            ucl=Decimal("12.0"),
            lcl=Decimal("8.0"),
        )
        assert result is True

    def test_value_below_lcl_is_anomalous(self) -> None:
        result = detect_anomaly(
            value=Decimal("5.0"),
            ucl=Decimal("12.0"),
            lcl=Decimal("8.0"),
        )
        assert result is True

    def test_value_within_limits_is_not_anomalous(self) -> None:
        result = detect_anomaly(
            value=Decimal("10.0"),
            ucl=Decimal("12.0"),
            lcl=Decimal("8.0"),
        )
        assert result is False

    def test_value_exactly_at_ucl_is_not_anomalous(self) -> None:
        result = detect_anomaly(
            value=Decimal("12.0"),
            ucl=Decimal("12.0"),
            lcl=Decimal("8.0"),
        )
        assert result is False

    def test_value_exactly_at_lcl_is_not_anomalous(self) -> None:
        result = detect_anomaly(
            value=Decimal("8.0"),
            ucl=Decimal("12.0"),
            lcl=Decimal("8.0"),
        )
        assert result is False


class TestWesternElectricRules:
    """Western Electric rules for detecting non-random patterns."""

    def test_rule1_one_point_beyond_3sigma(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        # 16 = mean + 3*std = 16, exactly on boundary → not triggered
        # 16.1 > 16 → triggered
        values = [mean] * 7 + [Decimal("16.1")]
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule1 = [v for v in violations if v.rule == 1]
        assert len(rule1) >= 1

    def test_rule1_not_triggered_within_limits(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        values = [mean] * 8
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule1 = [v for v in violations if v.rule == 1]
        assert len(rule1) == 0

    def test_rule4_eight_consecutive_same_side(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        # 8 points above mean (but within 3-sigma)
        values = [Decimal("11")] * 8
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule4 = [v for v in violations if v.rule == 4]
        assert len(rule4) >= 1

    def test_rule4_not_triggered_with_seven_consecutive(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        values = [Decimal("11")] * 7
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule4 = [v for v in violations if v.rule == 4]
        assert len(rule4) == 0

    def test_rule2_two_of_three_beyond_2sigma_same_side(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        # 2-sigma boundary = 14; values: [14.5, 14.5, 10] - 2 of 3 above 2-sigma same side
        values = [Decimal("14.5"), Decimal("14.5"), Decimal("10")]
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule2 = [v for v in violations if v.rule == 2]
        assert len(rule2) >= 1

    def test_violations_have_correct_structure(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        values = [Decimal("11")] * 8
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        for v in violations:
            assert isinstance(v, WesternElectricViolation)
            assert v.rule in (1, 2, 3, 4)
            assert v.index >= 0

    def test_empty_series_returns_no_violations(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        violations = check_western_electric_rules([], mean=mean, std_dev=std)
        assert violations == []


class TestWesternElectricRule3:
    def test_rule3_four_of_five_beyond_1sigma_same_side(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        # 1-sigma boundary = 12; 4 of 5 points above 12
        values = [Decimal("13"), Decimal("13"), Decimal("13"), Decimal("13"), Decimal("10")]
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule3 = [v for v in violations if v.rule == 3]
        assert len(rule3) >= 1

    def test_rule3_four_of_five_below_1sigma_same_side(self) -> None:
        mean = Decimal("10")
        std = Decimal("2")
        # Below 1-sigma boundary = 8; 4 of 5 points below 8
        values = [Decimal("7"), Decimal("7"), Decimal("7"), Decimal("7"), Decimal("10")]
        violations = check_western_electric_rules(values, mean=mean, std_dev=std)
        rule3 = [v for v in violations if v.rule == 3]
        assert len(rule3) >= 1


class TestDecimalSqrt:
    def test_negative_value_raises(self) -> None:
        from src.services.spc import _decimal_sqrt

        with pytest.raises(ValueError, match="negative"):
            _decimal_sqrt(Decimal("-1"))

    def test_sqrt_of_zero(self) -> None:
        from src.services.spc import _decimal_sqrt

        assert _decimal_sqrt(Decimal("0")) == Decimal("0")

    def test_sqrt_of_known_value(self) -> None:
        from src.services.spc import _decimal_sqrt

        result = _decimal_sqrt(Decimal("4"))
        assert abs(result - Decimal("2")) < Decimal("0.0001")

    def test_sqrt_returns_last_x_when_not_converged_in_time(self) -> None:
        from unittest.mock import patch

        import src.services.spc as spc_module

        # Force range(20) to yield only 1 iteration without triggering early return
        # by making abs(x_next - x) very large on the only iteration
        original_sqrt = spc_module._decimal_sqrt

        # Patch range to return a single element to exercise the fallback return
        with patch("builtins.range", return_value=range(1)):
            result = original_sqrt(Decimal("100"))
        # Result should be a Decimal (even if not fully converged)
        assert isinstance(result, Decimal)
        assert result > Decimal("0")


class TestSPCResult:
    def test_result_has_required_fields(self) -> None:
        result = SPCResult(
            mean=Decimal("10"),
            std_dev=Decimal("2"),
            ucl=Decimal("16"),
            lcl=Decimal("4"),
            sigma_multiplier=Decimal("3"),
            n=10,
        )
        assert result.mean == Decimal("10")
        assert result.ucl == Decimal("16")
        assert result.lcl == Decimal("4")
        assert result.n == 10
