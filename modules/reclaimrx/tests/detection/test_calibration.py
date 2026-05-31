"""Unit tests for calibration.py helpers.
Uses modules/reclaimrx/tests/conftest.py fixtures (engine, db, etc.) via conftest import.
"""
from __future__ import annotations
from decimal import Decimal
import pytest
from src.detection.calibration import (
    percentile_within_cohort,
    zscore_flag,
    passes_min_sample,
    passes_dollar_floor,
)

class TestPassesMinSample:
    def test_sufficient(self):
        assert passes_min_sample(sample_count=30, min_required=30) is True

    def test_insufficient(self):
        assert passes_min_sample(sample_count=29, min_required=30) is False

    def test_zero_min(self):
        assert passes_min_sample(sample_count=0, min_required=0) is True


class TestPassesDollarFloor:
    def test_above_floor(self):
        assert passes_dollar_floor(Decimal("150.00"), Decimal("100.00")) is True

    def test_at_floor(self):
        assert passes_dollar_floor(Decimal("100.00"), Decimal("100.00")) is True

    def test_below_floor(self):
        assert passes_dollar_floor(Decimal("99.99"), Decimal("100.00")) is False

    def test_none_floor(self):
        # None floor means no floor check
        assert passes_dollar_floor(Decimal("0.01"), None) is True


class TestZscoreFlag:
    def test_fires_above_threshold(self):
        # z = (150 - 100) / 10 = 5.0 > 3.0
        fired, z = zscore_flag(
            value=Decimal("150"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is True
        assert z > Decimal("3.0")

    def test_no_fire_below_threshold(self):
        # z = (102 - 100) / 10 = 0.2 < 3.0
        fired, z = zscore_flag(
            value=Decimal("102"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is False

    def test_zero_stddev_no_fire(self):
        # stddev=0 -> undefined z, must not raise, must not fire
        fired, z = zscore_flag(
            value=Decimal("200"),
            mean=Decimal("100"),
            stddev=Decimal("0"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is False
        assert z is None

    def test_returns_decimal_z(self):
        fired, z = zscore_flag(
            value=Decimal("130"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert isinstance(z, Decimal)


class TestPercentileWithinCohort:
    def test_top_value_is_p100(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("100"), values)
        assert pct == Decimal("1.0")

    def test_bottom_value_is_low(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("1"), values)
        assert pct <= Decimal("0.05")

    def test_midpoint(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("50"), values)
        assert Decimal("0.45") <= pct <= Decimal("0.55")

    def test_empty_cohort_returns_none(self):
        result = percentile_within_cohort(Decimal("50"), [])
        assert result is None

    def test_returns_decimal(self):
        values = [Decimal("10"), Decimal("20"), Decimal("30")]
        pct = percentile_within_cohort(Decimal("20"), values)
        assert isinstance(pct, Decimal)
