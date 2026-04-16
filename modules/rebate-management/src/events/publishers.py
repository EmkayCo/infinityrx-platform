"""Event publishers for the rebate-management module.

All events use EventEnvelope with ordering_key and idempotency_key.
All Decimal amounts are serialized as str() per financial-precision rules.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from shared.events.types import EventEnvelope

SOURCE_MODULE = "rebate-management"


def _decimal_payload(d: dict[str, Any]) -> dict[str, Any]:
    """Convert Decimal values in a payload dict to str for wire format."""
    return {
        k: str(v) if isinstance(v, Decimal) else v
        for k, v in d.items()
    }


def rebate_calculated_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    contract_id: uuid.UUID,
    period_start: str,
    period_end: str,
    total_rebate: Decimal,
    transaction_count: int,
    ndc_count: int,
) -> EventEnvelope:
    """Publish after a rebate period calculation completes."""
    return EventEnvelope(
        event_type="rebate.calculated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(contract_id),
        idempotency_key=f"rebate_calc:{contract_id}:{period_start}:{period_end}",
        payload=_decimal_payload({
            "contract_id": str(contract_id),
            "period_start": period_start,
            "period_end": period_end,
            "total_rebate": total_rebate,
            "transaction_count": transaction_count,
            "ndc_count": ndc_count,
        }),
    )


def rebate_invoice_generated_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    contract_id: uuid.UUID,
    invoice_id: uuid.UUID,
    total_amount: Decimal,
    manufacturer_id: uuid.UUID,
) -> EventEnvelope:
    """Publish when a rebate invoice is generated to a manufacturer."""
    return EventEnvelope(
        event_type="rebate.invoice_generated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(contract_id),
        idempotency_key=f"rebate_invoice:{invoice_id}",
        payload=_decimal_payload({
            "contract_id": str(contract_id),
            "invoice_id": str(invoice_id),
            "total_amount": total_amount,
            "manufacturer_id": str(manufacturer_id),
        }),
    )


def rebate_payment_received_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    contract_id: uuid.UUID,
    payment_amount: Decimal,
    reference_number: str,
) -> EventEnvelope:
    """Publish when a manufacturer rebate payment is received."""
    return EventEnvelope(
        event_type="rebate.payment_received",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(contract_id),
        idempotency_key=f"rebate_payment:{reference_number}",
        payload=_decimal_payload({
            "contract_id": str(contract_id),
            "payment_amount": payment_amount,
            "reference_number": reference_number,
        }),
    )


def passthrough_completed_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    sponsor_id: uuid.UUID,
    period_month: str,
    total_passed: Decimal,
) -> EventEnvelope:
    """Publish when pass-through remittance to plan sponsor completes."""
    return EventEnvelope(
        event_type="rebate.passthrough_completed",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(sponsor_id),
        idempotency_key=f"passthrough:{sponsor_id}:{period_month}",
        payload=_decimal_payload({
            "sponsor_id": str(sponsor_id),
            "period_month": period_month,
            "total_passed": total_passed,
        }),
    )


def audit_requested_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    export_id: uuid.UUID,
    requested_by: uuid.UUID,
) -> EventEnvelope:
    """Publish when an audit export is requested."""
    return EventEnvelope(
        event_type="rebate.audit_requested",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(export_id),
        idempotency_key=f"audit_export:{export_id}",
        payload={
            "export_id": str(export_id),
            "requested_by": str(requested_by),
        },
    )


def spend_cap_threshold_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    guarantee_id: uuid.UUID,
    threshold_pct: str,
    utilization_pct: Decimal,
    ceiling: Decimal,
    cumulative_spend: Decimal,
) -> EventEnvelope:
    """Publish when spend cap utilization crosses a threshold."""
    return EventEnvelope(
        event_type="spend_cap.threshold_approaching",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(guarantee_id),
        idempotency_key=f"spend_cap_alert:{guarantee_id}:{threshold_pct}",
        payload=_decimal_payload({
            "guarantee_id": str(guarantee_id),
            "threshold_pct": threshold_pct,
            "utilization_pct": utilization_pct,
            "ceiling": ceiling,
            "cumulative_spend": cumulative_spend,
        }),
    )


def fiduciary_report_due_event(
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    sponsor_id: uuid.UUID,
    report_type: str,
    due_date: str,
) -> EventEnvelope:
    """Publish when a fiduciary/transparency report is due."""
    return EventEnvelope(
        event_type="fiduciary.report_due",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        ordering_key=str(sponsor_id),
        idempotency_key=f"fiduciary_due:{sponsor_id}:{report_type}:{due_date}",
        payload={
            "sponsor_id": str(sponsor_id),
            "report_type": report_type,
            "due_date": due_date,
        },
    )
