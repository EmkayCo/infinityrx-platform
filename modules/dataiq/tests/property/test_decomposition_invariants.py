"""Property-based tests for drug trend decomposition.

The invariant util + price + mix == total_delta must hold for ALL inputs.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st
from src.services.trend_decomposition import decompose_drug_trend


def decimal_strategy(min_val: str = "0", max_val: str = "1000000") -> st.SearchStrategy:
    return st.decimals(
        min_value=Decimal(min_val),
        max_value=Decimal(max_val),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )


@given(
    q_old=decimal_strategy("0", "100000"),
    q_new=decimal_strategy("0", "100000"),
    p_old=decimal_strategy("0.01", "10000"),
    p_new=decimal_strategy("0.01", "10000"),
)
@settings(max_examples=500)
def test_decomposition_components_always_sum_to_total(
    q_old: Decimal,
    q_new: Decimal,
    p_old: Decimal,
    p_new: Decimal,
) -> None:
    result = decompose_drug_trend(q_old=q_old, q_new=q_new, p_old=p_old, p_new=p_new)
    component_sum = result.utilization_effect + result.price_effect + result.mix_effect
    assert component_sum == result.total_delta, (
        f"Decomposition invariant violated: "
        f"util={result.utilization_effect} + price={result.price_effect} + mix={result.mix_effect} "
        f"= {component_sum} != total_delta={result.total_delta}"
    )


@given(
    q_old=decimal_strategy("0", "100000"),
    q_new=decimal_strategy("0", "100000"),
    p_old=decimal_strategy("0.01", "10000"),
    p_new=decimal_strategy("0.01", "10000"),
)
@settings(max_examples=500)
def test_total_delta_equals_new_minus_old_spend(
    q_old: Decimal,
    q_new: Decimal,
    p_old: Decimal,
    p_new: Decimal,
) -> None:
    result = decompose_drug_trend(q_old=q_old, q_new=q_new, p_old=p_old, p_new=p_new)
    expected_delta = (q_new * p_new) - (q_old * p_old)
    assert result.total_delta == expected_delta


@given(
    q=decimal_strategy("1", "100000"),
    p_old=decimal_strategy("0.01", "10000"),
    p_new=decimal_strategy("0.01", "10000"),
)
@settings(max_examples=200)
def test_same_quantity_has_zero_utilization_and_mix_effects(
    q: Decimal,
    p_old: Decimal,
    p_new: Decimal,
) -> None:
    result = decompose_drug_trend(q_old=q, q_new=q, p_old=p_old, p_new=p_new)
    assert result.utilization_effect == Decimal("0")
    assert result.mix_effect == Decimal("0")


@given(
    q_old=decimal_strategy("1", "100000"),
    q_new=decimal_strategy("1", "100000"),
    p=decimal_strategy("0.01", "10000"),
)
@settings(max_examples=200)
def test_same_price_has_zero_price_and_mix_effects(
    q_old: Decimal,
    q_new: Decimal,
    p: Decimal,
) -> None:
    result = decompose_drug_trend(q_old=q_old, q_new=q_new, p_old=p, p_new=p)
    assert result.price_effect == Decimal("0")
    assert result.mix_effect == Decimal("0")


@given(
    q_old=decimal_strategy("0", "100000"),
    q_new=decimal_strategy("0", "100000"),
    p_old=decimal_strategy("0.01", "10000"),
    p_new=decimal_strategy("0.01", "10000"),
)
@settings(max_examples=500)
def test_all_components_are_decimal_type(
    q_old: Decimal,
    q_new: Decimal,
    p_old: Decimal,
    p_new: Decimal,
) -> None:
    result = decompose_drug_trend(q_old=q_old, q_new=q_new, p_old=p_old, p_new=p_new)
    assert isinstance(result.utilization_effect, Decimal)
    assert isinstance(result.price_effect, Decimal)
    assert isinstance(result.mix_effect, Decimal)
    assert isinstance(result.total_delta, Decimal)
    assert not isinstance(result.utilization_effect, float)
    assert not isinstance(result.price_effect, float)
    assert not isinstance(result.mix_effect, float)
    assert not isinstance(result.total_delta, float)
