"""Tests for 835 auto-posting service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, List, Optional
from unittest.mock import AsyncMock, MagicMock

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
from src.services.auto_posting import PostingResult, auto_post_835

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PARTNER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _MockBus:
    """Minimal event bus mock for testing without shared dependencies."""

    def __init__(self) -> None:
        self.published: List[Any] = []
        self._subscribers: List[tuple] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def publish(self, envelope: Any) -> None:
        self.published.append(envelope)
        for pattern, handler in self._subscribers:
            if pattern == "*" or envelope.event_type == pattern:
                await handler(envelope)

    async def subscribe(self, pattern: str, handler: Any) -> None:
        self._subscribers.append((pattern, handler))


class _MockEnvelope:
    """Minimal envelope for testing — mirrors shared.events.types.EventEnvelope fields."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


# Monkey-patch auto_posting to use a mock EventEnvelope

def _make_remittance():
    req = Generate835Request(
        tenant_id=str(TENANT_ID),
        trading_partner_id=str(PARTNER_ID),
        isa_control_number=10,
        gs_control_number=10,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("150.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT10",
        payer=N1Party(entity_qualifier="PR", name="PAYER INC"),
        payee=N1Party(entity_qualifier="PE", name="PHARMA"),
        trace=TrnTrace(check_eft_number="EFT10", payer_id="PAYER001"),
        claims=[
            ClpClaim(
                claim_id="CLM-AUTO-001",
                status_code="1",
                charge_amount=Decimal("100.00"),
                paid_amount=Decimal("85.00"),
                patient_responsibility=Decimal("15.00"),
                claim_filing_indicator="HM",
                adjustments=[CasAdjustment(group_code="CO", reason_code="45", amount=Decimal("15.00"))],
            ),
            ClpClaim(
                claim_id="CLM-AUTO-002",
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
    raw = generate_835(req, _DELIMS)
    return parse_835(raw)


@pytest.mark.asyncio
async def test_auto_post_emits_events():
    remittance = _make_remittance()
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert len(bus.published) == 2
    assert result.reconciliation_ok


@pytest.mark.asyncio
async def test_auto_post_matched_claim_ids():
    remittance = _make_remittance()
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert "CLM-AUTO-001" in result.matched_claims
    assert "CLM-AUTO-002" in result.matched_claims


@pytest.mark.asyncio
async def test_auto_post_event_payload_amounts_are_strings():
    """Decimal amounts must be serialized as strings in event payloads."""
    remittance = _make_remittance()
    bus = _MockBus()
    await auto_post_835(remittance, TENANT_ID, bus)

    for event in bus.published:
        payload = event.payload
        assert isinstance(payload["paid_amount"], str), "paid_amount must be str in event payload"
        assert isinstance(payload["charge_amount"], str), "charge_amount must be str in event payload"
        Decimal(payload["paid_amount"])
        Decimal(payload["charge_amount"])


@pytest.mark.asyncio
async def test_auto_post_reconciliation_mismatch():
    """When payment_amount != sum of CLP paid, reconciliation_ok=False."""
    remittance = _make_remittance()
    from dataclasses import replace
    remittance_bad = replace(remittance, payment_amount=Decimal("999.99"))
    bus = _MockBus()
    result = await auto_post_835(remittance_bad, TENANT_ID, bus)
    assert not result.reconciliation_ok


@pytest.mark.asyncio
async def test_auto_post_event_tenant_id():
    remittance = _make_remittance()
    bus = _MockBus()
    await auto_post_835(remittance, TENANT_ID, bus)
    for event in bus.published:
        assert event.tenant_id == TENANT_ID


@pytest.mark.asyncio
async def test_auto_post_event_has_idempotency_key():
    remittance = _make_remittance()
    bus = _MockBus()
    await auto_post_835(remittance, TENANT_ID, bus)
    for event in bus.published:
        assert event.idempotency_key
        assert "auto_post:" in event.idempotency_key


@pytest.mark.asyncio
async def test_auto_post_event_ordering_key_is_claim_id():
    remittance = _make_remittance()
    bus = _MockBus()
    await auto_post_835(remittance, TENANT_ID, bus)
    ordering_keys = {e.ordering_key for e in bus.published}
    assert "CLM-AUTO-001" in ordering_keys
    assert "CLM-AUTO-002" in ordering_keys


@pytest.mark.asyncio
async def test_auto_post_bpr_clp_reconciliation_ok():
    """150.00 BPR payment should equal 85.00 + 65.00 = 150.00 CLP sum."""
    remittance = _make_remittance()
    assert remittance.payment_amount == Decimal("150.00")
    assert remittance.total_claim_paid == Decimal("150.00")
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert result.reconciliation_ok
    assert result.bpr_amount == Decimal("150.00")
    assert result.clp_total == Decimal("150.00")
