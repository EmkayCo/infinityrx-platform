"""Billing event publishers.

Publishes structured domain events to the event bus (RabbitMQ locally,
Azure Service Bus in production). All events include tenant_id for isolation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol


class EventBus(Protocol):
    def publish(self, topic: str, payload: dict[str, Any]) -> None: ...


def _now() -> str:
    return datetime.now(UTC).isoformat()


def publish_claim_ingested(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    auth_number: str,
    claim_type: str,
    net_amount: Decimal,
    client_id: uuid.UUID,
    program_id: uuid.UUID,
) -> None:
    bus.publish(
        "claim.ingested",
        {
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


def publish_claim_classified(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    claim_id: uuid.UUID,
    payment_route: str | None,
    is_excluded: bool,
    is_statement: bool,
) -> None:
    bus.publish(
        "claim.classified",
        {
            "tenant_id": str(tenant_id),
            "claim_id": str(claim_id),
            "payment_route": payment_route,
            "is_excluded": is_excluded,
            "is_statement": is_statement,
            "occurred_at": _now(),
        },
    )


def publish_payment_batch_generated(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    batch_number: str,
    payment_route: str,
    total_amount: Decimal,
    payment_count: int,
) -> None:
    bus.publish(
        "payment_batch.generated",
        {
            "tenant_id": str(tenant_id),
            "batch_id": str(batch_id),
            "batch_number": batch_number,
            "payment_route": payment_route,
            "total_amount": str(total_amount),
            "payment_count": payment_count,
            "occurred_at": _now(),
        },
    )


def publish_payment_batch_voided(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    batch_id: uuid.UUID,
    batch_number: str,
    reason: str | None = None,
) -> None:
    bus.publish(
        "payment_batch.voided",
        {
            "tenant_id": str(tenant_id),
            "batch_id": str(batch_id),
            "batch_number": batch_number,
            "reason": reason,
            "occurred_at": _now(),
        },
    )


def publish_invoice_generated(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    invoice_id: uuid.UUID,
    invoice_number: str,
    client_id: uuid.UUID,
    total: Decimal,
    due_date: str,
) -> None:
    bus.publish(
        "invoice.generated",
        {
            "tenant_id": str(tenant_id),
            "invoice_id": str(invoice_id),
            "invoice_number": invoice_number,
            "client_id": str(client_id),
            "total": str(total),
            "due_date": due_date,
            "occurred_at": _now(),
        },
    )


def publish_ar_payment_received(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    ar_id: uuid.UUID,
    client_id: uuid.UUID,
    amount: Decimal,
    payment_date: str,
    outstanding_after: Decimal,
) -> None:
    bus.publish(
        "ar.payment_received",
        {
            "tenant_id": str(tenant_id),
            "ar_id": str(ar_id),
            "client_id": str(client_id),
            "amount": str(amount),
            "payment_date": payment_date,
            "outstanding_after": str(outstanding_after),
            "occurred_at": _now(),
        },
    )


def publish_budget_alert_fired(
    bus: EventBus,
    *,
    tenant_id: uuid.UUID,
    program_budget_id: uuid.UUID,
    program_id: uuid.UUID,
    alert_type: str,
    severity: str,
    message: str,
) -> None:
    bus.publish(
        "budget.alert_fired",
        {
            "tenant_id": str(tenant_id),
            "program_budget_id": str(program_budget_id),
            "program_id": str(program_id),
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "occurred_at": _now(),
        },
    )
