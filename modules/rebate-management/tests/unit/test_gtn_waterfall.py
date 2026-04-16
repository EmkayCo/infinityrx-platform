"""Tests for GTN waterfall service."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.services.gtn_waterfall import GTNWaterfallService
from src.utils.money import ZERO, money


class TestGTNComputation:
    """Test GTN net price and ratio calculations — pure math, no DB."""

    def setup_method(self):
        self.svc = GTNWaterfallService(db=None)

    def test_basic_waterfall(self):
        net, ratio = self.svc.compute_net_price(
            wac=Decimal("500.00"),
            wholesaler_discount=Decimal("10.00"),
            prompt_pay_discount=Decimal("10.00"),
            rebates=Decimal("150.00"),
            chargebacks=Decimal("50.00"),
            copay_assistance=Decimal("80.00"),
            copay_misuse_leakage=Decimal("15.00"),
            admin_fees=Decimal("5.00"),
        )
        # 500 - 10 - 10 - 150 - 50 - 80 - 15 - 5 = 180
        assert net == Decimal("180.00")
        # 180 / 500 = 0.3600
        assert ratio == Decimal("0.3600")

    def test_no_deductions(self):
        net, ratio = self.svc.compute_net_price(wac=Decimal("100.00"))
        assert net == Decimal("100.00")
        assert ratio == Decimal("1.0000")

    def test_zero_wac(self):
        net, ratio = self.svc.compute_net_price(wac=ZERO)
        assert net == ZERO
        assert ratio == Decimal("0.0000")

    def test_all_deductions_equal_wac(self):
        net, ratio = self.svc.compute_net_price(
            wac=Decimal("100.00"),
            rebates=Decimal("100.00"),
        )
        assert net == ZERO
        assert ratio == Decimal("0.0000")

    def test_sum_of_components_equals_wac(self):
        """Verify: WAC = net_price + sum(all deductions)."""
        wac = Decimal("1000.00")
        wd = Decimal("20.00")
        pp = Decimal("15.00")
        rb = Decimal("300.00")
        cb = Decimal("100.00")
        ca = Decimal("150.00")
        cm = Decimal("25.00")
        af = Decimal("10.00")
        net, _ = self.svc.compute_net_price(wac, wd, pp, rb, cb, ca, cm, af)
        total_deductions = money(wd + pp + rb + cb + ca + cm + af)
        assert money(net + total_deductions) == wac

    def test_fractional_ratio_rounding(self):
        # 333 / 1000 = 0.3330
        net, ratio = self.svc.compute_net_price(
            wac=Decimal("1000.00"),
            rebates=Decimal("667.00"),
        )
        assert net == Decimal("333.00")
        assert ratio == Decimal("0.3330")

    def test_all_return_types_decimal(self):
        net, ratio = self.svc.compute_net_price(
            wac=Decimal("500.00"), rebates=Decimal("100.00"),
        )
        assert isinstance(net, Decimal)
        assert isinstance(ratio, Decimal)
        assert not isinstance(net, float)
        assert not isinstance(ratio, float)
