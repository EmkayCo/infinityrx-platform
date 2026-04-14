"""Additional auto-posting coverage tests."""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any, List

import pytest

from src.x12.delimiters import Delimiters
from src.x12.generators.gen_835 import generate_835
from src.x12.generators.schemas import (
    ClpClaim,
    Generate835Request,
    N1Party,
    TrnTrace,
)
from src.x12.parsers.parse_835 import parse_835
from src.services.auto_posting import auto_post_835

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PARTNER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _MockBus:
    def __init__(self) -> None:
        self.published: List[Any] = []

    async def start(self) -> None:
        pass

    async def publish(self, envelope: Any) -> None:
        self.published.append(envelope)


def _make_remittance_with_empty_claim():
    req = Generate835Request(
        tenant_id=str(TENANT_ID),
        trading_partner_id=str(PARTNER_ID),
        isa_control_number=20,
        gs_control_number=20,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("0.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT20",
        payer=N1Party(entity_qualifier="PR", name="P"),
        payee=N1Party(entity_qualifier="PE", name="Q"),
        trace=TrnTrace(check_eft_number="EFT20", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    raw = generate_835(req, _DELIMS)
    return parse_835(raw)


@pytest.mark.asyncio
async def test_auto_post_empty_claims():
    remittance = _make_remittance_with_empty_claim()
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert len(bus.published) == 0
    assert result.matched_claims == []
    assert result.reconciliation_ok


@pytest.mark.asyncio
async def test_auto_post_custom_correlation_id():
    remittance = _make_remittance_with_empty_claim()
    bus = _MockBus()
    cid = uuid.uuid4()
    result = await auto_post_835(remittance, TENANT_ID, bus, correlation_id=cid)
    assert result is not None
