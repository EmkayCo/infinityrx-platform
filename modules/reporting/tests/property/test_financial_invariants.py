"""Property-based tests for financial report invariants.

These tests use Hypothesis to verify that financial calculations hold
for any valid input — not just the cases we manually wrote.

CRITICAL: report totals must equal journal totals penny-perfect for any input.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from hypothesis import given
from hypothesis import strategies as st
from src.services.financial import (
    calculate_ar_aging_buckets,
    calculate_cash_flow,
    calculate_prefund_burn_rate,
    calculate_program_financial_summary,
    money,
    penny_allocate,
)

# Strategy for valid monetary amounts (2 decimal places, positive)
monetary_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

non_negative_monetary = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("9999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


@given(total=monetary_amount, count=st.integers(min_value=1, max_value=1000))
def test_penny_allocate_always_sums_to_total(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert sum(result) == total, f"Sum mismatch: {sum(result)} != {total} for count={count}"


@given(total=monetary_amount, count=st.integers(min_value=1, max_value=1000))
def test_penny_allocate_correct_length(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert len(result) == count


@given(total=monetary_amount, count=st.integers(min_value=1, max_value=1000))
def test_penny_allocate_all_results_are_decimal(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert all(isinstance(r, Decimal) for r in result)


@given(total=monetary_amount, count=st.integers(min_value=1, max_value=1000))
def test_penny_allocate_no_result_exceeds_total(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    assert all(r <= total for r in result)


@given(total=monetary_amount, count=st.integers(min_value=2, max_value=1000))
def test_penny_allocate_first_item_gets_remainder(total: Decimal, count: int) -> None:
    result = penny_allocate(total, count)
    per_item = (total / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # All items except first should equal per_item (first may have +/- 0.01 for remainder)
    for item in result[1:]:
        assert item == per_item


@given(
    value=st.one_of(
        st.integers(min_value=0, max_value=1_000_000),
        monetary_amount,
        st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False),
    )
)
def test_money_always_returns_decimal_with_2_places(value: object) -> None:
    result = money(value)
    assert isinstance(result, Decimal)
    assert result == result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@given(value=monetary_amount)
def test_money_roundtrip_no_float_contamination(value: Decimal) -> None:
    result = money(value)
    assert result == value  # monetary_amount already has 2 places


@given(
    amounts=st.lists(monetary_amount, min_size=0, max_size=100),
    fees=st.lists(monetary_amount, min_size=0, max_size=100),
    recoveries=st.lists(monetary_amount, min_size=0, max_size=100),
)
def test_program_financial_totals_are_additive(
    amounts: list[Decimal], fees: list[Decimal], recoveries: list[Decimal]
) -> None:
    n = min(len(amounts), len(fees), len(recoveries))
    claims = [
        {"amount_paid": amounts[i], "fee": fees[i], "recovery": recoveries[i]} for i in range(n)
    ]
    result = calculate_program_financial_summary(claims)
    expected_spend = sum(amounts[:n])
    expected_fees = sum(fees[:n])
    expected_recoveries = sum(recoveries[:n])
    assert result["total_spend"] == expected_spend
    assert result["total_fees"] == expected_fees
    assert result["total_recoveries"] == expected_recoveries
    assert result["net_spend"] == expected_spend - expected_recoveries


@given(
    invoices_data=st.lists(
        st.tuples(
            monetary_amount,
            st.integers(min_value=0, max_value=200),  # days overdue
        ),
        min_size=0,
        max_size=50,
    )
)
def test_ar_aging_bucket_totals_equal_invoice_sum(invoices_data: list[tuple[Decimal, int]]) -> None:
    today = date(2026, 1, 15)
    invoices = [
        {"id": f"inv{i}", "amount_due": amt, "due_date": today - timedelta(days=days)}
        for i, (amt, days) in enumerate(invoices_data)
    ]
    result = calculate_ar_aging_buckets(invoices, today)
    bucket_total = sum(result.values())
    expected_total = sum(amt for amt, _ in invoices_data)
    assert bucket_total == expected_total, (
        f"Bucket total {bucket_total} != invoice sum {expected_total}"
    )


@given(ap=non_negative_monetary, ar=non_negative_monetary)
def test_cash_flow_net_is_ar_minus_ap(ap: Decimal, ar: Decimal) -> None:
    result = calculate_cash_flow(ap, ar)
    assert result["net"] == ar - ap
    assert result["ap_out"] == ap
    assert result["ar_in"] == ar


@given(
    total_spend=monetary_amount,
    days=st.integers(min_value=1, max_value=365),
)
def test_burn_rate_times_days_equals_total(total_spend: Decimal, days: int) -> None:
    rate = calculate_prefund_burn_rate(total_spend, days)
    # rate * days should approximately equal total_spend (within 1 penny per day due to rounding)
    reconstructed = rate * days
    diff = abs(reconstructed - total_spend)
    assert diff <= Decimal(str(days)) * Decimal("0.01"), (
        f"Burn rate reconstruction off by {diff} for total={total_spend}, days={days}"
    )
