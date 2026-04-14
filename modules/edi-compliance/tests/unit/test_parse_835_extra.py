"""Additional 835 parser coverage tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.x12.delimiters import Delimiters
from src.x12.parsers.parse_835 import parse_835


_DELIMS = Delimiters(element="*", sub_element=":", segment="~")

# A minimal hand-crafted 835 for edge case testing
_MINIMAL_835 = (
    "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000001*0*T*:~"
    "GS*HP*SENDER*RECEIVER*20260101*1200*1*X*005010X221A1~"
    "ST*835*0001*005010X221A1~"
    "BPR*I*0.00*C*ACH~~~~~~~~~~~~~~~~20260101~"
    "TRN*1*EFT001*PAYER001~"
    "DTM*405*20260101~"
    "N1*PR*PAYER INC~"
    "N1*PE*PAYEE INC~"
    "SE*8*0001~"
    "GE*1*1~"
    "IEA*1*000000001~"
)


def test_parse_835_minimal():
    parsed = parse_835(_MINIMAL_835)
    assert parsed.payment_amount == Decimal("0.00")
    assert parsed.check_eft_number == "EFT001"
    assert len(parsed.claims) == 0


def test_parse_835_dtm_date_fallback():
    """Payment date from DTM*405 when BPR16 is empty."""
    parsed = parse_835(_MINIMAL_835)
    assert parsed.payment_date == "20260101"


def test_parse_835_chain_code_ref():
    """PQ REF qualifier maps to chain_code."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000002*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*2*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*I*50.00*C*ACH~~~~~~~~~~~~~~~~20260101~"
        "TRN*1*EFT002*PAYER001~"
        "DTM*405*20260101~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "CLP*CLM001*1*50.00*50.00*0.00*HM**~"
        "REF*PQ*CHAIN001~"
        "SE*10*0001~"
        "GE*1*2~"
        "IEA*1*000000002~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims) == 1
    assert parsed.claims[0].chain_code == "CHAIN001"


def test_parse_835_multiple_functional_groups_handled():
    """Parser handles content with no GS groups gracefully (finds BPR)."""
    raw = (
        "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *260101*1200*^*00501*000000003*0*T*:~"
        "GS*HP*SENDER*RECEIVER*20260101*1200*3*X*005010X221A1~"
        "ST*835*0001*005010X221A1~"
        "BPR*I*100.00*C*ACH~~~~~~~~~~~~~~~~20260101~"
        "TRN*1*EFT003*PAYER001~"
        "DTM*405*20260101~"
        "N1*PR*PAYER~"
        "N1*PE*PAYEE~"
        "CLP*CLM-A*1*60.00*60.00*0.00*HM**~"
        "CLP*CLM-B*1*40.00*40.00*0.00*HM**~"
        "SE*10*0001~"
        "GE*1*3~"
        "IEA*1*000000003~"
    )
    parsed = parse_835(raw)
    assert len(parsed.claims) == 2
    assert parsed.total_claim_paid == Decimal("100.00")
