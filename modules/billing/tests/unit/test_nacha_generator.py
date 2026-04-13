"""Unit tests for NACHA file generator — format compliance."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from src.services.nacha import NACHAGenerator, NACHAPayment

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")


def _payment(
    amount: Decimal = Decimal("100.00"),
    routing: str = "021000021",
    account: str = "12345678",
    account_type: str = "checking",
    payee_name: str = "Test Pharmacy",
    individual_id: str = "ID001",
) -> NACHAPayment:
    return NACHAPayment(
        payment_id=uuid.uuid4(),
        amount=amount,
        routing_number=routing,
        account_number=account,
        account_type=account_type,
        payee_name=payee_name,
        individual_id=individual_id,
    )


class TestNACHAGenerator:
    def _gen(self) -> NACHAGenerator:
        return NACHAGenerator(
            originator_name="InfinityRx LLC",
            company_id="1234567890",
            company_entry_description="PHARMPAY",
            originating_dfi_id="02100002",
            effective_date="260115",
        )

    def test_generate_returns_string(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        assert isinstance(result, str)

    def test_file_header_record_type_1(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        lines = [l for l in result.split("\n") if l]
        assert lines[0][0] == "1"

    def test_batch_header_record_type_5(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        lines = [l for l in result.split("\n") if l]
        assert lines[1][0] == "5"

    def test_entry_detail_record_type_6(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        lines = [l for l in result.split("\n") if l]
        assert lines[2][0] == "6"

    def test_batch_control_record_type_8(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        lines = [l for l in result.split("\n") if l]
        # Second to last line before file control
        batch_ctrl = next(l for l in lines if l[0] == "8")
        assert batch_ctrl[0] == "8"

    def test_file_control_record_type_9(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        lines = [l for l in result.split("\n") if l]
        file_ctrl = next(l for l in lines if l[0] == "9")
        assert file_ctrl[0] == "9"

    def test_all_records_94_chars(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment()])
        # Do NOT strip — NACHA records have significant trailing spaces
        lines = [l for l in result.split("\n") if l]
        for line in lines:
            assert len(line) == 94, f"Record length {len(line)} != 94: {line!r}"

    def test_entry_amount_in_cents_no_decimal(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment(amount=Decimal("123.45"))])
        lines = [l for l in result.split("\n") if l]
        entry = next(l for l in lines if l[0] == "6")
        amount_field = entry[29:39]
        assert amount_field == "0000012345"

    def test_batch_total_equals_sum_of_entries(self) -> None:
        gen = self._gen()
        payments = [
            _payment(amount=Decimal("100.00"), individual_id="ID001"),
            _payment(amount=Decimal("200.00"), individual_id="ID002"),
        ]
        result = gen.generate(payments)
        lines = [l for l in result.split("\n") if l]
        batch_ctrl = next(l for l in lines if l[0] == "8")
        # Batch control positions 21-32 (0-indexed: 20:32) = total debit in cents
        total_cents = int(batch_ctrl[20:32])
        assert total_cents == 30000  # 300.00 = 30000 cents

    def test_entry_count_in_file_control(self) -> None:
        gen = self._gen()
        payments = [_payment(individual_id=f"ID{i:03d}") for i in range(3)]
        result = gen.generate(payments)
        lines = [l for l in result.split("\n") if l]
        file_ctrl = next(l for l in lines if l[0] == "9")
        # File control positions 14-21 (0-indexed: 13:21) = entry/addenda count
        entry_count = int(file_ctrl[13:21])
        assert entry_count == 3

    def test_amount_exceeding_same_day_limit_is_flagged(self) -> None:
        gen = self._gen()
        big_payment = _payment(amount=Decimal("1000001.00"))
        with pytest.raises(ValueError, match="same-day ACH limit"):
            gen.validate_same_day_limit([big_payment])

    def test_validate_same_day_limit_passes_for_valid_amount(self) -> None:
        gen = self._gen()
        valid_payment = _payment(amount=Decimal("999999.00"))
        gen.validate_same_day_limit([valid_payment])  # should not raise

    def test_routing_number_hash_in_batch_control(self) -> None:
        gen = self._gen()
        result = gen.generate([_payment(routing="021000021")])
        lines = [l for l in result.split("\n") if l]
        batch_ctrl = next(l for l in lines if l[0] == "8")
        # Batch control: pos 11-20 (0-indexed: 10:20) = entry hash
        routing_hash = batch_ctrl[10:20]
        # "02100002" -> 2100002, zfill(10) -> "0002100002"
        assert routing_hash == "0002100002"
