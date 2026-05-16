"""AI/NLP event publishers, consumers, and startup wiring.

wire_consumers() requires an OpenAIClient and AsyncSession factory.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("ai-nlp.events")

_idempotency_store = InMemoryIdempotencyStore()

# Consumer routing: topic → method name on AiNlpEventConsumer
CONSUMER_ROUTING = {
    "fwa.claim_flagged": "handle_fwa_claim_flagged",
    "fwa.investigation_opened": "handle_fwa_investigation_opened",
}


async def wire_consumers(
    bus: EventBus,
    *,
    openai_client: Any,
    db_factory: Any,
    idempotency_store: Any | None = None,
) -> None:
    """Subscribe all ai-nlp consumers at application startup.

    AiNlpEventConsumer is class-based and requires injected dependencies.
    A new consumer instance is created per envelope — stateless pattern.

    CR-01 v2 BLOCK-3 fix: openai_client must be a real OpenAIClient, not None.
    With None, events were marked as processed but NLP analysis was skipped —
    silent data loss. Fail-fast startup in app.py ensures this is never None.

    Args:
        bus: The event bus to subscribe to.
        openai_client: An initialized OpenAIClient instance (must not be None).
        db_factory: Callable that returns an AsyncSession (or None for no-DB mode).
        idempotency_store: Optional override for tests — use a fresh store per test.
    """
    from .consumers import AiNlpEventConsumer

    store = idempotency_store if idempotency_store is not None else _idempotency_store

    async def _handle_fwa_claim_flagged(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="ai_nlp.fwa_claim_flagged"):
            return
        consumer = AiNlpEventConsumer(
            db=db_factory() if db_factory else None,
            openai_client=openai_client,
        )
        await consumer.handle_fwa_claim_flagged(envelope.payload)
        await store.mark(key, consumer_name="ai_nlp.fwa_claim_flagged")

    async def _handle_fwa_investigation_opened(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="ai_nlp.fwa_investigation_opened"):
            return
        consumer = AiNlpEventConsumer(
            db=db_factory() if db_factory else None,
            openai_client=openai_client,
        )
        await consumer.handle_fwa_investigation_opened(envelope.payload)
        await store.mark(key, consumer_name="ai_nlp.fwa_investigation_opened")

    await bus.subscribe("fwa.claim_flagged", _handle_fwa_claim_flagged)
    await bus.subscribe("fwa.investigation_opened", _handle_fwa_investigation_opened)
    logger.info(
        "ai-nlp.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
