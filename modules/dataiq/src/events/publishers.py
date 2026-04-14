"""DataIQ event publishers.

Published events:
  dataiq.anomaly_detected      — SPC anomaly on any metric
  dataiq.data_quality_degraded — quality score below threshold
  dataiq.benchmark_breach      — metric crossed benchmark threshold
  dataiq.insight_generated     — auto-generated insight
  dataiq.forecast_deviation    — actual deviates from forecast by >X%

All events use EventEnvelope with ordering_key, idempotency_key, schema_version.
Decimal amounts serialized as str() in payload.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

SOURCE_MODULE = "dataiq"


async def publish_anomaly_detected(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    metric_key: str,
    value: Decimal,
    ucl: Decimal,
    lcl: Decimal,
    rule_id: int,
    severity: str,
) -> None:
    """Publish dataiq.anomaly_detected event."""
    envelope = EventEnvelope(
        event_type="dataiq.anomaly_detected",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=f"{tenant_id}:{metric_key}",
        idempotency_key=f"anomaly:{tenant_id}:{metric_key}:{rule_id}",
        payload={
            "metric_key": metric_key,
            "value": str(value),
            "ucl": str(ucl),
            "lcl": str(lcl),
            "rule_id": rule_id,
            "severity": severity,
        },
    )
    await bus.publish(envelope)


async def publish_data_quality_degraded(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    score_date: str,
    overall_score: Decimal,
    threshold: Decimal,
) -> None:
    """Publish dataiq.data_quality_degraded event."""
    envelope = EventEnvelope(
        event_type="dataiq.data_quality_degraded",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=str(tenant_id),
        idempotency_key=f"dq_degraded:{tenant_id}:{score_date}",
        payload={
            "score_date": score_date,
            "overall_score": str(overall_score),
            "threshold": str(threshold),
        },
    )
    await bus.publish(envelope)


async def publish_benchmark_breach(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    benchmark_id: uuid.UUID,
    metric_key: str,
    current_value: Decimal,
    threshold_value: Decimal,
    severity: str,
) -> None:
    """Publish dataiq.benchmark_breach event."""
    envelope = EventEnvelope(
        event_type="dataiq.benchmark_breach",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=f"{tenant_id}:{metric_key}",
        idempotency_key=f"benchmark_breach:{tenant_id}:{benchmark_id}",
        payload={
            "benchmark_id": str(benchmark_id),
            "metric_key": metric_key,
            "current_value": str(current_value),
            "threshold_value": str(threshold_value),
            "severity": severity,
        },
    )
    await bus.publish(envelope)


async def publish_insight_generated(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    insight_id: uuid.UUID,
    insight_type: str,
    severity: str,
    title: str,
) -> None:
    """Publish dataiq.insight_generated event."""
    envelope = EventEnvelope(
        event_type="dataiq.insight_generated",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=str(tenant_id),
        idempotency_key=f"insight:{tenant_id}:{insight_id}",
        payload={
            "insight_id": str(insight_id),
            "insight_type": insight_type,
            "severity": severity,
            "title": title,
        },
    )
    await bus.publish(envelope)


async def publish_forecast_deviation(
    bus: EventBus,
    tenant_id: uuid.UUID,
    correlation_id: uuid.UUID,
    forecast_id: uuid.UUID,
    metric_key: str,
    predicted_value: Decimal,
    actual_value: Decimal,
    deviation_pct: Decimal,
) -> None:
    """Publish dataiq.forecast_deviation event."""
    envelope = EventEnvelope(
        event_type="dataiq.forecast_deviation",
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        source_module=SOURCE_MODULE,
        schema_version="1.0",
        ordering_key=f"{tenant_id}:{metric_key}",
        idempotency_key=f"forecast_deviation:{tenant_id}:{forecast_id}",
        payload={
            "forecast_id": str(forecast_id),
            "metric_key": metric_key,
            "predicted_value": str(predicted_value),
            "actual_value": str(actual_value),
            "deviation_pct": str(deviation_pct),
        },
    )
    await bus.publish(envelope)
