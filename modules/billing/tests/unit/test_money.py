"""Unit tests for money helpers — 100% coverage required."""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from src.utils.money import money, net_claims, penny_allocate


class TestMoney:
    def test_converts_int(self) -> None:
        assert money(1) == Decimal("1.00")

    def test_converts_float_string(self) -> None:
        assert money("10.5") == Decimal("10.50")

    def test_rounds_half_up(self) -> None:
        assert money("0.005") == Decimal("0.01")

    def test_rounds_half_up_negative(self) -> None:
        assert money("-0.005") == Decimal("-0.01")

    def test_converts_decimal_passthrough(self) -> None:
        d = Decimal("99.99")
        assert money(d) == d

    def test_zero(self) -> None:
        assert money(0) == Decimal("0.00")

    def test_large_amount(self) -> None:
        assert money("9999999.99") == Decimal("9999999.99")


class TestPennyAllocate:
    def test_even_split(self) -> None:
        result = penny_allocate(Decimal("10.00"), 2)
        assert result == [Decimal("5.00"), Decimal("5.00")]
        assert sum(result) == Decimal("10.00")

    def test_uneven_three_ways(self) -> None:
        result = penny_allocate(Decimal("100.00"), 3)
        assert result == [Decimal("33.34"), Decimal("33.33"), Decimal("33.33")]
        assert sum(result) == Decimal("100.00")

    def test_one_way(self) -> None:
        result = penny_allocate(Decimal("50.00"), 1)
        assert result == [Decimal("50.00")]
        assert sum(result) == Decimal("50.00")

    def test_zero_count_returns_empty(self) -> None:
        assert penny_allocate(Decimal("100.00"), 0) == []

    def test_negative_count_returns_empty(self) -> None:
        assert penny_allocate(Decimal("100.00"), -1) == []

    def test_penny_amount(self) -> None:
        result = penny_allocate(Decimal("0.01"), 2)
        assert sum(result) == Decimal("0.01")
        assert len(result) == 2

    def test_zero_total(self) -> None:
        result = penny_allocate(Decimal("0.00"), 3)
        assert all(r == Decimal("0.00") for r in result)
        assert sum(result) == Decimal("0.00")

    def test_all_results_are_decimal(self) -> None:
        result = penny_allocate(Decimal("100.00"), 7)
        assert all(isinstance(r, Decimal) for r in result)

    def test_count_preserved(self) -> None:
        result = penny_allocate(Decimal("100.00"), 7)
        assert len(result) == 7

    @given(
        total=st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("999999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        ),
        count=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=500)
    def test_always_sums_to_total(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert sum(result) == total
        assert len(result) == count
        assert all(isinstance(r, Decimal) for r in result)


class TestNetClaims:
    def test_net_positive(self) -> None:
        amounts = [Decimal("100.00"), Decimal("50.00")]
        assert net_claims(amounts) == Decimal("150.00")

    def test_net_with_credits(self) -> None:
        amounts = [Decimal("100.00"), Decimal("-25.00")]
        assert net_claims(amounts) == Decimal("75.00")

    def test_net_empty(self) -> None:
        assert net_claims([]) == Decimal("0.00")

    def test_returns_decimal(self) -> None:
        result = net_claims([Decimal("1.00")])
        assert isinstance(result, Decimal)
