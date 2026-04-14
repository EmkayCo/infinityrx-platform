"""ReclaimRx event publishers, consumers, and startup wiring.

wire_consumers() subscribes all CONSUMER_ROUTING handlers to the shared EventBus.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

from .consumers import CONSUMER_ROUTING

logger = logging.getLogger("reclaimrx.events")

_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all reclaimrx consumers at application startup.

    ReclaimRx consumers are currently synchronous (dict payload handlers).
    They are wrapped in async adapters here with idempotency checks.
    """
    store = _idempotency_store

    for topic, sync_handler in CONSUMER_ROUTING.items():
        consumer_name = f"reclaimrx.{topic.replace('.', '_')}"

        def _make_async_wrapper(handler, cname: str):  # noqa: ANN001
            async def _async_handler(envelope: EventEnvelope) -> None:
                key = envelope.idempotency_key
                if await store.seen(key, consumer_name=cname):
                    return
                handler(envelope.payload)
                await store.mark(key, consumer_name=cname)

            _async_handler.__name__ = f"reclaimrx_{cname}"
            return _async_handler

        await bus.subscribe(topic, _make_async_wrapper(sync_handler, consumer_name))

    logger.info(
        "reclaimrx.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
