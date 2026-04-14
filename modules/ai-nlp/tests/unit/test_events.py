"""Unit tests for AI/NLP event consumers and publishers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.events.consumers import AiNlpEventConsumer
from src.events.publishers import AiNlpEventPublisher


class TestAiNlpEventPublisher:
    @pytest.fixture()
    def mock_bus(self) -> MagicMock:
        bus = MagicMock()
        bus.publish = AsyncMock()
        return bus

    @pytest.mark.asyncio
    async def test_publish_document_processed_event(self, mock_bus: MagicMock) -> None:
        pub = AiNlpEventPublisher(event_bus=mock_bus)
        await pub.document_processed(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            document_type="eob",
            confidence=0.92,
            correlation_id=uuid4(),
        )
        mock_bus.publish.assert_called_once()
        call_kwargs = mock_bus.publish.call_args[1]
        assert call_kwargs["event_type"] == "ai.document_processed"

    @pytest.mark.asyncio
    async def test_publish_confidence_low_event(self, mock_bus: MagicMock) -> None:
        pub = AiNlpEventPublisher(event_bus=mock_bus)
        await pub.confidence_low(
            tenant_id=uuid4(),
            service_request_id=uuid4(),
            service_type="document_extraction",
            confidence=0.55,
            correlation_id=uuid4(),
        )
        mock_bus.publish.assert_called_once()
        call_kwargs = mock_bus.publish.call_args[1]
        assert call_kwargs["event_type"] == "ai.confidence_low"

    @pytest.mark.asyncio
    async def test_publish_conversation_escalated_event(self, mock_bus: MagicMock) -> None:
        pub = AiNlpEventPublisher(event_bus=mock_bus)
        await pub.conversation_escalated(
            tenant_id=uuid4(),
            conversation_id=uuid4(),
            escalation_reason="consecutive_low_confidence",
            correlation_id=uuid4(),
        )
        mock_bus.publish.assert_called_once()
        call_kwargs = mock_bus.publish.call_args[1]
        assert call_kwargs["event_type"] == "ai.conversation_escalated"

    @pytest.mark.asyncio
    async def test_event_payload_includes_tenant_id(self, mock_bus: MagicMock) -> None:
        pub = AiNlpEventPublisher(event_bus=mock_bus)
        tid = uuid4()
        await pub.document_processed(
            tenant_id=tid,
            service_request_id=uuid4(),
            document_type="eob",
            confidence=0.90,
            correlation_id=uuid4(),
        )
        call_kwargs = mock_bus.publish.call_args[1]
        assert call_kwargs["tenant_id"] == tid


class TestAiNlpEventConsumer:
    @pytest.fixture()
    def mock_db(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture()
    def mock_openai(self) -> MagicMock:
        client = MagicMock()
        client.complete = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_handles_fwa_claim_flagged_event(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse
        from decimal import Decimal

        mock_openai.complete.return_value = OpenAIResponse(
            content="This pharmacy shows NQ inflation anomaly...",
            model="gpt-4.1",
            prompt_tokens=200,
            completion_tokens=150,
            total_cost_usd=Decimal("0.008"),
        )

        consumer = AiNlpEventConsumer(db=mock_db, openai_client=mock_openai)
        payload = {
            "tenant_id": str(uuid4()),
            "claim_id": str(uuid4()),
            "entity_type": "pharmacy",
            "entity_id": str(uuid4()),
            "flag_type": "nq_inflation",
            "evidence": {"ratio": 1.52},
            "claim_count": 47,
            "correlation_id": str(uuid4()),
        }
        await consumer.handle_fwa_claim_flagged(payload)
        mock_openai.complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_unknown_event_fields_gracefully(
        self, mock_db: AsyncMock, mock_openai: MagicMock
    ) -> None:
        from shared.ai.openai_client import OpenAIResponse
        from decimal import Decimal

        mock_openai.complete.return_value = OpenAIResponse(
            content="Narrative here",
            model="gpt-4.1",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost_usd=Decimal("0.003"),
        )

        consumer = AiNlpEventConsumer(db=mock_db, openai_client=mock_openai)
        payload = {
            "tenant_id": str(uuid4()),
            "claim_id": str(uuid4()),
            "entity_type": "pharmacy",
            "entity_id": str(uuid4()),
            "flag_type": "nq_inflation",
            "evidence": {},
            "claim_count": 1,
            "correlation_id": str(uuid4()),
            "unknown_future_field": "should be ignored",
        }
        await consumer.handle_fwa_claim_flagged(payload)
