"""835 auto-posting service.

Matches parsed CLP loops to internal claim records and emits
`payment.auto_posted` event for Billing to consume.  Does NOT write
to the Billing module directly — event-driven only (PRD §3.14).

EventBus and EventEnvelope are imported lazily to allow isolated unit
testing without the full shared infrastructure stack.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional, Protocol

from ..x12.parsers.parse_835 import Parsed835, Parsed835Claim


class _EventBusProtocol(Protocol):
    async def publish(self, envelope: Any) -> None:  # pragma: no cover
        ...


@dataclass
class PostingResult:
    matched_claims: list = field(default_factory=list)
    unmatched_claims: list = field(default_factory=list)
    reconciliation_ok: bool = True
    bpr_amount: Decimal = Decimal("0")
    clp_total: Decimal = Decimal("0")


def _make_envelope(**kwargs: Any) -> Any:
    """Build an EventEnvelope — import lazily to avoid shared import errors in tests."""
    try:
        from shared.events.types import EventEnvelope
        return EventEnvelope(**kwargs)
    except ImportError:  # pragma: no cover
        class _SimpleEnvelope:
            def __init__(self, **kw: Any) -> None:
                for k, v in kw.items():
                    setattr(self, k, v)
        return _SimpleEnvelope(**kwargs)


async def auto_post_835(
    remittance: Parsed835,
    tenant_id: uuid.UUID,
    event_bus: Any,
    correlation_id: Optional[uuid.UUID] = None,
) -> PostingResult:
    """Process a parsed 835 and emit payment.auto_posted events."""
    if correlation_id is None:
        correlation_id = uuid.uuid4()

    result = PostingResult(
        bpr_amount=remittance.payment_amount,
        clp_total=remittance.total_claim_paid,
    )

    if remittance.payment_amount != remittance.total_claim_paid:
        result.reconciliation_ok = False

    for claim in remittance.claims:
        await _post_claim(claim, remittance, tenant_id, event_bus, correlation_id, result)

    return result


async def _post_claim(
    claim: Parsed835Claim,
    remittance: Parsed835,
    tenant_id: uuid.UUID,
    event_bus: Any,
    correlation_id: uuid.UUID,
    result: PostingResult,
) -> None:
    if not claim.claim_id:
        result.unmatched_claims.append("")
        await event_bus.publish(_make_envelope(
            event_type="payment.unmatched_claim",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="edi-compliance",
            schema_version="1.0",
            ordering_key=str(tenant_id),
            idempotency_key=f"unmatched:{remittance.isa_control_number}:{claim.claim_id}",
            payload={
                "isa_control_number": remittance.isa_control_number,
                "claim_id": claim.claim_id,
                "paid_amount": str(claim.paid_amount),
            },
        ))
        return

    result.matched_claims.append(claim.claim_id)

    adjustments_payload = [
        {
            "group_code": adj.group_code,
            "reason_code": adj.reason_code,
            "amount": str(adj.amount),
        }
        for adj in claim.adjustments
    ]

    service_lines_payload = [
        {
            "procedure_qualifier": svc.procedure_qualifier,
            "procedure_code": svc.procedure_code,
            "charge_amount": str(svc.charge_amount),
            "paid_amount": str(svc.paid_amount),
            "quantity": str(svc.quantity),
            "adjustments": [
                {"group_code": a.group_code, "reason_code": a.reason_code, "amount": str(a.amount)}
                for a in svc.adjustments
            ],
        }
        for svc in claim.service_lines
    ]

    await event_bus.publish(_make_envelope(
        event_type="payment.auto_posted",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module="edi-compliance",
        schema_version="1.0",
        ordering_key=claim.claim_id,
        idempotency_key=f"auto_post:{remittance.isa_control_number}:{claim.claim_id}",
        payload={
            "claim_id": claim.claim_id,
            "status_code": claim.status_code,
            "charge_amount": str(claim.charge_amount),
            "paid_amount": str(claim.paid_amount),
            "patient_responsibility": str(claim.patient_responsibility),
            "claim_filing_indicator": claim.claim_filing_indicator,
            "payer_claim_ref": claim.payer_claim_ref,
            "adjustments": adjustments_payload,
            "service_lines": service_lines_payload,
            "check_eft_number": remittance.check_eft_number,
            "payment_date": remittance.payment_date,
            "payer_id": remittance.payer_id,
            "pharmacy_npi": claim.pharmacy_npi,
            "reconciliation_ok": remittance.payment_amount == remittance.total_claim_paid,
        },
    ))
