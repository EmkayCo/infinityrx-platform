"""Unit tests for upload_events.py (Task 3b — Plan B).

Covers:
- publish_upload_parsed: EventEnvelope shape (all required fields)
- Consumer decorated with @idempotent_handler logic
- Forward-compat: consumer handles extra unknown fields gracefully
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture()
def mock_upload():
    upload = MagicMock()
    upload.id = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
    upload.tenant_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    upload.status = "validated"
    upload.row_count = 10
    upload.error_count = 0
    return upload


@pytest.fixture()
def mock_bus():
    bus = MagicMock()
    bus.publish = AsyncMock()
    return bus


class TestPublishUploadParsed:
    @pytest.mark.asyncio
    async def test_publishes_correct_event_type(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        mock_bus.publish.assert_called_once()
        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.event_type == "paysync.upload.parsed"

    @pytest.mark.asyncio
    async def test_publishes_correct_tenant_id(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.tenant_id == mock_upload.tenant_id

    @pytest.mark.asyncio
    async def test_publishes_correct_correlation_id(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.correlation_id == correlation_id

    @pytest.mark.asyncio
    async def test_publishes_source_module_billing(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.source_module == "billing"

    @pytest.mark.asyncio
    async def test_publishes_correct_ordering_key(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.ordering_key == str(mock_upload.id)

    @pytest.mark.asyncio
    async def test_publishes_correct_idempotency_key(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.idempotency_key == f"paysync:upload:{mock_upload.id}:parsed"

    @pytest.mark.asyncio
    async def test_publishes_schema_version_1_0(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        assert envelope.schema_version == "1.0"

    @pytest.mark.asyncio
    async def test_payload_contains_required_fields(self, mock_upload, mock_bus):
        from src.events.upload_events import publish_upload_parsed

        correlation_id = uuid.uuid4()
        await publish_upload_parsed(mock_bus, upload=mock_upload, correlation_id=correlation_id)

        envelope = mock_bus.publish.call_args[0][0]
        payload = envelope.payload
        assert "upload_id" in payload
        assert "tenant_id" in payload
        assert "status" in payload
        assert "row_count" in payload
        assert "error_count" in payload


class TestUploadParsedConsumer:
    @pytest.mark.asyncio
    async def test_consumer_invalidates_redis_cache(self):
        from src.events.upload_events import handle_upload_parsed
        from shared.events.types import EventEnvelope

        tenant_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="paysync.upload.parsed",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(upload_id),
            idempotency_key=f"paysync:upload:{upload_id}:parsed",
            payload={
                "upload_id": str(upload_id),
                "tenant_id": str(tenant_id),
                "status": "validated",
                "row_count": 10,
                "error_count": 0,
            },
        )
        mock_redis = MagicMock()
        mock_redis.delete = MagicMock()
        mock_redis.scan_iter = MagicMock(return_value=[
            f"tenant:{tenant_id}:paysync:inbox:list:operator"
        ])

        with patch("src.events.upload_events._get_redis", return_value=mock_redis):
            await handle_upload_parsed(envelope)

        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_consumer_uses_tenant_prefixed_redis_key_pattern(self):
        """B6: Redis scan pattern must use tenant:{tenant_id}: prefix.

        The tenant-isolation hard rule (tenant-isolation.md) requires ALL Redis
        keys to be prefixed with tenant:{tenant_id}:. The old pattern
        paysync:inbox:list:{tenant_id}:* violates this rule.
        Correct pattern: tenant:{tenant_id}:paysync:inbox:list:*
        """
        from src.events.upload_events import handle_upload_parsed
        from shared.events.types import EventEnvelope

        tenant_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="paysync.upload.parsed",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="billing",
            schema_version="1.0",
            ordering_key=str(upload_id),
            idempotency_key=f"paysync:upload:{upload_id}:parsed",
            payload={
                "upload_id": str(upload_id),
                "tenant_id": str(tenant_id),
                "status": "validated",
                "row_count": 10,
                "error_count": 0,
            },
        )
        mock_redis = MagicMock()
        mock_redis.delete = MagicMock()
        mock_redis.scan_iter = MagicMock(return_value=[])

        with patch("src.events.upload_events._get_redis", return_value=mock_redis):
            await handle_upload_parsed(envelope)

        # Assert scan_iter was called with the tenant-prefixed pattern
        mock_redis.scan_iter.assert_called_once()
        actual_pattern = mock_redis.scan_iter.call_args[0][0]
        expected_pattern = f"tenant:{tenant_id}:paysync:inbox:list:*"
        assert actual_pattern == expected_pattern, (
            f"B6: Redis scan pattern must be tenant-prefixed. "
            f"Expected: {expected_pattern!r}, got: {actual_pattern!r}. "
            f"See .claude/rules/tenant-isolation.md"
        )

    @pytest.mark.asyncio
    async def test_consumer_handles_unknown_fields_gracefully(self):
        """Forward-compat: extra payload fields must not raise."""
        from src.events.upload_events import handle_upload_parsed
        from shared.events.types import EventEnvelope

        tenant_id = uuid.uuid4()
        upload_id = uuid.uuid4()
        envelope = EventEnvelope(
            event_type="paysync.upload.parsed",
            tenant_id=tenant_id,
            correlation_id=uuid.uuid4(),
            source_module="billing",
            schema_version="2.0",  # future version
            ordering_key=str(upload_id),
            idempotency_key=f"paysync:upload:{upload_id}:parsed",
            payload={
                "upload_id": str(upload_id),
                "tenant_id": str(tenant_id),
                "status": "validated",
                "row_count": 10,
                "error_count": 0,
                "new_field_v2": "should_be_ignored",  # unknown — must not raise
            },
        )
        mock_redis = MagicMock()
        mock_redis.delete = MagicMock()
        mock_redis.scan_iter = MagicMock(return_value=[])

        with patch("src.events.upload_events._get_redis", return_value=mock_redis):
            # Must not raise
            await handle_upload_parsed(envelope)

    @pytest.mark.asyncio
    async def test_upload_parsed_wired_via_make_wrapper_not_hand_rolled(self):
        """B5: paysync.upload.parsed consumer must be wired via _make_wrapper
        (the shared idempotency wrapper), not a hand-rolled seen/mark block.

        Verifies that the wire_consumers subscription for paysync.upload.parsed
        goes through _make_wrapper by confirming the registered handler name
        follows the billing_{consumer_name} convention set by _make_wrapper.
        """
        from unittest.mock import AsyncMock, MagicMock

        from shared.events.bus import EventBus
        from src.events import wire_consumers

        class _FakeBus(EventBus):
            def __init__(self):
                self._subs: dict[str, object] = {}

            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def publish(self, envelope):
                pass

            async def subscribe(self, topic: str, handler) -> None:
                self._subs[topic] = handler

        bus = _FakeBus()
        await wire_consumers(bus)

        handler = bus._subs.get("paysync.upload.parsed")
        assert handler is not None, "paysync.upload.parsed must be subscribed"
        # _make_wrapper sets __name__ = f"billing_{consumer_name}"
        assert handler.__name__.startswith("billing_"), (
            f"Handler must be wrapped via _make_wrapper (name starts with 'billing_'), "
            f"got: {handler.__name__!r}. B5: replace hand-rolled idempotency with _make_wrapper."
        )
