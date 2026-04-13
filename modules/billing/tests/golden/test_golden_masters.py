"""Golden master tests for NACHA and 835 file generation.

Each test generates a file from fixed, deterministic input and compares it
character-for-character to the stored golden master. If the format must change,
update the golden file intentionally and commit the diff for review.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

import pytest
from src.services.nacha import NACHAGenerator, NACHAPayment
from src.services.remittance_835 import (
    Remittance835Claim,
    Remittance835Generator,
    Remittance835Payment,
)

GOLDEN_DIR = Path(__file__).parent
PAYMENT_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CLAIM_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def _nacha_gen() -> NACHAGenerator:
    return NACHAGenerator(
        originator_name="InfinityRx LLC",
        company_id="1234567890",
        company_entry_description="PHARMPAY",
        originating_dfi_id="02100002",
        effective_date="260115",
    )


def _nacha_payment() -> NACHAPayment:
    return NACHAPayment(
        payment_id=PAYMENT_ID,
        amount=Decimal("1234.56"),
        routing_number="021000021",
        account_number="987654321",
        account_type="checking",
        payee_name="Test Pharmacy LLC",
        individual_id="PHR001",
    )


def _835_gen() -> Remittance835Generator:
    return Remittance835Generator(
        payer_id="INFTX",
        payer_name="InfinityRx LLC",
        production_date="20260115",
    )


def _835_payment() -> Remittance835Payment:
    return Remittance835Payment(
        payment_id=PAYMENT_ID,
        amount=Decimal("500.00"),
        payee_name="Test Pharmacy LLC",
        payee_npi="1234567890",
        claims=[
            Remittance835Claim(
                claim_id=CLAIM_ID,
                auth_number="AUTH001",
                paid_amount=Decimal("500.00"),
                patient_pay=Decimal("25.00"),
                plan_pay=Decimal("475.00"),
                ndc="12345678901",
                npi="1234567890",
                date_of_service="20260115",
            )
        ],
    )


class TestNACHAGoldenMaster:
    def test_nacha_output_matches_golden(self) -> None:
        """NACHA output must be byte-for-byte identical to the golden master."""
        gen = _nacha_gen()
        actual = gen.generate([_nacha_payment()])

        golden_path = GOLDEN_DIR / "nacha_sample.txt"
        if not golden_path.exists():
            golden_path.write_text(actual, encoding="ascii")
            pytest.skip("Golden master created — re-run tests to verify")

        expected = golden_path.read_text(encoding="ascii")
        assert actual == expected, (
            "NACHA output has changed. If intentional, update nacha_sample.txt. "
            f"First diff at char {next(i for i, (a, e) in enumerate(zip(actual, expected, strict=False)) if a != e)}"
            if actual != expected
            else ""
        )

    def test_nacha_golden_is_valid_format(self) -> None:
        """Golden NACHA file must satisfy all format invariants."""
        gen = _nacha_gen()
        output = gen.generate([_nacha_payment()])
        lines = [line for line in output.split("\n") if line]

        assert lines[0][0] == "1", "File header record type must be 1"
        assert lines[1][0] == "5", "Batch header record type must be 5"
        assert lines[2][0] == "6", "Entry detail record type must be 6"
        assert any(line[0] == "8" for line in lines), "Must have batch control record type 8"
        assert any(line[0] == "9" for line in lines), "Must have file control record type 9"
        for line in lines:
            assert len(line) == 94, f"All records must be 94 chars, got {len(line)}: {line!r}"

    def test_nacha_golden_amount_encoded_correctly(self) -> None:
        """$1234.56 must appear as 0000123456 in the entry detail record."""
        gen = _nacha_gen()
        output = gen.generate([_nacha_payment()])
        lines = [line for line in output.split("\n") if line]
        entry = next(line for line in lines if line[0] == "6")
        assert entry[29:39] == "0000123456"


class TestRemittance835GoldenMaster:
    def test_835_output_matches_golden(self) -> None:
        """835 output must be byte-for-byte identical to the golden master."""
        gen = _835_gen()
        actual = gen.generate(_835_payment())

        golden_path = GOLDEN_DIR / "835_sample.txt"
        if not golden_path.exists():
            golden_path.write_text(actual, encoding="utf-8")
            pytest.skip("Golden master created — re-run tests to verify")

        expected = golden_path.read_text(encoding="utf-8")
        assert actual == expected

    def test_835_golden_has_required_segments(self) -> None:
        """Golden 835 must contain all mandatory HIPAA segments."""
        gen = _835_gen()
        output = gen.generate(_835_payment())

        assert output.startswith("ISA"), "Must start with ISA segment"
        assert "GS*" in output, "Must contain GS segment"
        assert "ST*835*" in output, "Must contain ST*835 transaction set"
        assert "BPR*" in output, "Must contain BPR payment segment"
        assert "CLP*" in output, "Must contain CLP claim segment"
        assert "SE*" in output, "Must contain SE segment"
        assert "GE*" in output, "Must contain GE segment"
        assert "IEA*" in output, "Must contain IEA segment"

    def test_835_golden_payment_amount_present(self) -> None:
        """Payment amount $500.00 must appear in the 835 output."""
        gen = _835_gen()
        output = gen.generate(_835_payment())
        assert "500.00" in output

    def test_835_golden_auth_number_present(self) -> None:
        """AUTH001 claim auth number must appear in the 835 output."""
        gen = _835_gen()
        output = gen.generate(_835_payment())
        assert "AUTH001" in output
