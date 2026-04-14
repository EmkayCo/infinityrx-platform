"""AI/NLP event publishers.

All events use dot-notation event types per event-bus rules.
Every event includes tenant_id in the payload.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


class AiNlpEventPublisher:
    """Publishes AI/NLP domain events to the event bus."""

    def __init__(self, event_bus: Any) -> None:
        self._bus = event_bus

    async def document_processed(
        self,
        tenant_id: UUID,
        service_request_id: UUID,
        document_type: str,
        confidence: float,
        correlation_id: UUID,
    ) -> None:
        await self._bus.publish(
            event_type="ai.document_processed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "service_request_id": str(service_request_id),
                "document_type": document_type,
                "confidence": confidence,
            },
        )

    async def content_generated(
        self,
        tenant_id: UUID,
        service_request_id: UUID,
        template_name: str,
        correlation_id: UUID,
    ) -> None:
        await self._bus.publish(
            event_type="ai.content_generated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "service_request_id": str(service_request_id),
                "template_name": template_name,
            },
        )

    async def confidence_low(
        self,
        tenant_id: UUID,
        service_request_id: UUID,
        service_type: str,
        confidence: float,
        correlation_id: UUID,
    ) -> None:
        await self._bus.publish(
            event_type="ai.confidence_low",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "service_request_id": str(service_request_id),
                "service_type": service_type,
                "confidence": confidence,
            },
        )

    async def conversation_escalated(
        self,
        tenant_id: UUID,
        conversation_id: UUID,
        escalation_reason: str,
        correlation_id: UUID,
    ) -> None:
        await self._bus.publish(
            event_type="ai.conversation_escalated",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "conversation_id": str(conversation_id),
                "escalation_reason": escalation_reason,
            },
        )

    async def document_routed(
        self,
        tenant_id: UUID,
        service_request_id: UUID,
        document_type: str,
        target_module: str,
        correlation_id: UUID,
    ) -> None:
        await self._bus.publish(
            event_type="ai.document_routed",
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            payload={
                "service_request_id": str(service_request_id),
                "document_type": document_type,
                "target_module": target_module,
            },
        )
