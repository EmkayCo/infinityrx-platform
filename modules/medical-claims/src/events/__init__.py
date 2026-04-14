"""Medical-claims event publishers, consumers, and startup wiring.

wire_consumers() requires claim_service and unified_spend_service injections.
Call this from the lifespan coroutine after bus.start().
"""
from __future__ import annotations

import logging
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("medical-claims.events")

_idempotency_store = InMemoryIdempotencyStore()

CONSUMER_ROUTING = {
    "edi.837_received": "handle_edi_837_received",
    "claim.adjudicated": "handle_pharmacy_claim_adjudicated",
}


async def wire_consumers(
    bus: EventBus,
    *,
    claim_service: Any,
    unified_spend_service: Any,
    db: Any,
) -> None:
    """Subscribe all medical-claims consumers at application startup.

    Args:
        bus: The event bus to subscribe to.
        claim_service: Initialized ClaimService (or compatible stub).
        unified_spend_service: Initialized UnifiedSpendService (or compatible stub).
        db: An AsyncSession or compatible database session.
    """
    from .consumers import handle_edi_837_received, handle_pharmacy_claim_adjudicated

    store = _idempotency_store

    async def _handle_edi_837_received(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="medical_claims.edi_837_received"):
            return
        await handle_edi_837_received(envelope, claim_service=claim_service, db=db)
        await store.mark(key, consumer_name="medical_claims.edi_837_received")

    async def _handle_pharmacy_claim_adjudicated(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="medical_claims.claim_adjudicated"):
            return
        await handle_pharmacy_claim_adjudicated(
            envelope, unified_spend_service=unified_spend_service
        )
        await store.mark(key, consumer_name="medical_claims.claim_adjudicated")

    await bus.subscribe("edi.837_received", _handle_edi_837_received)
    await bus.subscribe("claim.adjudicated", _handle_pharmacy_claim_adjudicated)
    logger.info(
        "medical-claims.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
