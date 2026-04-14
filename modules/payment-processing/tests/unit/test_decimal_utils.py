"""Unit tests for decimal_utils — 100% coverage required (financial path)."""
from __future__ import annotations

from decimal import Decimal


from src.services.decimal_utils import money, penny_allocate


class TestMoney:
    def test_converts_string_to_decimal(self):
        assert money("10.50") == Decimal("10.50")

    def test_converts_int_to_decimal(self):
        assert money(100) == Decimal("100.00")

    def test_converts_decimal_passthrough(self):
        assert money(Decimal("3.14159")) == Decimal("3.14")

    def test_rounds_half_up(self):
        assert money("0.005") == Decimal("0.01")

    def test_rounds_down_below_half(self):
        assert money("0.004") == Decimal("0.00")

    def test_large_amount(self):
        assert money("999999.99") == Decimal("999999.99")

    def test_zero(self):
        assert money("0") == Decimal("0.00")

    def test_negative(self):
        assert money("-5.50") == Decimal("-5.50")


class TestPennyAllocate:
    def test_splits_evenly(self):
        result = penny_allocate(Decimal("90.00"), 3)
        assert result == [Decimal("30.00"), Decimal("30.00"), Decimal("30.00")]

    def test_splits_with_remainder_to_first(self):
        result = penny_allocate(Decimal("10.00"), 3)
        assert result == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]

    def test_sum_always_equals_total(self):
        total = Decimal("100.01")
        result = penny_allocate(total, 3)
        assert sum(result) == total

    def test_single_item(self):
        result = penny_allocate(Decimal("42.00"), 1)
        assert result == [Decimal("42.00")]

    def test_zero_count_returns_empty(self):
        result = penny_allocate(Decimal("100.00"), 0)
        assert result == []

    def test_zero_total(self):
        result = penny_allocate(Decimal("0.00"), 3)
        assert all(r == Decimal("0.00") for r in result)

    def test_one_cent_divided_by_three(self):
        result = penny_allocate(Decimal("0.01"), 3)
        assert sum(result) == Decimal("0.01")
        assert len(result) == 3

    def test_large_split(self):
        total = Decimal("10000.00")
        result = penny_allocate(total, 1000)
        assert sum(result) == total
        assert all(r == Decimal("10.00") for r in result)

    def test_negative_count_returns_empty(self):
        result = penny_allocate(Decimal("100.00"), -1)
        assert result == []
