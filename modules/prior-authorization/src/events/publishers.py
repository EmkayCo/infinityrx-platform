"""Prior Authorization event publishers.

All events use EventEnvelope with:
- ordering_key = str(pa_request.id)
- idempotency_key = f"pa:{pa_id}:{event_type}"
- schema_version = "1.0"
- dot-notation event types per event-bus rules

Money amounts serialized as str() per financial-precision rules.
"""
from __future__ import annotations

import uuid
from typing import Any

from shared.events import EventBus, EventEnvelope

MODULE_NAME = "prior-authorization"


def _envelope(
    event_type: str,
    tenant_id: uuid.UUID,
    pa_request_id: uuid.UUID,
    correlation_id: uuid.UUID,
    payload: dict[str, Any],
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=MODULE_NAME,
        schema_version="1.0",
        ordering_key=str(pa_request_id),
        idempotency_key=f"pa:{pa_request_id}:{event_type}",
        payload=payload,
    )


async def publish_pa_submitted(
    bus: EventBus,
    tenant_id: uuid.UUID,
    pa_request_id: uuid.UUID,
    correlation_id: uuid.UUID,
    member_id: str,
    drug_ndc: str,
    source: str,
    priority: str,
) -> None:
    """Publish pa.submitted event when a new PA is created."""
    env = _envelope(
        "pa.submitted",
        tenant_id,
        pa_request_id,
        correlation_id,
        {
            "pa_request_id": str(pa_request_id),
            "member_id": member_id,
            "drug_ndc": drug_ndc,
            "source": source,
            "priority": priority,
        },
    )
    await bus.publish(env)


async def publish_pa_approved(
    bus: EventBus,
    tenant_id: uuid.UUID,
    pa_request_id: uuid.UUID,
    correlation_id: uuid.UUID,
    approved_duration_days: int | None,
    auto_approved: bool,
) -> None:
    """Publish pa.approved event when a PA is approved (auto or manual)."""
    env = _envelope(
        "pa.approved",
        tenant_id,
        pa_request_id,
        correlation_id,
        {
            "pa_request_id": str(pa_request_id),
            "approved_duration_days": approved_duration_days,
            "auto_approved": auto_approved,
        },
    )
    await bus.publish(env)


async def publish_pa_denied(
    bus: EventBus,
    tenant_id: uuid.UUID,
    pa_request_id: uuid.UUID,
    correlation_id: uuid.UUID,
    denial_reasons: list[str],
) -> None:
    """Publish pa.denied event when a PA is denied."""
    env = _envelope(
        "pa.denied",
        tenant_id,
        pa_request_id,
        correlation_id,
        {
            "pa_request_id": str(pa_request_id),
            "denial_reasons": denial_reasons,
        },
    )
    await bus.publish(env)


async def publish_pa_appealed(
    bus: EventBus,
    tenant_id: uuid.UUID,
    pa_request_id: uuid.UUID,
    correlation_id: uuid.UUID,
    appeal_level: int,
    appeal_type: str,
) -> None:
    """Publish pa.appealed event when an appeal is filed."""
    env = _envelope(
        "pa.appealed",
        tenant_id,
        pa_request_id,
        correlation_id,
        {
            "pa_request_id": str(pa_request_id),
            "appeal_level": appeal_level,
            "appeal_type": appeal_type,
        },
    )
    await bus.publish(env)
