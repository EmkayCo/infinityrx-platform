"""Unit tests for drug database event publishers."""
from __future__ import annotations

import sys
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest

from shared.events.in_memory_bus import InMemoryEventBus
from src.events.publishers import (
    publish_discontinued,
    publish_generic_available,
    publish_new_product,
    publish_price_change,
    publish_refresh_completed,
)

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
CORRELATION_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


class TestPublishPriceChange:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_price_change(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            price_type="NADAC",
            old_price=Decimal("0.045000"),
            new_price=Decimal("0.050000"),
            change_pct=Decimal("11.1111"),
            effective_date=date(2026, 4, 1),
        )
        events = bus.published
        assert len(events) == 1
        assert events[0].event_type == "drug.price_change"

    @pytest.mark.asyncio
    async def test_price_serialized_as_string(self, bus: InMemoryEventBus) -> None:
        await publish_price_change(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            price_type="NADAC",
            old_price=Decimal("0.045000"),
            new_price=Decimal("0.050000"),
            change_pct=Decimal("11.1111"),
            effective_date=date(2026, 4, 1),
        )
        payload = bus.published[0].payload
        assert isinstance(payload["old_price"], str)
        assert isinstance(payload["new_price"], str)
        assert not isinstance(payload["old_price"], float)

    @pytest.mark.asyncio
    async def test_ordering_key_is_ndc(self, bus: InMemoryEventBus) -> None:
        await publish_price_change(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            price_type="NADAC",
            old_price=Decimal("0.045000"),
            new_price=Decimal("0.050000"),
            change_pct=Decimal("11.1111"),
            effective_date=date(2026, 4, 1),
        )
        assert bus.published[0].ordering_key == "00093314905"

    @pytest.mark.asyncio
    async def test_idempotency_key_is_business_level(self, bus: InMemoryEventBus) -> None:
        await publish_price_change(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            price_type="NADAC",
            old_price=Decimal("0.045000"),
            new_price=Decimal("0.050000"),
            change_pct=Decimal("11.1111"),
            effective_date=date(2026, 4, 1),
        )
        key = bus.published[0].idempotency_key
        assert "00093314905" in key
        assert "NADAC" in key

    @pytest.mark.asyncio
    async def test_schema_version_is_1_0(self, bus: InMemoryEventBus) -> None:
        await publish_price_change(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            price_type="NADAC",
            old_price=Decimal("0.045000"),
            new_price=Decimal("0.050000"),
            change_pct=Decimal("11.1111"),
            effective_date=date(2026, 4, 1),
        )
        assert bus.published[0].schema_version == "1.0"


class TestPublishNewProduct:
    @pytest.mark.asyncio
    async def test_publishes_new_product_event(self, bus: InMemoryEventBus) -> None:
        await publish_new_product(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
            data_source="fda_ndc",
        )
        assert len(bus.published) == 1
        assert bus.published[0].event_type == "drug.new_product"
        assert bus.published[0].payload["ndc_11"] == "00093314905"


class TestPublishDiscontinued:
    @pytest.mark.asyncio
    async def test_publishes_discontinued_event(self, bus: InMemoryEventBus) -> None:
        await publish_discontinued(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            ndc_11="00093314905",
            drug_name="Metformin",
        )
        assert bus.published[0].event_type == "drug.discontinued"


class TestPublishRefreshCompleted:
    @pytest.mark.asyncio
    async def test_publishes_refresh_completed(self, bus: InMemoryEventBus) -> None:
        await publish_refresh_completed(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            data_source="fda_ndc",
            stats={"records_added": 100, "started_at": "2026-01-01T00:00:00"},
        )
        ev = bus.published[0]
        assert ev.event_type == "drug.refresh_completed"
        assert ev.payload["data_source"] == "fda_ndc"
        assert ev.payload["records_added"] == 100


class TestPublishGenericAvailable:
    @pytest.mark.asyncio
    async def test_publishes_generic_available(self, bus: InMemoryEventBus) -> None:
        await publish_generic_available(
            bus=bus,
            tenant_id=TENANT_ID,
            correlation_id=CORRELATION_ID,
            brand_ndc="00002143601",
            generic_ndc="00093314905",
            te_code="AB",
            generic_name="insulin lispro",
        )
        ev = bus.published[0]
        assert ev.event_type == "drug.generic_available"
        assert ev.payload["te_code"] == "AB"
