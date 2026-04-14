"""Tests for event publisher — correct event_type, ordering_key, idempotency_key."""
from __future__ import annotations

import uuid

import pytest

from shared.events.in_memory_bus import InMemoryEventBus

from src.events.publisher import (
    publish_application_submitted,
    publish_credential_expiring,
    publish_credentialing_completed,
    publish_network_added,
    publish_network_removed,
    publish_pharmacy_created,
    publish_pharmacy_deactivated,
    publish_pharmacy_ownership_changed,
    publish_pharmacy_updated,
)

TENANT_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")
CORR_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")
PHARMACY_ID = str(uuid.uuid4())
NETWORK_ID = str(uuid.uuid4())
APP_ID = str(uuid.uuid4())
MEMBER_ID = str(uuid.uuid4())


@pytest.fixture
def bus() -> InMemoryEventBus:
    b = InMemoryEventBus()
    return b


class TestEventPublisher:
    @pytest.mark.asyncio
    async def test_pharmacy_created_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_created(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].event_type == "pharmacy.created"

    @pytest.mark.asyncio
    async def test_pharmacy_created_ordering_key_is_pharmacy_id(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_created(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].ordering_key == PHARMACY_ID

    @pytest.mark.asyncio
    async def test_pharmacy_updated_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_updated(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890", ["address_line_1"])
        assert bus.published[0].event_type == "pharmacy.updated"

    @pytest.mark.asyncio
    async def test_pharmacy_ownership_changed_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_ownership_changed(
            bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890", "Old Owner", "New Owner"
        )
        assert bus.published[0].event_type == "pharmacy.ownership_changed"

    @pytest.mark.asyncio
    async def test_pharmacy_deactivated_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_deactivated(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].event_type == "pharmacy.deactivated"

    @pytest.mark.asyncio
    async def test_network_added_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_network_added(bus, TENANT_ID, CORR_ID, PHARMACY_ID, NETWORK_ID, MEMBER_ID)
        assert bus.published[0].event_type == "pharmacy.network_added"

    @pytest.mark.asyncio
    async def test_network_removed_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_network_removed(bus, TENANT_ID, CORR_ID, PHARMACY_ID, NETWORK_ID, MEMBER_ID)
        assert bus.published[0].event_type == "pharmacy.network_removed"

    @pytest.mark.asyncio
    async def test_credential_expiring_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_credential_expiring(
            bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890", "state_license", 30
        )
        assert bus.published[0].event_type == "pharmacy.credential_expiring"

    @pytest.mark.asyncio
    async def test_credential_expiring_payload_has_days(self, bus: InMemoryEventBus) -> None:
        await publish_credential_expiring(
            bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890", "dea", 60
        )
        assert bus.published[0].payload["days_until_expiry"] == 60

    @pytest.mark.asyncio
    async def test_credentialing_completed_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_credentialing_completed(
            bus, TENANT_ID, CORR_ID, APP_ID, PHARMACY_ID, "1234567890", "approved"
        )
        assert bus.published[0].event_type == "pharmacy.credentialing_completed"

    @pytest.mark.asyncio
    async def test_application_submitted_event_type(self, bus: InMemoryEventBus) -> None:
        await publish_application_submitted(bus, TENANT_ID, CORR_ID, APP_ID, "1234567890")
        assert bus.published[0].event_type == "pharmacy.application_submitted"

    @pytest.mark.asyncio
    async def test_all_events_have_schema_version_1_0(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_created(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].schema_version == "1.0"

    @pytest.mark.asyncio
    async def test_all_events_have_idempotency_key(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_created(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].idempotency_key

    @pytest.mark.asyncio
    async def test_all_events_have_tenant_id(self, bus: InMemoryEventBus) -> None:
        await publish_pharmacy_created(bus, TENANT_ID, CORR_ID, PHARMACY_ID, "1234567890")
        assert bus.published[0].tenant_id == TENANT_ID
