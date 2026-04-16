"""Tests for spend cap guarantee service."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from src.utils.money import ZERO, money


class TestSpendCapAlertThresholds:
    """Test alert threshold logic without DB dependency."""

    def test_90_pct_threshold_calculation(self):
        ceiling = Decimal("100000.00")
        cumulative = Decimal("90000.00")
        pct = money(cumulative / ceiling)
        # At exactly 90% → alert should fire
        assert pct >= Decimal("0.90")

    def test_below_80_no_alert(self):
        ceiling = Decimal("100000.00")
        cumulative = Decimal("79000.00")
        pct = (cumulative / ceiling).quantize(Decimal("0.0001"))
        assert pct < Decimal("0.80")

    def test_overage_refund_calculation(self):
        ceiling = Decimal("100000.00")
        actual = Decimal("115000.00")
        refund = money(actual - ceiling)
        assert refund == Decimal("15000.00")

    def test_under_ceiling_no_refund(self):
        ceiling = Decimal("100000.00")
        actual = Decimal("95000.00")
        refund = max(money(actual - ceiling), ZERO)
        assert refund == ZERO

    def test_exact_ceiling_no_refund(self):
        ceiling = Decimal("100000.00")
        actual = Decimal("100000.00")
        refund = money(actual - ceiling)
        assert refund == ZERO

    def test_utilization_pct_precision(self):
        ceiling = Decimal("333333.33")
        cumulative = Decimal("250000.00")
        pct = (cumulative / ceiling).quantize(Decimal("0.0001"))
        # 250000 / 333333.33 = 0.7500...
        assert isinstance(pct, Decimal)
        assert pct == Decimal("0.7500")
