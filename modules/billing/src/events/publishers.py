"""Billing event publishers.

Publishes structured domain events to the event bus (RabbitMQ locally,
Azure Service Bus in production). All events use EventEnvelope per event-bus rules.

All publisher functions are async — the shared EventBus.publish() is a coroutine.
Call sites in sync routes must be adapted to async (CR-05 / Teammate 3).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def publish_claim_ingested(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    auth_number: str,
    claim_type: str,
    net_amount: Decimal,
    client_id: uuid.UUID,
    program_id: uuid.UUID,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="claim.ingested",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(claim_id),
            idempotency_key=f"claim.ingested:{claim_id}",
            payload={
                "tenant_id": str(tenant_id),
                "claim_id": str(claim_id),
                "auth_number": auth_number,
                "claim_type": claim_type,
                "net_amount": str(net_amount),
                "client_id": str(client_id),
                "program_id": str(program_id),
                "occurred_at": _now(),
            },
        )
    )


async def publish_claim_classified(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    correlation_id: uuid.UUID,
    payment_route: str | None,
    is_excluded: bool,
    is_statement: bool,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="claim.classified",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(claim_id),
            idempotency_key=f"claim.classified:{claim_id}",
            payload={
                "tenant_id": str(tenant_id),
                "claim_id": str(claim_id),
                "payment_route": payment_route,
                "is_excluded": is_excluded,
                "is_statement": is_statement,
                "occurred_at": _now(),
            },
        )
    )


async def publish_payment_batch_submitted(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    correlation_id: uuid.UUID,
    batch_number: str,
    payment_route: str,
    total_amount: Decimal,
    payment_count: int,
) -> None:
    """Publish payment_batch.submitted — the canonical topic for payment-processing to consume.

    NOTE: payment_batch.generated was the old topic name. payment_batch.submitted is the
    correct semantic (batch submitted to vendor) per CR-01 topic reconciliation.
    The ap.py service's direct bus.publish("payment_batch.generated", ...) calls will be
    updated to async EventEnvelope calls by Teammate 3 (CR-05 sync route conversion).
    """
    await bus.publish(
        EventEnvelope(
            event_type="payment_batch.submitted",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(batch_id),
            idempotency_key=f"payment_batch.submitted:{batch_id}",
            payload={
                "tenant_id": str(tenant_id),
                "batch_id": str(batch_id),
                "batch_number": batch_number,
                "payment_route": payment_route,
                "total_amount": str(total_amount),
                "payment_count": payment_count,
                "occurred_at": _now(),
            },
        )
    )


async def publish_payment_batch_voided(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    correlation_id: uuid.UUID,
    batch_number: str,
    reason: str | None = None,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="payment_batch.voided",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(batch_id),
            idempotency_key=f"payment_batch.voided:{batch_id}",
            payload={
                "tenant_id": str(tenant_id),
                "batch_id": str(batch_id),
                "batch_number": batch_number,
                "reason": reason,
                "occurred_at": _now(),
            },
        )
    )


async def publish_invoice_generated(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
    correlation_id: uuid.UUID,
    invoice_number: str,
    client_id: uuid.UUID,
    total: Decimal,
    due_date: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="invoice.generated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(invoice_id),
            idempotency_key=f"invoice.generated:{invoice_id}",
            payload={
                "tenant_id": str(tenant_id),
                "invoice_id": str(invoice_id),
                "invoice_number": invoice_number,
                "client_id": str(client_id),
                "total": str(total),
                "due_date": due_date,
                "occurred_at": _now(),
            },
        )
    )


async def publish_ar_payment_received(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    ar_id: uuid.UUID,
    correlation_id: uuid.UUID,
    client_id: uuid.UUID,
    amount: Decimal,
    payment_date: str,
    outstanding_after: Decimal,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="ar.payment_received",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(ar_id),
            idempotency_key=f"ar.payment_received:{ar_id}:{payment_date}",
            payload={
                "tenant_id": str(tenant_id),
                "ar_id": str(ar_id),
                "client_id": str(client_id),
                "amount": str(amount),
                "payment_date": payment_date,
                "outstanding_after": str(outstanding_after),
                "occurred_at": _now(),
            },
        )
    )


async def publish_budget_alert_fired(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    program_budget_id: uuid.UUID,
    correlation_id: uuid.UUID,
    program_id: uuid.UUID,
    alert_type: str,
    severity: str,
    message: str,
) -> None:
    await bus.publish(
        EventEnvelope(
            event_type="budget.alert_fired",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(program_budget_id),
            idempotency_key=f"budget.alert_fired:{program_budget_id}:{alert_type}",
            payload={
                "tenant_id": str(tenant_id),
                "program_budget_id": str(program_budget_id),
                "program_id": str(program_id),
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "occurred_at": _now(),
            },
        )
    )
