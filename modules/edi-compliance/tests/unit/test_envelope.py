"""Tests for X12 envelope builder."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.x12.delimiters import Delimiters
from src.x12.envelope import (
    build_ge,
    build_gs,
    build_iea,
    build_se,
    build_st,
    parse_envelope,
)
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import Generate835Request, N1Party, TrnTrace
from decimal import Decimal

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
_FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

TENANT_ID = "11111111-1111-1111-1111-111111111111"
PARTNER_ID = "22222222-2222-2222-2222-222222222222"


def test_build_gs():
    gs = build_gs("HP", "SENDER", "RECEIVER", 1, _FIXED_NOW, "005010X221A1", _DELIMS)
    assert gs.startswith("GS*HP*SENDER*RECEIVER*")
    assert gs.endswith("~")


def test_build_ge():
    ge = build_ge(1, 1, _DELIMS)
    assert ge == "GE*1*1~"


def test_build_se():
    se = build_se(10, 1, _DELIMS)
    assert se == "SE*10*0001~"


def test_build_st():
    st = build_st("835", 1, "005010X221A1", _DELIMS)
    assert st == "ST*835*0001*005010X221A1~"


def test_build_iea():
    iea = build_iea(1, 1, _DELIMS)
    assert iea == "IEA*1*000000001~"


def test_parse_envelope_basic():
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
    raw = generate_835(req, _DELIMS, _FIXED_NOW)
    parsed = parse_envelope(raw, _DELIMS)
    assert parsed.transaction_id == "835"
    assert parsed.sender_qualifier == "ZZ"
    assert len(parsed.sender_id) == 15  # ISA06 not stripped


def test_parse_envelope_missing_isa_raises():
    with pytest.raises(ValueError, match="Missing ISA"):
        parse_envelope("GS*HP*~SE*1*0001~", _DELIMS)


def test_build_gs_default_delims():
    gs = build_gs("HP", "SENDER", "RECEIVER", 1, _FIXED_NOW, "005010X221A1")
    assert "*" in gs
    assert gs.endswith("~")
