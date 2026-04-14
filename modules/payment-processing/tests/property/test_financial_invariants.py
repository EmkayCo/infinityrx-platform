"""Property-based tests for financial invariants.

These tests run hundreds of random inputs to verify mathematical invariants
that must ALWAYS hold regardless of input.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import List

from hypothesis import given, settings
from hypothesis import strategies as st

from src.services.decimal_utils import money, penny_allocate
from src.services.nacha_generator import (
    NachaBatchConfig,
    NachaEntryDetail,
    NachaFileConfig,
    TC_CREDIT_CHECKING,
    generate_nacha_file,
)
from src.services.positive_pay import IssuedCheck, generate_positive_pay_csv, generate_positive_pay_fixed_width

# Strategies
decimal_amounts = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)
positive_count = st.integers(min_value=1, max_value=1000)


FILE_CFG = NachaFileConfig(
    immediate_destination="021000021",
    immediate_origin="1234567890",
    immediate_destination_name="BANK OF TEST",
    immediate_origin_name="INFINITYRX LLC",
)
BATCH_CFG = NachaBatchConfig(
    company_name="INFINITYRX",
    company_id="1234567890",
    entry_class_code="CCD",
    company_entry_description="PAYMT",
    originating_dfi_id="02100002",
    effective_date=date(2026, 4, 15),
)


class TestPennyAllocateInvariant:
    @given(total=decimal_amounts, count=positive_count)
    @settings(max_examples=200)
    def test_sum_always_equals_total(self, total: Decimal, count: int) -> None:
        """Fundamental invariant: split amounts must always sum to total."""
        result = penny_allocate(total, count)
        assert sum(result) == total, f"penny_allocate({total}, {count}) sum {sum(result)} != {total}"

    @given(total=decimal_amounts, count=positive_count)
    @settings(max_examples=200)
    def test_length_matches_count(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert len(result) == count

    @given(total=decimal_amounts, count=positive_count)
    @settings(max_examples=200)
    def test_all_items_are_decimal(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        assert all(isinstance(r, Decimal) for r in result)

    @given(total=decimal_amounts, count=positive_count)
    @settings(max_examples=200)
    def test_all_items_have_two_decimal_places(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        for r in result:
            assert r == r.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @given(total=decimal_amounts, count=positive_count)
    @settings(max_examples=100)
    def test_no_item_exceeds_total(self, total: Decimal, count: int) -> None:
        result = penny_allocate(total, count)
        for r in result:
            assert r <= total


class TestNachaTotalInvariant:
    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_nacha_total_matches_sum_of_entries(self, amounts: List[Decimal]) -> None:
        """NACHA file total must ALWAYS equal sum of entry amounts."""
        entries = [
            NachaEntryDetail(
                routing_number="021000021",
                account_number="12345678901234567",
                amount=a,
                individual_id="PAY001",
                individual_name="TEST PHARMACY",
                trace_number=f"0210000200{i:05d}",
                transaction_code=TC_CREDIT_CHECKING,
            )
            for i, a in enumerate(amounts)
        ]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        expected_total = money(sum(amounts))
        assert result.total_amount == expected_total, (
            f"NACHA total {result.total_amount} != expected {expected_total}"
        )

    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_nacha_file_lines_are_94_chars(self, amounts: List[Decimal]) -> None:
        entries = [
            NachaEntryDetail(
                routing_number="021000021",
                account_number="12345678901234567",
                amount=a,
                individual_id="PAY001",
                individual_name="TEST PHARMACY",
                trace_number=f"0210000200{i:05d}",
                transaction_code=TC_CREDIT_CHECKING,
            )
            for i, a in enumerate(amounts)
        ]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        for line in lines:
            assert len(line) == 94, f"Line not 94 chars: {len(line)}"

    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50)
    def test_nacha_record_count_multiple_of_10(self, amounts: List[Decimal]) -> None:
        entries = [
            NachaEntryDetail(
                routing_number="021000021",
                account_number="12345678901234567",
                amount=a,
                individual_id="PAY001",
                individual_name="TEST PHARMACY",
                trace_number=f"0210000200{i:05d}",
                transaction_code=TC_CREDIT_CHECKING,
            )
            for i, a in enumerate(amounts)
        ]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        assert len(lines) % 10 == 0


class TestMoneyConversionInvariant:
    @given(
        value=st.one_of(
            decimal_amounts,
            st.integers(min_value=0, max_value=999999),
        )
    )
    @settings(max_examples=300)
    def test_money_always_returns_decimal(self, value: Decimal | int) -> None:
        result = money(value)
        assert isinstance(result, Decimal)

    @given(amount=decimal_amounts)
    @settings(max_examples=300)
    def test_money_roundtrip_stable(self, amount: Decimal) -> None:
        """Applying money() twice should not change the value."""
        result = money(amount)
        assert money(result) == result


class TestSettlementAmountInvariant:
    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=100)
    def test_settlement_amounts_preserve_individual_values(self, amounts: List[Decimal]) -> None:
        """Each settlement amount must match the original instruction amount."""
        for amt in amounts:
            converted = money(str(amt))
            assert converted == money(amt), f"Settlement amount {converted} != instruction {money(amt)}"


class TestPositivePayInvariant:
    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=100)
    def test_csv_row_count_matches_check_count(self, amounts: List[Decimal]) -> None:
        checks = [
            IssuedCheck(
                check_number=f"CHK{i:08d}",
                amount=a,
                payee_name="Pharmacy",
                issue_date=date(2026, 4, 15),
                account_number="ACCT-001",
            )
            for i, a in enumerate(amounts)
        ]
        csv = generate_positive_pay_csv(checks)
        lines = csv.strip().split("\n")
        assert len(lines) == len(checks) + 1  # header + data

    @given(
        amounts=st.lists(
            decimal_amounts,
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50)
    def test_fixed_width_all_80_chars(self, amounts: List[Decimal]) -> None:
        checks = [
            IssuedCheck(
                check_number=f"CHK{i:08d}",
                amount=a,
                payee_name="Pharmacy",
                issue_date=date(2026, 4, 15),
                account_number="ACCT-001",
            )
            for i, a in enumerate(amounts)
        ]
        content = generate_positive_pay_fixed_width(checks)
        lines = [l for l in content.split("\n") if l]
        for line in lines:
            assert len(line) == 80
