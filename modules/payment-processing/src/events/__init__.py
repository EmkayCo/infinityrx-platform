"""Payment-processing event publishers, consumers, and startup wiring.

wire_consumers() subscribes all consumer handlers to the shared EventBus.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("payment-processing.events")

_idempotency_store = InMemoryIdempotencyStore()

# Consumer routing: topic → sync handler
CONSUMER_ROUTING: dict[str, str] = {
    "payment_batch.submitted": "handle_payment_batch_submitted",
    "fwa.payment_hold_placed": "handle_fwa_hold_placed",
    "fwa.payment_hold_released": "handle_fwa_hold_released",
}


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all payment-processing consumers at application startup.

    Handlers are sync — wrapped in async adapters with idempotency checks.
    """
    from .consumers import (
        handle_fwa_hold_placed,
        handle_fwa_hold_released,
        handle_payment_batch_submitted,
    )

    store = _idempotency_store

    routing = {
        "payment_batch.submitted": (handle_payment_batch_submitted, "payment.batch_submitted"),
        "fwa.payment_hold_placed": (handle_fwa_hold_placed, "payment.fwa_hold_placed"),
        "fwa.payment_hold_released": (handle_fwa_hold_released, "payment.fwa_hold_released"),
    }

    for topic, (sync_handler, consumer_name) in routing.items():
        def _make_wrapper(handler, cname: str):  # noqa: ANN001
            async def _async_handler(envelope: EventEnvelope) -> None:
                key = envelope.idempotency_key
                if await store.seen(key, consumer_name=cname):
                    return
                handler(envelope.payload)
                await store.mark(key, consumer_name=cname)

            _async_handler.__name__ = f"payment_{cname}"
            return _async_handler

        await bus.subscribe(topic, _make_wrapper(sync_handler, consumer_name))

    logger.info(
        "payment-processing.consumers_wired",
        extra={"svc_topics": ",".join(routing.keys())},
    )
