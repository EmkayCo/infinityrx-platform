"""Event publishing functions for the reporting module."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


async def publish_report_generated(
    event_bus: Any,
    tenant_id: str,
    report_run_id: str,
    report_definition_id: str,
    row_count: int,
    output_format: str,
    correlation_id: str,
) -> None:
    """Publish event when a report execution completes."""
    await event_bus.publish(
        event_type="report.generated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload={
            "report_run_id": report_run_id,
            "report_definition_id": report_definition_id,
            "row_count": row_count,
            "output_format": output_format,
            "completed_at": datetime.now(UTC).isoformat(),
        },
    )


async def publish_report_delivered(
    event_bus: Any,
    tenant_id: str,
    report_run_id: str,
    delivery_method: str,
    correlation_id: str,
) -> None:
    """Publish event when a report is successfully delivered."""
    await event_bus.publish(
        event_type="report.delivered",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload={
            "report_run_id": report_run_id,
            "delivery_method": delivery_method,
            "delivered_at": datetime.now(UTC).isoformat(),
        },
    )


async def publish_report_delivery_failed(
    event_bus: Any,
    tenant_id: str,
    report_run_id: str,
    delivery_method: str,
    error: str,
    correlation_id: str,
) -> None:
    """Publish event when report delivery fails."""
    await event_bus.publish(
        event_type="report.delivery_failed",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload={
            "report_run_id": report_run_id,
            "delivery_method": delivery_method,
            "error": error,
            "failed_at": datetime.now(UTC).isoformat(),
        },
    )


async def publish_regulatory_deadline_approaching(
    event_bus: Any,
    tenant_id: str,
    submission_id: str,
    report_type: str,
    due_date: str,
    days_until_due: int,
    correlation_id: str,
) -> None:
    """Publish event when a regulatory submission deadline is approaching."""
    await event_bus.publish(
        event_type="regulatory.deadline_approaching",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload={
            "submission_id": submission_id,
            "report_type": report_type,
            "due_date": due_date,
            "days_until_due": days_until_due,
        },
    )


async def publish_quality_measure_at_risk(
    event_bus: Any,
    tenant_id: str,
    measure_id: str,
    measure_name: str,
    current_rate: str,
    target_rate: str,
    correlation_id: str,
) -> None:
    """Publish event when a Star Rating measure is trending below target."""
    await event_bus.publish(
        event_type="quality.measure_at_risk",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        payload={
            "measure_id": measure_id,
            "measure_name": measure_name,
            "current_rate": current_rate,
            "target_rate": target_rate,
            "evaluated_at": datetime.now(UTC).isoformat(),
        },
    )
