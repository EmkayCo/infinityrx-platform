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
            f"paysync:inbox:list:{tenant_id}:operator"
        ])

        with patch("src.events.upload_events._get_redis", return_value=mock_redis):
            await handle_upload_parsed(envelope)

        mock_redis.delete.assert_called()

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
