"""Additional tests for validation edge cases to boost coverage."""

from __future__ import annotations

from decimal import Decimal


from src.x12.delimiters import Delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace
from src.x12.validators.validator import (
    _check_npi_luhn,
    validate_x12,
)
from datetime import datetime, timezone

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_FIXED = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_835():
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260101",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    return generate_835(req, _DELIMS, _FIXED)


def test_npi_luhn_valid():
    assert _check_npi_luhn("1234567893")


def test_npi_luhn_invalid_checksum():
    assert not _check_npi_luhn("1234567890")


def test_npi_luhn_wrong_length():
    assert not _check_npi_luhn("12345")
    assert not _check_npi_luhn("12345678901")


def test_npi_luhn_non_digits():
    assert not _check_npi_luhn("123456789X")


def test_iea_non_numeric_gs_count():
    raw = _make_835()
    corrupted = raw.replace("IEA*1*", "IEA*X*")
    result = validate_x12(corrupted)
    assert not result.is_valid
    error_codes = [e.code for e in result.errors]
    assert "L1-006" in error_codes


def test_isa_element_count_wrong():
    raw = _make_835()
    # Remove one ISA element by replacing ISA segment
    isa_end = raw.index(_DELIMS.segment)
    isa = raw[:isa_end]
    parts = isa.split(_DELIMS.element)
    short_isa = _DELIMS.element.join(parts[:10]) + _DELIMS.segment
    rest = raw[isa_end + 1:]
    corrupted = short_isa + rest
    result = validate_x12(corrupted)
    assert not result.is_valid
    error_codes = [e.code for e in result.errors]
    assert "L1-003" in error_codes


def test_st_se_pair_count_mismatch():
    raw = _make_835()
    # Add an extra ST without a matching SE
    corrupted = raw.replace("ST*835*", "ST*835*EXTRA~ST*835*")
    result = validate_x12(corrupted)
    assert not result.is_valid
