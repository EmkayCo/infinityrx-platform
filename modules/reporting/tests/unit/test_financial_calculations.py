"""Unit tests for financial calculation services.

Written FIRST (TDD) — these define the expected behavior before implementation.
100% coverage required on all financial logic.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from src.services.financial import (
    calculate_ar_aging_buckets,
    calculate_cash_flow,
    calculate_client_profitability,
    calculate_prefund_burn_rate,
    calculate_prefund_projection,
    calculate_program_financial_summary,
    calculate_spread_pricing,
    money,
    penny_allocate,
)


class TestMoney:
    def test_converts_int_to_decimal(self) -> None:
        assert money(100) == Decimal("100.00")

    def test_converts_float_string_to_decimal(self) -> None:
        assert money("99.999") == Decimal("100.00")

    def test_rounds_half_up(self) -> None:
        assert money("0.005") == Decimal("0.01")

    def test_rounds_down(self) -> None:
        assert money("0.004") == Decimal("0.00")

    def test_returns_decimal_unchanged(self) -> None:
        d = Decimal("42.50")
        assert money(d) == d

    def test_negative_value(self) -> None:
        assert money("-10.50") == Decimal("-10.50")

    def test_zero(self) -> None:
        assert money(0) == Decimal("0.00")

    def test_large_value(self) -> None:
        assert money("999999999.999") == Decimal("1000000000.00")

    def test_result_is_decimal_type(self) -> None:
        result = money(1)
        assert isinstance(result, Decimal)

    def test_no_float_contamination(self) -> None:
        result = money("0.1")
        assert result == Decimal("0.10")
        assert str(result) == "0.10"


class TestPennyAllocate:
    def test_even_split(self) -> None:
        result = penny_allocate(Decimal("100.00"), 4)
        assert result == [Decimal("25.00")] * 4
        assert sum(result) == Decimal("100.00")

    def test_remainder_goes_to_first(self) -> None:
        result = penny_allocate(Decimal("100.00"), 3)
        assert result[0] == Decimal("33.34")
        assert result[1] == Decimal("33.33")
        assert result[2] == Decimal("33.33")
        assert sum(result) == Decimal("100.00")

    def test_single_item(self) -> None:
        result = penny_allocate(Decimal("42.17"), 1)
        assert result == [Decimal("42.17")]

    def test_zero_count_returns_empty(self) -> None:
        result = penny_allocate(Decimal("100.00"), 0)
        assert result == []

    def test_sum_always_equals_total(self) -> None:
        for total_cents in range(1, 101):
            total = Decimal(str(total_cents)) / 100
            for count in range(1, 21):
                result = penny_allocate(total, count)
                assert sum(result) == total, f"Failed for total={total}, count={count}"

    def test_all_results_are_decimal(self) -> None:
        result = penny_allocate(Decimal("50.00"), 7)
        assert all(isinstance(r, Decimal) for r in result)

    def test_one_cent_among_many(self) -> None:
        result = penny_allocate(Decimal("0.01"), 5)
        assert sum(result) == Decimal("0.01")
        assert result[0] == Decimal("0.01")
        assert result[1:] == [Decimal("0.00")] * 4

    def test_large_split(self) -> None:
        total = Decimal("1000000.00")
        result = penny_allocate(total, 1000)
        assert sum(result) == total
        assert len(result) == 1000


class TestArAgingBuckets:
    def test_current_invoice_in_0_30(self) -> None:
        today = date.today()
        invoices = [
            {"id": "inv1", "amount_due": Decimal("500.00"), "due_date": today - timedelta(days=15)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        assert result["0_30"] == Decimal("500.00")
        assert result["31_60"] == Decimal("0.00")
        assert result["61_90"] == Decimal("0.00")
        assert result["91_120"] == Decimal("0.00")
        assert result["121_plus"] == Decimal("0.00")

    def test_overdue_30_days_in_31_60(self) -> None:
        today = date.today()
        invoices = [
            {"id": "inv1", "amount_due": Decimal("300.00"), "due_date": today - timedelta(days=45)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        assert result["0_30"] == Decimal("0.00")
        assert result["31_60"] == Decimal("300.00")

    def test_multiple_invoices_across_buckets(self) -> None:
        today = date.today()
        invoices = [
            {"id": "i1", "amount_due": Decimal("100.00"), "due_date": today - timedelta(days=5)},
            {"id": "i2", "amount_due": Decimal("200.00"), "due_date": today - timedelta(days=35)},
            {"id": "i3", "amount_due": Decimal("300.00"), "due_date": today - timedelta(days=65)},
            {"id": "i4", "amount_due": Decimal("400.00"), "due_date": today - timedelta(days=95)},
            {"id": "i5", "amount_due": Decimal("500.00"), "due_date": today - timedelta(days=125)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        assert result["0_30"] == Decimal("100.00")
        assert result["31_60"] == Decimal("200.00")
        assert result["61_90"] == Decimal("300.00")
        assert result["91_120"] == Decimal("400.00")
        assert result["121_plus"] == Decimal("500.00")

    def test_total_equals_sum_of_buckets(self) -> None:
        today = date.today()
        invoices = [
            {"id": "i1", "amount_due": Decimal("111.11"), "due_date": today - timedelta(days=5)},
            {"id": "i2", "amount_due": Decimal("222.22"), "due_date": today - timedelta(days=50)},
            {"id": "i3", "amount_due": Decimal("333.33"), "due_date": today - timedelta(days=150)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        bucket_total = sum(
            [result["0_30"], result["31_60"], result["61_90"], result["91_120"], result["121_plus"]]
        )
        assert bucket_total == Decimal("666.66")

    def test_boundary_exactly_30_days(self) -> None:
        today = date.today()
        invoices = [
            {"id": "i1", "amount_due": Decimal("100.00"), "due_date": today - timedelta(days=30)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        assert result["0_30"] == Decimal("100.00")

    def test_boundary_exactly_31_days(self) -> None:
        today = date.today()
        invoices = [
            {"id": "i1", "amount_due": Decimal("100.00"), "due_date": today - timedelta(days=31)},
        ]
        result = calculate_ar_aging_buckets(invoices, today)
        assert result["31_60"] == Decimal("100.00")

    def test_empty_invoice_list(self) -> None:
        today = date.today()
        result = calculate_ar_aging_buckets([], today)
        assert all(v == Decimal("0.00") for v in result.values())

    def test_all_results_are_decimal(self) -> None:
        today = date.today()
        result = calculate_ar_aging_buckets([], today)
        assert all(isinstance(v, Decimal) for v in result.values())


class TestPrefundCalculations:
    def test_burn_rate_daily(self) -> None:
        total_spend = Decimal("30000.00")
        days = 30
        rate = calculate_prefund_burn_rate(total_spend, days)
        assert rate == Decimal("1000.00")

    def test_burn_rate_rounds_half_up(self) -> None:
        rate = calculate_prefund_burn_rate(Decimal("100.00"), 3)
        assert rate == Decimal("33.33")

    def test_burn_rate_zero_days_raises(self) -> None:
        with pytest.raises(ValueError, match="days must be positive"):
            calculate_prefund_burn_rate(Decimal("100.00"), 0)

    def test_projection_days_remaining(self) -> None:
        balance = Decimal("10000.00")
        daily_burn = Decimal("500.00")
        days = calculate_prefund_projection(balance, daily_burn)
        assert days == 20

    def test_projection_zero_burn_raises(self) -> None:
        with pytest.raises(ValueError, match="daily_burn must be positive"):
            calculate_prefund_projection(Decimal("10000.00"), Decimal("0.00"))

    def test_projection_zero_balance(self) -> None:
        days = calculate_prefund_projection(Decimal("0.00"), Decimal("100.00"))
        assert days == 0

    def test_prefund_balance_after_equals_before_minus_spend(self) -> None:
        before = Decimal("50000.00")
        spend = Decimal("15000.00")
        after = before - spend
        assert after == Decimal("35000.00")
        assert after + spend == before


class TestCashFlow:
    def test_net_cash_flow_is_ar_minus_ap(self) -> None:
        ap_total = Decimal("80000.00")
        ar_total = Decimal("95000.00")
        result = calculate_cash_flow(ap_total, ar_total)
        assert result["net"] == Decimal("15000.00")
        assert result["ap_out"] == Decimal("80000.00")
        assert result["ar_in"] == Decimal("95000.00")

    def test_negative_net_when_ap_exceeds_ar(self) -> None:
        result = calculate_cash_flow(Decimal("100.00"), Decimal("80.00"))
        assert result["net"] == Decimal("-20.00")

    def test_zero_values(self) -> None:
        result = calculate_cash_flow(Decimal("0.00"), Decimal("0.00"))
        assert result["net"] == Decimal("0.00")

    def test_all_results_are_decimal(self) -> None:
        result = calculate_cash_flow(Decimal("100.00"), Decimal("200.00"))
        assert all(isinstance(v, Decimal) for v in result.values())


class TestSpreadPricing:
    def test_spread_is_plan_paid_minus_pharmacy_paid(self) -> None:
        plan_paid = Decimal("100.00")
        pharmacy_paid = Decimal("85.00")
        spread = calculate_spread_pricing(plan_paid, pharmacy_paid)
        assert spread["spread"] == Decimal("15.00")
        assert spread["spread_pct"] == Decimal("15.00")

    def test_zero_spread(self) -> None:
        spread = calculate_spread_pricing(Decimal("100.00"), Decimal("100.00"))
        assert spread["spread"] == Decimal("0.00")
        assert spread["spread_pct"] == Decimal("0.00")

    def test_spread_pct_rounds_half_up(self) -> None:
        # 1/3 = 33.333...% → rounds to 33.33%
        spread = calculate_spread_pricing(Decimal("3.00"), Decimal("2.00"))
        assert spread["spread_pct"] == Decimal("33.33")

    def test_zero_plan_paid_raises(self) -> None:
        with pytest.raises(ValueError, match="plan_paid must be positive"):
            calculate_spread_pricing(Decimal("0.00"), Decimal("85.00"))

    def test_all_decimal(self) -> None:
        result = calculate_spread_pricing(Decimal("200.00"), Decimal("150.00"))
        assert all(isinstance(v, Decimal) for v in result.values())


class TestClientProfitability:
    def test_profit_is_fees_minus_costs(self) -> None:
        fees = Decimal("50000.00")
        costs = Decimal("32000.00")
        result = calculate_client_profitability(fees, costs)
        assert result["profit"] == Decimal("18000.00")
        assert result["margin_pct"] == Decimal("36.00")

    def test_negative_margin_when_costs_exceed_fees(self) -> None:
        result = calculate_client_profitability(Decimal("10000.00"), Decimal("12000.00"))
        assert result["profit"] == Decimal("-2000.00")

    def test_zero_fees_raises(self) -> None:
        with pytest.raises(ValueError, match="fees must be positive"):
            calculate_client_profitability(Decimal("0.00"), Decimal("1000.00"))

    def test_result_is_decimal(self) -> None:
        result = calculate_client_profitability(Decimal("100.00"), Decimal("60.00"))
        assert all(isinstance(v, Decimal) for v in result.values())


class TestProgramFinancialSummary:
    def test_summary_totals_are_correct(self) -> None:
        claims = [
            {"amount_paid": Decimal("100.00"), "fee": Decimal("5.00"), "recovery": Decimal("0.00")},
            {
                "amount_paid": Decimal("200.00"),
                "fee": Decimal("10.00"),
                "recovery": Decimal("15.00"),
            },
            {
                "amount_paid": Decimal("300.00"),
                "fee": Decimal("15.00"),
                "recovery": Decimal("0.00"),
            },
        ]
        result = calculate_program_financial_summary(claims)
        assert result["total_spend"] == Decimal("600.00")
        assert result["total_fees"] == Decimal("30.00")
        assert result["total_recoveries"] == Decimal("15.00")
        assert result["net_spend"] == Decimal("585.00")

    def test_empty_claims_returns_zeros(self) -> None:
        result = calculate_program_financial_summary([])
        assert result["total_spend"] == Decimal("0.00")
        assert result["total_fees"] == Decimal("0.00")
        assert result["total_recoveries"] == Decimal("0.00")
        assert result["net_spend"] == Decimal("0.00")

    def test_all_results_are_decimal(self) -> None:
        result = calculate_program_financial_summary([])
        assert all(isinstance(v, Decimal) for v in result.values())
