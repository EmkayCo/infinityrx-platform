"""Medical-claims event publishers, consumers, and startup wiring.

wire_consumers() wires edi.837_received and claim.adjudicated consumers to
the shared EventBus. All DB writes use a per-delivery session via
session_factory so each event is committed independently — no long-lived
session held across events (CR-01 v2 BLOCK-2 fix).

Call this from the lifespan coroutine after bus.start(). The lifespan in
main.py passes the module's own sync session factory so services receive a
fresh, committed session per event.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
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


def reset_idempotency_store() -> None:
    """Replace the module-level store with a fresh instance. Tests use this."""
    global _idempotency_store
    _idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable | None = None,
    idempotency_store: Any | None = None,
) -> None:
    """Subscribe all medical-claims consumers at application startup.

    CR-01 v2 BLOCK-2 fix: services are now created per event delivery using
    session_factory, not once at startup with a long-lived session.

    Args:
        bus: The event bus to subscribe to.
        session_factory: Zero-argument callable returning a context manager
            that yields a sync Session. Commits on success, rolls back on
            exception. Production uses src.db.session.get_db_session.
            Tests inject their own SAVEPOINT session factory.
        idempotency_store: Optional override for the module-level store.
            Tests pass a fresh InMemoryIdempotencyStore() per test.
    """
    from .consumers import handle_edi_837_received, handle_pharmacy_claim_adjudicated
    from src.services.claim_service import ClaimService
    from src.services.unified_spend_service import UnifiedDrugSpendService

    if session_factory is None:
        from src.db.session import get_db_session  # noqa: PLC0415
        session_factory = get_db_session

    store = idempotency_store if idempotency_store is not None else _idempotency_store

    async def _handle_edi_837_received(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="medical_claims.edi_837_received"):
            return
        with session_factory() as session:
            svc = ClaimService(db=session)
            await handle_edi_837_received(envelope, claim_service=svc, db=session)
        await store.mark(key, consumer_name="medical_claims.edi_837_received")

    async def _handle_pharmacy_claim_adjudicated(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="medical_claims.claim_adjudicated"):
            return
        with session_factory() as session:
            svc = UnifiedDrugSpendService(db=session)
            await handle_pharmacy_claim_adjudicated(envelope, unified_spend_service=svc)
        await store.mark(key, consumer_name="medical_claims.claim_adjudicated")

    await bus.subscribe("edi.837_received", _handle_edi_837_received)
    await bus.subscribe("claim.adjudicated", _handle_pharmacy_claim_adjudicated)
    logger.info(
        "medical-claims.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
