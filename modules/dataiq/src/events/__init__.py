"""DataIQ event publishers, consumers, and startup wiring.

wire_consumers() requires a Redis client instance.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging
from typing import Any

from shared.events.bus import EventBus
from shared.events.types import EventEnvelope

logger = logging.getLogger("dataiq.events")

# Consumer routing: topic → factory function name
CONSUMER_ROUTING = {
    "claim.ingested": "make_claim_ingested_handler",
    "fwa.claim_flagged": "make_fwa_flagged_handler",
    "payment.settled": "make_payment_settled_handler",
}


async def wire_consumers(bus: EventBus, *, redis: Any) -> None:
    """Subscribe all dataiq consumers at application startup.

    DataIQ consumers are factory-built with idempotency already embedded.
    The factory returns a handler that accepts (idempotency_key, envelope).
    We wrap in a thin adapter here to conform to the EventBus handler signature.

    Args:
        bus: The event bus to subscribe to.
        redis: An initialized aioredis client for KPI counter updates.
    """
    from .consumers import (
        make_claim_ingested_handler,
        make_fwa_flagged_handler,
        make_payment_settled_handler,
    )

    claim_ingested_handler = make_claim_ingested_handler(redis)
    fwa_flagged_handler = make_fwa_flagged_handler(redis)
    payment_settled_handler = make_payment_settled_handler(redis)

    async def _dispatch_claim_ingested(envelope: EventEnvelope) -> None:
        await claim_ingested_handler(envelope.idempotency_key, envelope)

    async def _dispatch_fwa_flagged(envelope: EventEnvelope) -> None:
        await fwa_flagged_handler(envelope.idempotency_key, envelope)

    async def _dispatch_payment_settled(envelope: EventEnvelope) -> None:
        await payment_settled_handler(envelope.idempotency_key, envelope)

    await bus.subscribe("claim.ingested", _dispatch_claim_ingested)
    await bus.subscribe("fwa.claim_flagged", _dispatch_fwa_flagged)
    await bus.subscribe("payment.settled", _dispatch_payment_settled)
    logger.info(
        "dataiq.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
