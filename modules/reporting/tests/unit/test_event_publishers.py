"""Unit tests for reporting event publishers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.events.publishers import (
    publish_quality_measure_at_risk,
    publish_regulatory_deadline_approaching,
    publish_report_delivered,
    publish_report_delivery_failed,
    publish_report_generated,
)


def _mock_bus() -> MagicMock:
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


class TestPublishReportGenerated:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self) -> None:
        bus = _mock_bus()
        await publish_report_generated(bus, "t1", "run1", "def1", 100, "excel", "corr1")
        bus.publish.assert_called_once()
        call_kwargs = bus.publish.call_args
        assert call_kwargs.kwargs["event_type"] == "report.generated"

    @pytest.mark.asyncio
    async def test_payload_contains_run_id(self) -> None:
        bus = _mock_bus()
        await publish_report_generated(bus, "t1", "run999", "def1", 50, "csv", "c1")
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["report_run_id"] == "run999"

    @pytest.mark.asyncio
    async def test_payload_contains_row_count(self) -> None:
        bus = _mock_bus()
        await publish_report_generated(bus, "t1", "r1", "d1", 12345, "excel", "c1")
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["row_count"] == 12345


class TestPublishReportDelivered:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self) -> None:
        bus = _mock_bus()
        await publish_report_delivered(bus, "t1", "run1", "email", "corr1")
        assert bus.publish.call_args.kwargs["event_type"] == "report.delivered"

    @pytest.mark.asyncio
    async def test_payload_contains_delivery_method(self) -> None:
        bus = _mock_bus()
        await publish_report_delivered(bus, "t1", "run1", "sftp", "c1")
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["delivery_method"] == "sftp"


class TestPublishReportDeliveryFailed:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self) -> None:
        bus = _mock_bus()
        await publish_report_delivery_failed(bus, "t1", "run1", "email", "smtp error", "c1")
        assert bus.publish.call_args.kwargs["event_type"] == "report.delivery_failed"

    @pytest.mark.asyncio
    async def test_payload_contains_error(self) -> None:
        bus = _mock_bus()
        await publish_report_delivery_failed(bus, "t1", "r1", "email", "Connection refused", "c1")
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["error"] == "Connection refused"


class TestPublishRegulatoryDeadline:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self) -> None:
        bus = _mock_bus()
        await publish_regulatory_deadline_approaching(
            bus, "t1", "sub1", "caa_transparency_semiannual", "2026-06-30", 14, "c1"
        )
        assert bus.publish.call_args.kwargs["event_type"] == "regulatory.deadline_approaching"

    @pytest.mark.asyncio
    async def test_payload_days_until_due(self) -> None:
        bus = _mock_bus()
        await publish_regulatory_deadline_approaching(
            bus, "t1", "sub1", "star_ratings", "2026-12-31", 30, "c1"
        )
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["days_until_due"] == 30


class TestPublishQualityMeasureAtRisk:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self) -> None:
        bus = _mock_bus()
        await publish_quality_measure_at_risk(
            bus, "t1", "D01", "statin_adherence", "0.78", "0.80", "c1"
        )
        assert bus.publish.call_args.kwargs["event_type"] == "quality.measure_at_risk"

    @pytest.mark.asyncio
    async def test_payload_contains_measure_id(self) -> None:
        bus = _mock_bus()
        await publish_quality_measure_at_risk(bus, "t1", "D03", "ras", "0.75", "0.80", "c1")
        payload = bus.publish.call_args.kwargs["payload"]
        assert payload["measure_id"] == "D03"
