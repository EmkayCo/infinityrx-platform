"""Unit tests for positive pay file generator."""
from __future__ import annotations

from datetime import date
from decimal import Decimal


from src.services.positive_pay import IssuedCheck, generate_positive_pay_csv, generate_positive_pay_fixed_width


def _check(n: int = 1) -> IssuedCheck:
    return IssuedCheck(
        check_number=f"CHK{str(n).zfill(8)}",
        amount=Decimal("500.00"),
        payee_name="Test Pharmacy",
        issue_date=date(2026, 4, 15),
        account_number="ACCT-123456",
        reference=f"INV-{n:04d}",
    )


class TestPositivePayCsv:
    def test_generates_header_and_rows(self):
        checks = [_check(1), _check(2)]
        csv = generate_positive_pay_csv(checks)
        lines = csv.strip().split("\n")
        assert lines[0].startswith("check_number")
        assert len(lines) == 3  # header + 2 checks

    def test_amount_is_decimal_string(self):
        csv = generate_positive_pay_csv([_check()])
        lines = csv.strip().split("\n")
        assert "500.00" in lines[1]

    def test_empty_checks_returns_header_only(self):
        csv = generate_positive_pay_csv([])
        lines = csv.strip().split("\n")
        assert len(lines) == 1

    def test_no_float_values(self):
        chk = _check()
        assert isinstance(chk.amount, Decimal)


class TestPositivePayFixedWidth:
    def test_records_are_80_chars(self):
        checks = [_check(1), _check(2)]
        content = generate_positive_pay_fixed_width(checks)
        lines = [l for l in content.split("\n") if l]
        for line in lines:
            assert len(line) == 80, f"Expected 80, got {len(line)}: {line!r}"

    def test_check_number_in_record(self):
        content = generate_positive_pay_fixed_width([_check(1)])
        assert "CHK00000001" in content

    def test_empty_returns_empty_content(self):
        content = generate_positive_pay_fixed_width([])
        assert content == "\n"
