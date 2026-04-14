"""Tests for gen_835 branch coverage."""

from __future__ import annotations

from datetime import datetime, timezone
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

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def _base_req(**overrides) -> Generate835Request:
    kwargs = dict(
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
    kwargs.update(overrides)
    return Generate835Request(**kwargs)


def test_n1_with_id_qualifier():
    """N1 party with id_qualifier and id_code emits 4-element N1 segment."""
    payer = N1Party(entity_qualifier="PR", name="PAYER INC", id_qualifier="PI", id_code="PAYER001")
    req = _base_req(payer=payer)
    result = generate_835(req, _DELIMS, _NOW)
    assert "N1*PR*PAYER INC*PI*PAYER001~" in result


def test_trn_with_originating_company_id():
    """TRN segment includes element 4 when originating_company_id is set."""
    trace = TrnTrace(check_eft_number="EFT001", payer_id="P001", originating_company_id="ORIGCO")
    req = _base_req(trace=trace)
    result = generate_835(req, _DELIMS, _NOW)
    assert "TRN*1*EFT001*P001*ORIGCO~" in result


def test_clp_with_patient_control_number():
    """CLP with patient_control_number emits NM1*QC segment."""
    claim = ClpClaim(
        claim_id="CLM001",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        patient_control_number="PAT001",
    )
    req = _base_req(claims=[claim])
    result = generate_835(req, _DELIMS, _NOW)
    assert "NM1*QC*1****" in result
    assert "PAT001" in result


def test_svc_with_rx_number():
    """SVC line with rx_number emits REF*1D segment."""
    svc = SvcLine(
        procedure_code="99213",
        procedure_qualifier="HC",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        rx_number="RX123456",
    )
    claim = ClpClaim(
        claim_id="CLM001",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        service_lines=[svc],
    )
    req = _base_req(claims=[claim])
    result = generate_835(req, _DELIMS, _NOW)
    assert "REF*1D*RX123456~" in result


def test_svc_with_ndc():
    """SVC line with NDC uses N4 qualifier in SVC01 composite."""
    svc = SvcLine(
        procedure_code="99213",
        procedure_qualifier="HC",
        charge_amount=Decimal("10.00"),
        paid_amount=Decimal("8.00"),
        ndc="12345678901",
    )
    claim = ClpClaim(
        claim_id="CLM002",
        charge_amount=Decimal("10.00"),
        paid_amount=Decimal("8.00"),
        service_lines=[svc],
    )
    req = _base_req(claims=[claim])
    result = generate_835(req, _DELIMS, _NOW)
    assert "SVC*N4:12345678901*" in result


def test_clp_pharmacy_ref_segments():
    """CLP with pharmacy identifiers emits REF*HPI, REF*G1, REF*EO, REF*PQ."""
    claim = ClpClaim(
        claim_id="CLM003",
        charge_amount=Decimal("50.00"),
        paid_amount=Decimal("50.00"),
        pharmacy_npi="1234567893",
        bin_number="999999",
        ncpdp_number="1234567",
        chain_code="CHN01",
    )
    req = _base_req(claims=[claim])
    result = generate_835(req, _DELIMS, _NOW)
    assert "REF*HPI*1234567893~" in result
    assert "REF*G1*999999~" in result
    assert "REF*EO*1234567~" in result
    assert "REF*PQ*CHN01~" in result


def test_svc_cas_adjustment():
    """CAS segment is emitted for SVC adjustments."""
    adj = CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("20.00"))
    svc = SvcLine(
        procedure_code="99213",
        procedure_qualifier="HC",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        adjustments=[adj],
    )
    claim = ClpClaim(
        claim_id="CLM004",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        service_lines=[svc],
    )
    req = _base_req(claims=[claim])
    result = generate_835(req, _DELIMS, _NOW)
    assert "CAS*CO*45*20.00~" in result


def test_production_mode():
    """ISA15 is P when test_mode=False."""
    req = _base_req(test_mode=False)
    result = generate_835(req, _DELIMS, _NOW)
    isa_seg = result.split("~")[0]
    elements = isa_seg.split("*")
    assert elements[15] == "P"
