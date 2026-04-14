"""Unit tests for NACHA file generator — financial path, 100% coverage."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.services.nacha_generator import (
    NachaBatchConfig,
    NachaEntryDetail,
    NachaFileConfig,
    TC_CREDIT_CHECKING,
    generate_nacha_file,
)

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


def _make_entry(amount: Decimal, routing: str = "021000021", acct: str = "12345678901234567") -> NachaEntryDetail:
    return NachaEntryDetail(
        routing_number=routing,
        account_number=acct,
        amount=amount,
        individual_id="PAY001",
        individual_name="TEST PHARMACY LLC",
        trace_number="021000020000001",
        transaction_code=TC_CREDIT_CHECKING,
    )


class TestNachaFileGeneration:
    def test_generates_file_with_single_entry(self):
        entries = [_make_entry(Decimal("100.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        assert result.total_amount == Decimal("100.00")
        assert result.entry_count == 1
        assert result.batch_count == 1

    def test_file_content_is_94_char_lines(self):
        entries = [_make_entry(Decimal("50.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = result.file_content.strip().split("\n")
        for line in lines:
            if line:
                assert len(line) == 94, f"Line length {len(line)} != 94: {line!r}"

    def test_file_length_is_multiple_of_10_records(self):
        entries = [_make_entry(Decimal("100.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        assert len(lines) % 10 == 0

    def test_total_matches_sum_of_entries(self):
        amounts = [Decimal("100.00"), Decimal("200.50"), Decimal("75.25")]
        entries = [_make_entry(a) for a in amounts]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        expected = sum(amounts)
        assert result.total_amount == expected

    def test_empty_entries_raises(self):
        with pytest.raises(ValueError, match="no entries"):
            generate_nacha_file(FILE_CFG, BATCH_CFG, [])

    def test_file_header_starts_with_1(self):
        entries = [_make_entry(Decimal("10.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        first_line = result.file_content.split("\n")[0]
        assert first_line[0] == "1"

    def test_batch_header_starts_with_5(self):
        entries = [_make_entry(Decimal("10.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = result.file_content.split("\n")
        assert lines[1][0] == "5"

    def test_entry_detail_starts_with_6(self):
        entries = [_make_entry(Decimal("10.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = result.file_content.split("\n")
        assert lines[2][0] == "6"

    def test_batch_control_starts_with_8(self):
        entries = [_make_entry(Decimal("10.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        batch_control = next(l for l in lines if l[0] == "8")
        assert batch_control is not None

    def test_file_control_starts_with_9(self):
        entries = [_make_entry(Decimal("10.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        file_control = next(l for l in lines if l[0] == "9" and not all(c == "9" for c in l))
        assert file_control is not None

    def test_no_float_in_amounts(self):
        entries = [_make_entry(Decimal("1234567.89"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        assert isinstance(result.total_amount, Decimal)

    def test_result_has_file_hash(self):
        entries = [_make_entry(Decimal("50.00"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        assert len(result.file_hash) == 16

    def test_addenda_increases_entry_addenda_count(self):
        entry = NachaEntryDetail(
            routing_number="021000021",
            account_number="12345678901234567",
            amount=Decimal("100.00"),
            individual_id="PAY001",
            individual_name="TEST PHARMACY LLC",
            trace_number="021000020000001",
            transaction_code=TC_CREDIT_CHECKING,
            addenda_info="REFERENCE:INV-2026-001",
        )
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, [entry])
        assert result.entry_addenda_count == 2  # 1 entry + 1 addenda

    def test_ten_entries_gives_20_or_30_record_file(self):
        entries = [_make_entry(Decimal("100.00")) for _ in range(10)]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        lines = [l for l in result.file_content.split("\n") if l]
        assert len(lines) % 10 == 0

    def test_penny_amounts_preserved(self):
        entries = [_make_entry(Decimal("0.01"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        assert result.total_amount == Decimal("0.01")

    def test_max_amount_preserved(self):
        entries = [_make_entry(Decimal("9999999.99"))]
        result = generate_nacha_file(FILE_CFG, BATCH_CFG, entries)
        assert result.total_amount == Decimal("9999999.99")
