"""Payment-processing event publishers.

All event publishing goes through the shim event bus.
Real implementation uses RabbitMQ (local) / Azure Service Bus (prod).
"""
from __future__ import annotations

from decimal import Decimal

from .._shim import events as event_bus
from ..utils.constants import (
    EVENT_FAILED,
    EVENT_FILE_GENERATED,
    EVENT_RETURN_SUSPICIOUS,
    EVENT_RETURNED,
    EVENT_SETTLED,
    EVENT_SUBMITTED,
    EVENT_VENDOR_STATUS_CHANGED,
)


def publish_file_generated(
    *,
    tenant_id: str,
    submission_id: str,
    billing_payment_batch_id: str,
    payment_count: int,
    total_amount: Decimal,
    file_format: str | None = None,
) -> None:
    event_bus.publish(
        EVENT_FILE_GENERATED,
        {
            "tenant_id": tenant_id,
            "submission_id": submission_id,
            "billing_payment_batch_id": billing_payment_batch_id,
            "payment_count": payment_count,
            "total_amount": str(total_amount),
            "file_format": file_format,
        },
    )


def publish_submitted(
    *,
    tenant_id: str,
    submission_id: str,
    billing_payment_batch_id: str,
    vendor_reference: str | None,
    total_amount: Decimal,
    payment_count: int,
) -> None:
    event_bus.publish(
        EVENT_SUBMITTED,
        {
            "tenant_id": tenant_id,
            "submission_id": submission_id,
            "billing_payment_batch_id": billing_payment_batch_id,
            "vendor_reference": vendor_reference,
            "total_amount": str(total_amount),
            "payment_count": payment_count,
        },
    )


def publish_settled(
    *,
    tenant_id: str,
    billing_payment_id: str,
    submission_id: str,
    settlement_date: str,
    settlement_reference: str,
    amount: Decimal,
    payment_method_used: str,
) -> None:
    event_bus.publish(
        EVENT_SETTLED,
        {
            "tenant_id": tenant_id,
            "billing_payment_id": billing_payment_id,
            "submission_id": submission_id,
            "settlement_date": settlement_date,
            "settlement_reference": settlement_reference,
            "amount": str(amount),
            "payment_method_used": payment_method_used,
        },
    )


def publish_returned(
    *,
    tenant_id: str,
    billing_payment_id: str,
    submission_id: str,
    return_code: str,
    return_reason: str | None,
    amount: Decimal,
    default_action: str,
    is_retryable: bool,
) -> None:
    event_bus.publish(
        EVENT_RETURNED,
        {
            "tenant_id": tenant_id,
            "billing_payment_id": billing_payment_id,
            "submission_id": submission_id,
            "return_code": return_code,
            "return_reason": return_reason,
            "amount": str(amount),
            "default_action": default_action,
            "is_retryable": is_retryable,
        },
    )


def publish_return_suspicious(
    *,
    tenant_id: str,
    billing_payment_id: str,
    submission_id: str,
    return_code: str,
    amount: Decimal,
) -> None:
    event_bus.publish(
        EVENT_RETURN_SUSPICIOUS,
        {
            "tenant_id": tenant_id,
            "billing_payment_id": billing_payment_id,
            "submission_id": submission_id,
            "return_code": return_code,
            "amount": str(amount),
        },
    )


def publish_failed(
    *,
    tenant_id: str,
    submission_id: str,
    billing_payment_batch_id: str,
    error: str,
) -> None:
    event_bus.publish(
        EVENT_FAILED,
        {
            "tenant_id": tenant_id,
            "submission_id": submission_id,
            "billing_payment_batch_id": billing_payment_batch_id,
            "error": error,
        },
    )


def publish_vendor_status_changed(
    *,
    tenant_id: str,
    vendor_adapter_id: str,
    old_status: str,
    new_status: str,
) -> None:
    event_bus.publish(
        EVENT_VENDOR_STATUS_CHANGED,
        {
            "tenant_id": tenant_id,
            "vendor_adapter_id": vendor_adapter_id,
            "old_status": old_status,
            "new_status": new_status,
        },
    )
