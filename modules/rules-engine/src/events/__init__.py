"""Rules-engine event publishers, consumers, and startup wiring.

wire_consumers() is called from the module lifespan to activate all
consumer subscriptions on the shared EventBus.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("rules_engine.events")

_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Subscribe all rules-engine consumers at application startup."""
    from src.events import consumers as _consumers  # noqa: PLC0415

    store = _idempotency_store

    def _make_wrapper(handler_attr: str, consumer_name: str):
        async def _async_handler(envelope: EventEnvelope) -> None:
            key = envelope.idempotency_key
            if await store.seen(key, consumer_name=consumer_name):
                return
            handler = getattr(_consumers, handler_attr)
            await handler(envelope, bus=bus)
            await store.mark(key, consumer_name=consumer_name)

        _async_handler.__name__ = f"rules_engine_{consumer_name}"
        return _async_handler

    await bus.subscribe(
        "claim.submitted",
        _make_wrapper("handle_claim_submitted", "rules_engine.claim_submitted"),
    )
    await bus.subscribe(
        "plan.updated",
        _make_wrapper("handle_plan_updated", "rules_engine.plan_updated"),
    )
    await bus.subscribe(
        "drug.price_updated",
        _make_wrapper("handle_drug_price_updated", "rules_engine.drug_price_updated"),
    )
    logger.info(
        "rules_engine.consumers_wired",
        extra={
            "svc_topics": "claim.submitted,plan.updated,drug.price_updated",
        },
    )
