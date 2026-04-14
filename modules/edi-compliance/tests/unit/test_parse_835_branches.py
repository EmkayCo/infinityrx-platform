"""Branch coverage tests for parse_835."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.x12.parsers.parse_835 import parse_835


def _wrap_835(body_segs: str, isa_ctrl: str = "000000001") -> str:
    """Wrap body segments in minimal ISA/GS/ST/SE/GE/IEA envelope."""
    return (
        f"ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        f"*260101*1200*^*00501*{isa_ctrl}*0*T*:~"
        f"GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
        f"ST*835*0001*005010X221A1~"
        f"BPR*I*100.00*C*ACH~~~~~~~~~~~~~~~~20260101~"
        f"TRN*1*EFT001*PAYER001~"
        f"DTM*405*20260101~"
        f"N1*PR*PAYER~"
        f"N1*PE*PAYEE~"
        f"{body_segs}"
        f"SE*10*0001~"
        f"GE*1*1~"
        f"IEA*1*{isa_ctrl}~"
    )


def test_parse_835_no_isa_raises():
    """parse_835 raises ValueError on invalid/too-short EDI (via detect_delimiters or missing ISA)."""
    with pytest.raises(ValueError):
        parse_835("GS*HP*SENDER*RECEIVER~SE*1*0001~")


def test_parse_835_isa_not_found_in_segments():
    """parse_835 raises ValueError('No ISA segment found') when segments contain no ISA."""
    from unittest.mock import patch
    # Build a valid-length ISA-like header so detect_delimiters passes,
    # then mock parse_segments to return non-ISA segments.
    valid_header = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000001*0*T*:~"
    )
    with patch("src.x12.parsers.parse_835.parse_segments", return_value=[["GS", "HP"], ["SE", "1"]]):
        with pytest.raises(ValueError, match="No ISA segment found"):
            parse_835(valid_header + "GE*1*1~IEA*1*000000001~")


def test_parse_835_cas_on_svc():
    """CAS after SVC is attached to the service line, not the claim."""
    raw = _wrap_835(
        "CLP*CLM001*1*100.00*80.00*20.00*HM**~"
        "SVC*HC:99213*100.00*80.00***1~"
        "CAS*CO*45*20.00~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims) == 1
    claim = parsed.claims[0]
    assert len(claim.service_lines) == 1
    assert len(claim.service_lines[0].adjustments) == 1
    assert len(claim.adjustments) == 0


def test_parse_835_cas_on_claim():
    """CAS before any SVC is attached to the claim."""
    raw = _wrap_835(
        "CLP*CLM002*1*100.00*80.00*20.00*HM**~"
        "CAS*CO*45*20.00~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims[0].adjustments) == 1
    assert len(parsed.claims[0].service_lines) == 0


def test_parse_835_ref_hpi():
    """REF*HPI sets pharmacy_npi on current claim."""
    raw = _wrap_835(
        "CLP*CLM003*1*100.00*100.00*0.00*HM**~"
        "REF*HPI*1234567893~"
    )
    parsed = parse_835(raw)
    assert parsed.claims[0].pharmacy_npi == "1234567893"


def test_parse_835_ref_g1():
    """REF*G1 sets bin_number."""
    raw = _wrap_835(
        "CLP*CLM004*1*50.00*50.00*0.00*HM**~"
        "REF*G1*999999~"
    )
    parsed = parse_835(raw)
    assert parsed.claims[0].bin_number == "999999"


def test_parse_835_ref_eo():
    """REF*EO sets ncpdp_number."""
    raw = _wrap_835(
        "CLP*CLM005*1*50.00*50.00*0.00*HM**~"
        "REF*EO*NCPDP001~"
    )
    parsed = parse_835(raw)
    assert parsed.claims[0].ncpdp_number == "NCPDP001"


def test_parse_835_ref_1d_svc():
    """REF*1D sets rx_number on current SVC line."""
    raw = _wrap_835(
        "CLP*CLM006*1*50.00*50.00*0.00*HM**~"
        "SVC*HC:99213*50.00*50.00***1~"
        "REF*1D*RX99999~"
    )
    parsed = parse_835(raw)
    assert parsed.claims[0].service_lines[0].rx_number == "RX99999"


def test_parse_835_svc_no_sub_element():
    """SVC01 without sub-element delimiter sets qualifier to empty."""
    raw = _wrap_835(
        "CLP*CLM007*1*50.00*50.00*0.00*HM**~"
        "SVC*99213*50.00*50.00***1~"
    )
    parsed = parse_835(raw)
    svc = parsed.claims[0].service_lines[0]
    assert svc.procedure_qualifier == ""
    assert svc.procedure_code == "99213"


def test_parse_835_multiple_svc_lines_flushed():
    """Multiple SVC lines in one CLP loop are all captured."""
    raw = _wrap_835(
        "CLP*CLM008*1*200.00*180.00*20.00*HM**~"
        "SVC*HC:99213*100.00*90.00***1~"
        "SVC*HC:99214*100.00*90.00***1~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims[0].service_lines) == 2


def test_parse_835_multiple_claims_total():
    """total_claim_paid sums across all CLP loops."""
    raw = _wrap_835(
        "CLP*CLM-A*1*100.00*100.00*0.00*HM**~"
        "CLP*CLM-B*1*200.00*200.00*0.00*HM**~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims) == 2
    assert parsed.total_claim_paid == Decimal("300.00")


def test_parse_835_bpr_missing_date_no_dtm():
    """Payment date is empty when BPR16 empty and no DTM*405."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000099*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*I*0.00*C*ACH~~~~~~~~~~~~~~~~~"
        "TRN*1*EFT099*PAYER001~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "SE*8*0001~"
        "GE*1*1~"
        "IEA*1*000000099~"
    )
    parsed = parse_835(raw)
    assert parsed.payment_date == ""


def test_parse_835_bpr16_populated():
    """When BPR16 is directly populated, payment_date comes from BPR16 (not DTM fallback).

    BPR structure: BPR01-04 (4 values) + BPR05-15 (11 empty) + BPR16 (date).
    11 empty elements = 12 stars between ACH and the date in the raw EDI because
    the separators create: ACH*[11 empties joined by *]*date = 12 star chars total.
    """
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       "
        "*260101*1200*^*00501*000000098*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*I*50.00*C*ACH************20260115~"
        "TRN*1*EFT098*PAYER001~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "SE*8*0001~"
        "GE*1*1~"
        "IEA*1*000000098~"
    )
    parsed = parse_835(raw)
    assert parsed.payment_date == "20260115"


def test_parse_835_ref_1d_without_svc():
    """REF*1D without an active SVC is silently ignored (line 149->108 branch)."""
    raw = _wrap_835(
        "CLP*CLM-NOSVC*1*50.00*50.00*0.00*HM**~"
        "REF*1D*RXIGNORED~"  # No SVC active — qualifier == '1D' but current_svc is None
    )
    parsed = parse_835(raw)
    assert len(parsed.claims) == 1
    assert len(parsed.claims[0].service_lines) == 0
