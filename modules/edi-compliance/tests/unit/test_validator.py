"""Tests for the 4-level X12 validation engine."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.x12.delimiters import Delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.gen_837p import generate_837p
from src.x12.generators.schemas import (
    ClpClaim,
    Generate835Request,
    Generate837PRequest,
    N1Party,
    TrnTrace,
)
from src.x12.validators.validator import (
    ValidationLevel,
    validate_835_basic,
    validate_x12,
)

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_835_raw() -> str:
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT001",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT001", payer_id="PAYER001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    return generate_835(req, _DELIMS)


def test_valid_835_passes_all_levels():
    raw = _make_835_raw()
    result = validate_x12(raw)
    assert result.is_valid, f"Errors: {[e.message for e in result.errors]}"


def test_missing_isa_fails_syntax():
    result = validate_x12("GS*HC*~SE*1*0001~GE*1*1~IEA*1*000000001~")
    assert not result.is_valid
    assert any(e.level == ValidationLevel.SYNTAX for e in result.errors)


def test_control_number_mismatch_fails_syntax():
    raw = _make_835_raw()
    # Replace IEA control number with wrong value
    corrupted = raw.replace("IEA*1*000000001~", "IEA*1*000000999~")
    result = validate_x12(corrupted)
    assert not result.is_valid
    error_codes = [e.code for e in result.errors]
    assert "L1-007" in error_codes


def test_gs_ge_mismatch_fails_syntax():
    raw = _make_835_raw()
    # Add an extra GS segment — GS/GE count will be off
    corrupted = raw.replace("GS*HP*", "GS*HP*EXTRA~GS*HP*")
    result = validate_x12(corrupted)
    assert not result.is_valid


def test_missing_bpr_fails_ig_validation():
    raw = _make_835_raw()
    # Remove BPR segment
    lines = [seg for seg in raw.split("~") if not seg.strip().startswith("BPR")]
    corrupted = "~".join(lines) + "~"
    errors = validate_835_basic(corrupted, _DELIMS)
    assert any("BPR" in e for e in errors)


def test_invalid_npi_fails_business_validation():
    """NPI that fails Luhn check must be flagged at L3."""
    # Build an 837P with an invalid NPI
    req = Generate837PRequest(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        receiver_id="PAYER001       ",
        test_mode=True,
        implementation_guide="005010X222A2",
        billing_provider_npi="0000000000",   # invalid NPI (Luhn fail)
        billing_provider_name="TEST PROVIDER",
        billing_provider_ein="123456789",
        subscriber_id="MEM001",
        subscriber_last_name="DOE",
        subscriber_first_name="JANE",
        subscriber_dob="19800101",
        subscriber_gender="F",
        payer_id="PAYER001",
        payer_name="TEST PAYER",
        claims=[],
    )
    # generate will call validate — it might raise, or the result will have errors
    try:
        raw = generate_837p(req, _DELIMS)
        result = validate_x12(raw)
        # If generation succeeded, validation should catch bad NPI
        npi_errors = [e for e in result.errors if e.code == "L3-001"]
        assert npi_errors, "Invalid NPI should be caught at L3"
    except ValueError:
        pass  # Generation itself rejected the invalid NPI — acceptable


def test_valid_npi_passes():
    """1234567893 passes Luhn check."""
    req = Generate837PRequest(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        receiver_id="PAYER001       ",
        test_mode=True,
        implementation_guide="005010X222A2",
        billing_provider_npi="1234567893",   # valid NPI
        billing_provider_name="TEST PROVIDER",
        billing_provider_ein="123456789",
        subscriber_id="MEM001",
        subscriber_last_name="DOE",
        subscriber_first_name="JANE",
        subscriber_dob="19800101",
        subscriber_gender="F",
        payer_id="PAYER001",
        payer_name="TEST PAYER",
        claims=[
            {
                "claim_id": "CLM001",
                "charge_amount": "100.00",
                "facility_code": "11",
                "claim_frequency": "1",
                "service_lines": [
                    {"procedure_code": "99213", "charge_amount": "100.00", "units": "1",
                     "place_of_service": "11", "date_of_service": "20260101"}
                ],
            }
        ],
    )
    raw = generate_837p(req, _DELIMS)
    result = validate_x12(raw)
    npi_errors = [e for e in result.errors if e.code == "L3-001"]
    assert npi_errors == []


def test_too_short_content_returns_syntax_error():
    result = validate_x12("short")
    assert not result.is_valid


def test_se_count_mismatch_fails():
    raw = _make_835_raw()
    # Replace SE segment count with a wrong value
    from src.x12.segments import parse_segments
    segs = parse_segments(raw, _DELIMS)
    se_seg = next(s for s in segs if s[0] == "SE")
    correct_count = int(se_seg[1])
    corrupted = raw.replace(f"SE*{correct_count}*", f"SE*{correct_count + 5}*")
    result = validate_x12(corrupted)
    assert not result.is_valid
    assert any(e.code == "L1-009" for e in result.errors)
