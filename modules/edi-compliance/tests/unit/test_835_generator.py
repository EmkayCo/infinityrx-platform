"""Tests for the 835 remittance advice generator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.x12.delimiters import Delimiters, detect_delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import (
    CasAdjustment,
    ClpClaim,
    Generate835Request,
    N1Party,
    SvcLine,
    TrnTrace,
)
from src.x12.validators.validator import validate_835_basic

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_request(**kwargs) -> Generate835Request:
    defaults = dict(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=1,
        gs_control_number=1,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("150.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT123456",
        payer=N1Party(entity_qualifier="PR", name="INFINITYRX HEALTH", id_qualifier="PI", id_code="12345"),
        payee=N1Party(entity_qualifier="PE", name="GOOD PHARMACY", id_qualifier="XX", id_code="1234567890"),
        trace=TrnTrace(check_eft_number="EFT123456", payer_id="1234567890"),
        claims=[
            ClpClaim(
                claim_id="CLM001",
                status_code="1",
                charge_amount=Decimal("100.00"),
                paid_amount=Decimal("85.00"),
                patient_responsibility=Decimal("15.00"),
                claim_filing_indicator="HM",
                adjustments=[
                    CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("15.00"))
                ],
                service_lines=[
                    SvcLine(
                        procedure_code="12345678901",
                        procedure_qualifier="N4",
                        charge_amount=Decimal("100.00"),
                        paid_amount=Decimal("85.00"),
                        ndc="12345678901",
                        rx_number="RX00001",
                    )
                ],
            ),
            ClpClaim(
                claim_id="CLM002",
                status_code="1",
                charge_amount=Decimal("80.00"),
                paid_amount=Decimal("65.00"),
                patient_responsibility=Decimal("15.00"),
                claim_filing_indicator="HM",
            ),
        ],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    defaults.update(kwargs)
    return Generate835Request(**defaults)


def test_835_generates_valid_x12():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    assert isinstance(result, str)
    assert result.startswith("ISA")
    assert result.endswith("~")


def test_835_contains_required_segments():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    for seg in ["ISA", "GS", "ST", "BPR", "TRN", "N1", "CLP", "SE", "GE", "IEA"]:
        assert seg in result, f"Missing required segment: {seg}"


def test_835_isa06_is_15_chars():
    """ISA06 must always be exactly 15 characters (PRD §3.18)."""
    req = _make_request(sender_id="INFINITYRX     ")
    result = generate_835(req, _DELIMS)
    # Parse ISA manually — split on element separator
    isa_end = result.index(_DELIMS.segment)
    isa_raw = result[:isa_end]
    parts = isa_raw.split(_DELIMS.element)
    isa06 = parts[6]
    assert len(isa06) == 15, f"ISA06 must be 15 chars, got {len(isa06)}: {isa06!r}"


def test_835_isa08_is_15_chars():
    """ISA08 must always be exactly 15 characters (PRD §3.18)."""
    req = _make_request()
    result = generate_835(req, _DELIMS)
    isa_end = result.index(_DELIMS.segment)
    isa_raw = result[:isa_end]
    parts = isa_raw.split(_DELIMS.element)
    isa08 = parts[8]
    assert len(isa08) == 15, f"ISA08 must be 15 chars, got {len(isa08)}: {isa08!r}"


def test_835_isa13_is_9_digits():
    req = _make_request(isa_control_number=42)
    result = generate_835(req, _DELIMS)
    isa_end = result.index(_DELIMS.segment)
    parts = result[:isa_end].split(_DELIMS.element)
    isa13 = parts[13]
    assert isa13 == "000000042"
    assert len(isa13) == 9


def test_835_passes_validation():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    errors = validate_835_basic(result, _DELIMS)
    assert errors == [], f"Validation errors: {errors}"


def test_835_amounts_are_decimal():
    """All amounts must be formatted with exactly 2 decimal places."""
    req = _make_request(payment_amount=Decimal("999.99"))
    result = generate_835(req, _DELIMS)
    assert "999.99" in result


def test_835_clp_segments_present():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    assert result.count("CLP*") == 2


def test_835_cas_segment_present():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    assert "CAS*CO*45*15.00" in result


def test_835_svc_segment_with_ndc():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    assert "SVC*" in result
    assert "N4" in result


def test_835_ref_rx_number():
    req = _make_request()
    result = generate_835(req, _DELIMS)
    assert "REF*1D*RX00001" in result


def test_835_iea_isa_control_match():
    req = _make_request(isa_control_number=77)
    result = generate_835(req, _DELIMS)
    assert "IEA*1*000000077" in result


def test_835_se_segment_count_correct():
    """SE01 segment count must equal actual number of segments from ST through SE."""
    req = _make_request()
    result = generate_835(req, _DELIMS)
    from src.x12.segments import parse_segments
    segs = parse_segments(result, _DELIMS)
    st_idx = next(i for i, s in enumerate(segs) if s[0] == "ST")
    se_idx = next(i for i, s in enumerate(segs) if s[0] == "SE")
    expected_count = se_idx - st_idx + 1
    se_seg = segs[se_idx]
    assert int(se_seg[1]) == expected_count, (
        f"SE01={se_seg[1]} but actual count from ST to SE = {expected_count}"
    )


def test_835_test_mode_indicator():
    req = _make_request(test_mode=True)
    result = generate_835(req, _DELIMS)
    isa_end = result.index(_DELIMS.segment)
    parts = result[:isa_end].split(_DELIMS.element)
    assert parts[15] == "T"


def test_835_production_mode_indicator():
    req = _make_request(test_mode=False)
    result = generate_835(req, _DELIMS)
    isa_end = result.index(_DELIMS.segment)
    parts = result[:isa_end].split(_DELIMS.element)
    assert parts[15] == "P"


def test_835_empty_claims_still_valid():
    req = _make_request(claims=[], payment_amount=Decimal("0.00"))
    result = generate_835(req, _DELIMS)
    errors = validate_835_basic(result, _DELIMS)
    assert errors == []
