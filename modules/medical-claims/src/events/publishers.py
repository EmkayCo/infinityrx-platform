"""Medical Claims event publishers.

All events use EventEnvelope with:
- ordering_key = str(claim.id)
- idempotency_key = f"medical_claim:{claim_id}:{event_type}"
- schema_version = "1.0"
- dot-notation event types per event-bus rules
"""
from __future__ import annotations

import uuid
from typing import Any

from shared.events import EventEnvelope, EventBus

MODULE_NAME = "medical-claims"


def _envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    payload: dict[str, Any],
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=MODULE_NAME,
        schema_version="1.0",
        ordering_key=str(claim_id),
        idempotency_key=f"medical_claim:{claim_id}:{event_type}",
        payload=payload,
    )


async def publish_claim_received(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    claim_number: str,
    procedure_code: str,
    date_of_service: str,
    billed_amount: str,
) -> None:
    env = _envelope(
        "medical_claim.received",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "claim_number": claim_number,
            "procedure_code": procedure_code,
            "date_of_service": date_of_service,
            "billed_amount": billed_amount,
        },
    )
    await bus.publish(env)


async def publish_claim_priced(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    allowed_amount: str,
    paid_amount: str,
) -> None:
    env = _envelope(
        "medical_claim.priced",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "allowed_amount": allowed_amount,
            "paid_amount": paid_amount,
        },
    )
    await bus.publish(env)


async def publish_claim_adjudicated(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    status: str,
    paid_amount: str,
) -> None:
    env = _envelope(
        "medical_claim.adjudicated",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "status": status,
            "paid_amount": paid_amount,
        },
    )
    await bus.publish(env)


async def publish_claim_denied(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    denial_reason_code: str | None,
    denial_reason_description: str | None,
) -> None:
    env = _envelope(
        "medical_claim.denied",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "denial_reason_code": denial_reason_code,
            "denial_reason_description": denial_reason_description,
        },
    )
    await bus.publish(env)


async def publish_340b_detected(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    entity_340b_id: str | None,
    billing_provider_npi: str,
) -> None:
    env = _envelope(
        "medical_claim.340b_detected",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "entity_340b_id": entity_340b_id,
            "billing_provider_npi": billing_provider_npi,
        },
    )
    await bus.publish(env)


async def publish_unified_spend_updated(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    unified_spend_id: uuid.UUID,
    benefit_type: str,
) -> None:
    env = _envelope(
        "medical_claim.unified_spend_updated",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "unified_spend_id": str(unified_spend_id),
            "benefit_type": benefit_type,
        },
    )
    await bus.publish(env)


async def publish_therapeutic_duplication(
    bus: EventBus,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    member_id: str,
    ndc: str,
    date_of_service: str,
) -> None:
    env = _envelope(
        "medical_claim.therapeutic_duplication",
        tenant_id,
        claim_id,
        correlation_id,
        {
            "claim_id": str(claim_id),
            "member_id": member_id,
            "ndc": ndc,
            "date_of_service": date_of_service,
        },
    )
    await bus.publish(env)
