"""Reporting event publishers, consumers, and startup wiring.

wire_consumers() subscribes all EVENT_HANDLERS to the shared EventBus.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("reporting.events")

_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all reporting consumers at application startup.

    Reporting consumers accept (payload, tenant_id) — wrapped here to
    extract those values from the EventEnvelope.
    """
    from .consumers import EVENT_HANDLERS

    store = _idempotency_store

    for topic, handler in EVENT_HANDLERS.items():
        consumer_name = f"reporting.{topic.replace('.', '_')}"

        def _make_wrapper(h, cname: str):  # noqa: ANN001
            async def _async_handler(envelope: EventEnvelope) -> None:
                key = envelope.idempotency_key
                if await store.seen(key, consumer_name=cname):
                    return
                await h(envelope.payload, str(envelope.tenant_id))
                await store.mark(key, consumer_name=cname)

            _async_handler.__name__ = f"reporting_{cname}"
            return _async_handler

        await bus.subscribe(topic, _make_wrapper(handler, consumer_name))

    logger.info(
        "reporting.consumers_wired",
        extra={"svc_topics": ",".join(EVENT_HANDLERS.keys())},
    )
