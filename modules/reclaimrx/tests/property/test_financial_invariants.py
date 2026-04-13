"""Property-based tests for financial invariants — TDD first.

These use Hypothesis to verify mathematical invariants hold for any inputs.
"""
from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from src.utils.money import money, penny_allocate, three_tier_recovery

# ── Strategies ────────────────────────────────────────────────────────────────

# Financial amounts: 0.01 to 999,999.99 with 2 decimal places
money_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

split_counts = st.integers(min_value=1, max_value=1000)

confidence_tiers = st.sampled_from(["high", "medium", "low"])

recovery_item = st.fixed_dictionaries({
    "amount": money_amounts,
    "confidence": confidence_tiers,
})


# ── Penny Allocation Invariants ────────────────────────────────────────────────

@given(total=money_amounts, count=split_counts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_penny_allocate_sum_always_equals_total(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert sum(result) == total, f"Sum {sum(result)} != total {total} for count={count}"


@given(total=money_amounts, count=split_counts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_penny_allocate_correct_length(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert len(result) == count


@given(total=money_amounts, count=split_counts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_penny_allocate_all_results_are_decimal(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert all(isinstance(r, Decimal) for r in result)


@given(total=money_amounts, count=split_counts)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_penny_allocate_non_first_items_are_equal(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    # Items at index 1+ are all the same base per-item amount; only index 0 absorbs remainder
    if len(result) > 2:
        for i in range(2, len(result)):
            assert result[i] == result[1], f"Non-first items differ: {result[1]} vs {result[i]}"


@given(total=money_amounts, count=split_counts)
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_penny_allocate_first_item_absorbs_remainder(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    per_item = (total / count).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
    remainder = total - per_item * count
    expected_first = (per_item + remainder).quantize(Decimal("0.01"), rounding="ROUND_HALF_UP")
    assert result[0] == expected_first, f"First item {result[0]} != expected {expected_first}"


# ── Three-Tier Recovery Invariants ─────────────────────────────────────────────

@given(items=st.lists(recovery_item, min_size=0, max_size=50))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_three_tier_conservative_lte_mid_lte_aggressive(items: list) -> None:
    result = three_tier_recovery(items)
    assert result["conservative"] <= result["mid"] <= result["aggressive"], (
        f"Monotonicity violated: conservative={result['conservative']}, "
        f"mid={result['mid']}, aggressive={result['aggressive']}"
    )


@given(items=st.lists(recovery_item, min_size=0, max_size=50))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_three_tier_aggressive_equals_sum_of_all(items: list) -> None:
    result = three_tier_recovery(items)
    total = sum(i["amount"] for i in items) if items else Decimal("0.00")
    assert result["aggressive"] == total


@given(items=st.lists(recovery_item, min_size=1, max_size=50))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_three_tier_all_results_are_decimal(items: list) -> None:
    result = three_tier_recovery(items)
    assert isinstance(result["conservative"], Decimal)
    assert isinstance(result["mid"], Decimal)
    assert isinstance(result["aggressive"], Decimal)


@given(items=st.lists(recovery_item, min_size=0, max_size=50))
@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
def test_three_tier_results_non_negative(items: list) -> None:
    result = three_tier_recovery(items)
    assert result["conservative"] >= Decimal("0.00")
    assert result["mid"] >= Decimal("0.00")
    assert result["aggressive"] >= Decimal("0.00")


# ── Money Conversion Invariants ────────────────────────────────────────────────

@given(amount=money_amounts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_money_result_has_two_decimal_places(amount: Decimal) -> None:
    result = money(amount)
    _sign, _digits, exponent = result.as_tuple()
    assert exponent == -2, f"Expected 2 decimal places, got exponent={exponent}"


@given(amount=money_amounts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_money_result_is_decimal_type(amount: Decimal) -> None:
    result = money(amount)
    assert isinstance(result, Decimal)


@given(amount=money_amounts)
@settings(max_examples=500, suppress_health_check=[HealthCheck.too_slow])
def test_money_idempotent(amount: Decimal) -> None:
    """Applying money() twice should equal applying it once."""
    assert money(money(amount)) == money(amount)
