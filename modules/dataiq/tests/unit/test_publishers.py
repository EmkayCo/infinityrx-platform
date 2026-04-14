"""Unit tests for DataIQ event publishers.

Verifies event envelopes have correct structure, Decimal serialized as str,
and all required fields (ordering_key, idempotency_key, schema_version).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from src.events.publishers import (
    publish_anomaly_detected,
    publish_benchmark_breach,
    publish_data_quality_degraded,
    publish_forecast_deviation,
    publish_insight_generated,
)

from shared.events.types import EventEnvelope


@pytest.fixture()
def mock_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
CORRELATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class TestPublishAnomalyDetected:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_bus: AsyncMock) -> None:
        await publish_anomaly_detected(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            metric_key="claim_count",
            value=Decimal("500"),
            ucl=Decimal("300"),
            lcl=Decimal("100"),
            rule_id=1,
            severity="critical",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "dataiq.anomaly_detected"

    @pytest.mark.asyncio
    async def test_decimal_values_serialized_as_strings(self, mock_bus: AsyncMock) -> None:
        await publish_anomaly_detected(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            metric_key="claim_count",
            value=Decimal("500.25"),
            ucl=Decimal("300.00"),
            lcl=Decimal("100.00"),
            rule_id=1,
            severity="critical",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        payload = envelope.payload
        assert payload["value"] == "500.25"
        assert payload["ucl"] == "300.00"
        assert payload["lcl"] == "100.00"
        assert not isinstance(payload["value"], float)

    @pytest.mark.asyncio
    async def test_envelope_has_ordering_key(self, mock_bus: AsyncMock) -> None:
        await publish_anomaly_detected(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            metric_key="claim_count",
            value=Decimal("500"),
            ucl=Decimal("300"),
            lcl=Decimal("100"),
            rule_id=1,
            severity="warning",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.ordering_key is not None
        assert str(TENANT_ID) in envelope.ordering_key

    @pytest.mark.asyncio
    async def test_envelope_has_schema_version(self, mock_bus: AsyncMock) -> None:
        await publish_anomaly_detected(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            metric_key="claim_count",
            value=Decimal("500"),
            ucl=Decimal("300"),
            lcl=Decimal("100"),
            rule_id=1,
            severity="warning",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.schema_version == "1.0"

    @pytest.mark.asyncio
    async def test_envelope_has_idempotency_key(self, mock_bus: AsyncMock) -> None:
        await publish_anomaly_detected(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            metric_key="claim_count",
            value=Decimal("500"),
            ucl=Decimal("300"),
            lcl=Decimal("100"),
            rule_id=1,
            severity="warning",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.idempotency_key
        assert envelope.idempotency_key != str(envelope.event_id)


class TestPublishDataQualityDegraded:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_bus: AsyncMock) -> None:
        await publish_data_quality_degraded(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            score_date="2026-04-13",
            overall_score=Decimal("82.50"),
            threshold=Decimal("95.00"),
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "dataiq.data_quality_degraded"

    @pytest.mark.asyncio
    async def test_score_serialized_as_string(self, mock_bus: AsyncMock) -> None:
        await publish_data_quality_degraded(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            score_date="2026-04-13",
            overall_score=Decimal("82.50"),
            threshold=Decimal("95.00"),
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.payload["overall_score"] == "82.50"
        assert not isinstance(envelope.payload["overall_score"], float)


class TestPublishBenchmarkBreach:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_bus: AsyncMock) -> None:
        await publish_benchmark_breach(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            benchmark_id=uuid.uuid4(),
            metric_key="generic_fill_rate",
            current_value=Decimal("0.72"),
            threshold_value=Decimal("0.80"),
            severity="warning",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "dataiq.benchmark_breach"


class TestPublishInsightGenerated:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_bus: AsyncMock) -> None:
        await publish_insight_generated(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            insight_id=uuid.uuid4(),
            insight_type="spend_spike",
            severity="warning",
            title="Drug spend increased 25% week-over-week",
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "dataiq.insight_generated"


class TestPublishForecastDeviation:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_bus: AsyncMock) -> None:
        await publish_forecast_deviation(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            forecast_id=uuid.uuid4(),
            metric_key="total_spend",
            predicted_value=Decimal("100000.00"),
            actual_value=Decimal("130000.00"),
            deviation_pct=Decimal("30.00"),
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "dataiq.forecast_deviation"

    @pytest.mark.asyncio
    async def test_decimal_amounts_serialized_as_strings(self, mock_bus: AsyncMock) -> None:
        await publish_forecast_deviation(
            bus=mock_bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            forecast_id=uuid.uuid4(),
            metric_key="total_spend",
            predicted_value=Decimal("100000.00"),
            actual_value=Decimal("130000.00"),
            deviation_pct=Decimal("30.00"),
        )
        envelope: EventEnvelope = mock_bus.publish.call_args[0][0]
        payload = envelope.payload
        assert payload["predicted_value"] == "100000.00"
        assert payload["actual_value"] == "130000.00"
        assert payload["deviation_pct"] == "30.00"
        assert not isinstance(payload["predicted_value"], float)
