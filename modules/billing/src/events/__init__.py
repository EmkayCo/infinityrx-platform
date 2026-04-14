"""Billing event publishers, consumers, and startup wiring.

wire_consumers() is called from the module lifespan to activate all
consumer subscriptions on the shared EventBus.
"""
from __future__ import annotations

import logging

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("billing.events")

# Shared idempotency store (replaced with PostgresIdempotencyStore at startup)
_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(bus: EventBus) -> None:
    """Subscribe all billing consumers at application startup.

    Each handler is wrapped with idempotency checks per event-bus rules.
    Call this from the lifespan coroutine after bus.start().

    Handlers are dispatched through the consumers module at call time so that
    test patches applied to ``modules.billing.src.events.consumers.*`` are
    respected even after wiring (LESSON-006: test the wire, not the component).
    """
    import modules.billing.src.events.consumers as _consumers

    store = _idempotency_store

    async def _wrap_claim_adjudicated(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="billing.claim_adjudicated"):
            return
        await _consumers.handle_claim_adjudicated(envelope, db=None, bus=bus)
        await store.mark(key, consumer_name="billing.claim_adjudicated")

    async def _wrap_claim_reversed(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="billing.claim_reversed"):
            return
        await _consumers.handle_claim_reversed(envelope, db=None, bus=bus)
        await store.mark(key, consumer_name="billing.claim_reversed")

    async def _wrap_payment_auto_posted(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="billing.payment_auto_posted"):
            return
        await _consumers.handle_payment_auto_posted(envelope, db=None, bus=bus)
        await store.mark(key, consumer_name="billing.payment_auto_posted")

    async def _wrap_member_enrolled(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="billing.member_enrolled"):
            return
        await _consumers.handle_member_enrolled(envelope, db=None, bus=bus)
        await store.mark(key, consumer_name="billing.member_enrolled")

    await bus.subscribe("claim.adjudicated", _wrap_claim_adjudicated)
    await bus.subscribe("claim.reversed", _wrap_claim_reversed)
    await bus.subscribe("payment.auto_posted", _wrap_payment_auto_posted)
    await bus.subscribe("member.enrolled", _wrap_member_enrolled)
    logger.info(
        "billing.consumers_wired",
        extra={
            "svc_topics": "claim.adjudicated,claim.reversed,payment.auto_posted,member.enrolled"
        },
    )
