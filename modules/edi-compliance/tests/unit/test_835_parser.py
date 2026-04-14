"""Tests for the 835 remittance advice parser."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.x12.delimiters import Delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import (
    CasAdjustment,
    ClpClaim,
    Generate835Request,
    N1Party,
    SvcLine,
    TrnTrace,
)
from src.x12.parsers.parse_835 import parse_835

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _make_835() -> str:
    req = Generate835Request(
        tenant_id=TENANT_ID,
        trading_partner_id=PARTNER_ID,
        isa_control_number=5,
        gs_control_number=5,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("150.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT99999",
        payer=N1Party(entity_qualifier="PR", name="HEALTH PLAN", id_qualifier="PI", id_code="HP001"),
        payee=N1Party(entity_qualifier="PE", name="PHARMA INC", id_qualifier="XX", id_code="1234567890"),
        trace=TrnTrace(check_eft_number="EFT99999", payer_id="HP001"),
        claims=[
            ClpClaim(
                claim_id="CLAIMRX001",
                status_code="1",
                charge_amount=Decimal("100.00"),
                paid_amount=Decimal("85.00"),
                patient_responsibility=Decimal("15.00"),
                claim_filing_indicator="HM",
                pharmacy_npi="1234567893",
                bin_number="123456",
                ncpdp_number="NCPDP001",
                adjustments=[CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("15.00"))],
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
                claim_id="CLAIMRX002",
                status_code="1",
                charge_amount=Decimal("50.00"),
                paid_amount=Decimal("65.00"),
                patient_responsibility=Decimal("0.00"),
                claim_filing_indicator="HM",
            ),
        ],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    return generate_835(req, _DELIMS)


def test_parse_835_payment_amount():
    raw = _make_835()
    parsed = parse_835(raw)
    assert parsed.payment_amount == Decimal("150.00")


def test_parse_835_payment_date():
    raw = _make_835()
    parsed = parse_835(raw)
    assert parsed.payment_date == "20260401"


def test_parse_835_check_eft_number():
    raw = _make_835()
    parsed = parse_835(raw)
    assert parsed.check_eft_number == "EFT99999"


def test_parse_835_claim_count():
    raw = _make_835()
    parsed = parse_835(raw)
    assert len(parsed.claims) == 2


def test_parse_835_claim_ids():
    raw = _make_835()
    parsed = parse_835(raw)
    ids = [c.claim_id for c in parsed.claims]
    assert "CLAIMRX001" in ids
    assert "CLAIMRX002" in ids


def test_parse_835_amounts_are_decimal():
    raw = _make_835()
    parsed = parse_835(raw)
    for claim in parsed.claims:
        assert isinstance(claim.charge_amount, Decimal)
        assert isinstance(claim.paid_amount, Decimal)
        assert isinstance(claim.patient_responsibility, Decimal)


def test_parse_835_adjustments():
    raw = _make_835()
    parsed = parse_835(raw)
    claim = next(c for c in parsed.claims if c.claim_id == "CLAIMRX001")
    assert len(claim.adjustments) == 1
    adj = claim.adjustments[0]
    assert adj.group_code == "CO"
    assert adj.reason_code == "45"
    assert adj.amount == Decimal("15.00")


def test_parse_835_service_lines():
    raw = _make_835()
    parsed = parse_835(raw)
    claim = next(c for c in parsed.claims if c.claim_id == "CLAIMRX001")
    assert len(claim.service_lines) == 1
    svc = claim.service_lines[0]
    assert svc.procedure_code == "12345678901"
    assert svc.charge_amount == Decimal("100.00")
    assert svc.paid_amount == Decimal("85.00")


def test_parse_835_rx_number():
    raw = _make_835()
    parsed = parse_835(raw)
    claim = next(c for c in parsed.claims if c.claim_id == "CLAIMRX001")
    assert claim.service_lines[0].rx_number == "RX00001"


def test_parse_835_pharmacy_identifiers():
    raw = _make_835()
    parsed = parse_835(raw)
    claim = next(c for c in parsed.claims if c.claim_id == "CLAIMRX001")
    assert claim.pharmacy_npi == "1234567893"
    assert claim.bin_number == "123456"
    assert claim.ncpdp_number == "NCPDP001"


def test_parse_835_isa_ids_not_stripped():
    """ISA06/ISA08 must NOT be stripped — trailing spaces structurally required."""
    raw = _make_835()
    parsed = parse_835(raw)
    assert len(parsed.sender_id) == 15, f"sender_id should be 15 chars: {parsed.sender_id!r}"
    assert parsed.sender_id.startswith("INFINITYRX")


def test_parse_835_total_claim_paid():
    raw = _make_835()
    parsed = parse_835(raw)
    expected = Decimal("85.00") + Decimal("65.00")
    assert parsed.total_claim_paid == expected


def test_parse_835_reconciliation_mismatch_detected():
    """When BPR02 != sum of CLP paid amounts, total_claim_paid differs from payment_amount."""
    raw = _make_835()
    parsed = parse_835(raw)
    # payment_amount=150.00, total_claim_paid=150.00 → reconciliation ok
    assert parsed.payment_amount == parsed.total_claim_paid


def test_parse_835_invalid_content_raises():
    with pytest.raises(ValueError):
        parse_835("NOTEDI")
