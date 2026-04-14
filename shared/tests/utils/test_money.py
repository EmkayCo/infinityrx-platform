"""Canonical money-helper tests.

This is the ONE place the ``money()`` / ``penny_allocate()`` / ``net_claims()``
behaviour is specified. Module-local tests in billing / payment-processing /
reclaimrx / reporting continue to exist for backward-compatibility but they
all exercise the same canonical implementation through the re-export shim.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from shared.utils.money import ZERO, money, net_claims, penny_allocate

_money = st.decimals(
    min_value=Decimal("-1000000"),
    max_value=Decimal("1000000"),
    allow_nan=False,
    allow_infinity=False,
    places=2,
)


class TestMoney:
    def test_int_to_decimal_2dp(self) -> None:
        assert money(100) == Decimal("100.00")

    def test_str_to_decimal_2dp(self) -> None:
        assert money("1.2345") == Decimal("1.23")

    def test_rounds_half_up(self) -> None:
        assert money("1.005") == Decimal("1.01")
        assert money("1.015") == Decimal("1.02")

    def test_negative_rounds_half_up(self) -> None:
        # ROUND_HALF_UP on a negative means away-from-zero on the .5
        assert money("-1.005") == Decimal("-1.01")

    def test_decimal_passthrough_rounds(self) -> None:
        assert money(Decimal("2.004")) == Decimal("2.00")
        assert money(Decimal("2.005")) == Decimal("2.01")


class TestPennyAllocate:
    def test_clean_split(self) -> None:
        assert penny_allocate(Decimal("10.00"), 4) == [Decimal("2.50")] * 4

    def test_remainder_absorbed_by_first_item(self) -> None:
        result = penny_allocate(Decimal("10.01"), 4)
        assert sum(result) == Decimal("10.01")
        # items[1:] are identical; items[0] carries the remainder.
        assert len(set(result[1:])) == 1

    def test_zero_count_returns_empty(self) -> None:
        assert penny_allocate(Decimal("10.00"), 0) == []

    def test_negative_count_returns_empty(self) -> None:
        assert penny_allocate(Decimal("10.00"), -1) == []

    @given(total=_money, count=st.integers(min_value=1, max_value=50))
    @settings(max_examples=300)
    def test_sum_preservation_invariant(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert sum(result) == total
        assert len(result) == count
        # Every non-first element is the same — only index 0 carries the
        # remainder. (LESSON-003: the first item may be smaller than the
        # rest when ``per_item`` rounds up.)
        assert len(set(result[1:])) <= 1


class TestNetClaims:
    def test_simple_sum(self) -> None:
        assert net_claims([Decimal("10.00"), Decimal("5.50")]) == Decimal("15.50")

    def test_credits_subtract(self) -> None:
        # Credits are expected to be negative amounts per contract.
        assert net_claims([Decimal("100.00"), Decimal("-25.00")]) == Decimal("75.00")

    def test_empty_list_is_zero(self) -> None:
        assert net_claims([]) == ZERO
