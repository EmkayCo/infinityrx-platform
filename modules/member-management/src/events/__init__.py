"""Member Management event consumers and startup wiring.

wire_consumers() subscribes claim.adjudicated and claim.reversed consumers
to the shared EventBus. All DB writes use a per-delivery session via
session_factory so each event is committed independently.

CR-01 v2 BLOCK-4 fix: v1's session context only close()d — accumulator
writes were lost on process restart. v2 passes session_factory that commits
on success and rolls back on exception.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("member-management.events")

_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable | None = None,
    idempotency_store: Any | None = None,
) -> None:
    """Subscribe all member-management consumers at application startup.

    Args:
        bus: The event bus to subscribe to.
        session_factory: Zero-argument callable returning a context manager
            that yields a sync Session. Commits on success, rolls back on
            exception. Production uses src.db.session.get_db_session.
            Tests inject their own SAVEPOINT session factory.
        idempotency_store: Optional override for tests — use a fresh store per test.
    """
    from .consumers import ClaimAdjudicatedConsumer, ClaimReversedConsumer  # noqa: PLC0415

    if session_factory is None:
        from src.db.session import get_db_session  # noqa: PLC0415
        session_factory = get_db_session

    store = idempotency_store if idempotency_store is not None else _idempotency_store

    async def _handle_claim_adjudicated(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="member_mgmt.claim_adjudicated"):
            return
        # CR-01 v2 BLOCK-4: per-delivery session — commits on success, rolls back on error
        with session_factory() as session:
            consumer = ClaimAdjudicatedConsumer(db=session, idempotency_store=store)
            await consumer.handle(key, envelope.payload)
        await store.mark(key, consumer_name="member_mgmt.claim_adjudicated")

    async def _handle_claim_reversed(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="member_mgmt.claim_reversed"):
            return
        with session_factory() as session:
            consumer = ClaimReversedConsumer(db=session, idempotency_store=store)
            await consumer.handle(key, envelope.payload)
        await store.mark(key, consumer_name="member_mgmt.claim_reversed")

    await bus.subscribe("claim.adjudicated", _handle_claim_adjudicated)
    await bus.subscribe("claim.reversed", _handle_claim_reversed)
    logger.info(
        "member-management.consumers_wired",
        extra={"svc_topics": "claim.adjudicated,claim.reversed"},
    )
