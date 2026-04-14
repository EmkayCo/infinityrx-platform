"""Branch coverage for auto_posting service."""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any, List

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
from src.services.auto_posting import auto_post_835, _make_envelope

_DELIMS = Delimiters(element="*", sub_element=":", segment="~")
TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PARTNER_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


class _MockBus:
    def __init__(self) -> None:
        self.published: List[Any] = []

    async def publish(self, envelope: Any) -> None:
        self.published.append(envelope)


def _make_req(**overrides) -> Generate835Request:
    defaults = dict(
        tenant_id=str(TENANT_ID),
        trading_partner_id=str(PARTNER_ID),
        isa_control_number=50,
        gs_control_number=50,
        st_control_number=1,
        payment_date="20260401",
        payment_amount=Decimal("100.00"),
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT50",
        payer=N1Party(entity_qualifier="PR", name="PAYER"),
        payee=N1Party(entity_qualifier="PE", name="PAYEE"),
        trace=TrnTrace(check_eft_number="EFT50", payer_id="P001"),
        claims=[],
        sender_qualifier="ZZ",
        sender_id="INFINITYRX     ",
        receiver_qualifier="ZZ",
        test_mode=True,
        implementation_guide="005010X221A1",
    )
    defaults.update(overrides)
    return Generate835Request(**defaults)


def _make_remittance_with_claims(claims):
    req = _make_req(
        payment_amount=sum(c.paid_amount for c in claims),
        claims=claims,
    )
    raw = generate_835(req, _DELIMS)
    return parse_835(raw)


@pytest.mark.asyncio
async def test_auto_post_unmatched_claim_empty_id():
    """Claim with empty claim_id goes to unmatched_claims."""
    from src.x12.parsers.parse_835 import Parsed835, Parsed835Claim
    from decimal import Decimal

    claim = Parsed835Claim(
        claim_id="",
        status_code="1",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("100.00"),
        patient_responsibility=Decimal("0"),
        claim_filing_indicator="HM",
        payer_claim_ref="",
    )
    from src.x12.parsers.parse_835 import Parsed835
    remittance = Parsed835(
        sender_id="SENDER         ",
        receiver_id="RECEIVER       ",
        isa_control_number="000000001",
        payment_amount=Decimal("100.00"),
        payment_date="20260401",
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT50",
        payer_id="P001",
        claims=[claim],
        total_claim_paid=Decimal("100.00"),
    )
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert len(result.unmatched_claims) == 1
    assert len(result.matched_claims) == 0
    assert len(bus.published) == 1


@pytest.mark.asyncio
async def test_auto_post_reconciliation_mismatch():
    """BPR amount != CLP total sets reconciliation_ok=False."""
    from src.x12.parsers.parse_835 import Parsed835, Parsed835Claim

    claim = Parsed835Claim(
        claim_id="CLM001",
        status_code="1",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),  # CLP total = 80
        patient_responsibility=Decimal("20.00"),
        claim_filing_indicator="HM",
        payer_claim_ref="",
    )
    remittance = Parsed835(
        sender_id="SENDER         ",
        receiver_id="RECEIVER       ",
        isa_control_number="000000001",
        payment_amount=Decimal("100.00"),  # BPR = 100, CLP = 80 → mismatch
        payment_date="20260401",
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT50",
        payer_id="P001",
        claims=[claim],
        total_claim_paid=Decimal("80.00"),
    )
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert not result.reconciliation_ok


@pytest.mark.asyncio
async def test_auto_post_with_svc_adjustments():
    """Claims with service lines and adjustments publish event with full payload."""
    from src.x12.parsers.parse_835 import (
        Parsed835, Parsed835Claim, Parsed835SvcLine, Parsed835Adjustment
    )

    adj = Parsed835Adjustment(group_code="CO", reason_code="45", amount=Decimal("20.00"))
    svc = Parsed835SvcLine(
        procedure_qualifier="HC",
        procedure_code="99213",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        quantity=Decimal("1"),
        adjustments=[adj],
    )
    claim = Parsed835Claim(
        claim_id="CLM-SVC",
        status_code="1",
        charge_amount=Decimal("100.00"),
        paid_amount=Decimal("80.00"),
        patient_responsibility=Decimal("20.00"),
        claim_filing_indicator="HM",
        payer_claim_ref="",
        service_lines=[svc],
    )
    remittance = Parsed835(
        sender_id="SENDER         ",
        receiver_id="RECEIVER       ",
        isa_control_number="000000002",
        payment_amount=Decimal("80.00"),
        payment_date="20260401",
        credit_debit_flag="C",
        payment_method="ACH",
        check_eft_number="EFT51",
        payer_id="P001",
        claims=[claim],
        total_claim_paid=Decimal("80.00"),
    )
    bus = _MockBus()
    result = await auto_post_835(remittance, TENANT_ID, bus)
    assert len(result.matched_claims) == 1
    assert result.reconciliation_ok
    assert len(bus.published) == 1
    envelope = bus.published[0]
    payload = envelope.payload
    assert payload["service_lines"][0]["adjustments"][0]["amount"] == "20.00"


def test_make_envelope_fallback():
    """_make_envelope creates a simple namespace when shared import is unavailable."""
    envelope = _make_envelope(
        event_type="test.event",
        tenant_id=TENANT_ID,
        correlation_id=uuid.uuid4(),
        source_module="edi-compliance",
        schema_version="1.0",
        ordering_key="test",
        idempotency_key="test:key",
        payload={"key": "value"},
    )
    assert envelope.event_type == "test.event"
    assert envelope.payload["key"] == "value"


def test_make_envelope_with_shared_success():
    """_make_envelope uses shared.events.types.EventEnvelope when available."""
    from unittest.mock import MagicMock, patch

    mock_envelope_class = MagicMock(return_value=MagicMock(event_type="test.event"))
    mock_shared_events = MagicMock()
    mock_shared_events.EventEnvelope = mock_envelope_class

    with patch.dict("sys.modules", {
        "shared": MagicMock(),
        "shared.events": MagicMock(),
        "shared.events.types": mock_shared_events,
    }):
        import importlib
        import src.services.auto_posting as ap_module
        importlib.reload(ap_module)
        result = ap_module._make_envelope(
            event_type="test.event",
            tenant_id=TENANT_ID,
            correlation_id=uuid.uuid4(),
            source_module="edi-compliance",
            schema_version="1.0",
            ordering_key="test",
            idempotency_key="test:key",
            payload={"key": "value"},
        )
        mock_envelope_class.assert_called_once()

    # Reload back to original state
    import importlib
    import src.services.auto_posting as ap_module
    importlib.reload(ap_module)
