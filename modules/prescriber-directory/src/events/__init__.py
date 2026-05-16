"""Prescriber Directory event consumers and startup wiring.

wire_consumers() subscribes claim.ingested and exclusion.match_found consumers
to the shared EventBus. All DB queries are filtered by EventEnvelope.tenant_id.

CR-01 v2 HIPAA fix: v1 did not filter DB queries by tenant_id, causing
PrescriberPharmacyRelationship rows to be shared across tenants.
v2 passes tenant_id from each event envelope to the consumer handlers,
and PrescriberPharmacyRelationship now has a tenant_id column.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("prescriber-directory.events")

_idempotency_store = InMemoryIdempotencyStore()


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable | None = None,
    idempotency_store: Any | None = None,
) -> None:
    """Subscribe all prescriber-directory consumers at application startup.

    Args:
        bus: The event bus to subscribe to.
        session_factory: A zero-argument callable returning a context manager
            that yields a DB Session. Production uses src.db.session.get_db_session.
            Tests inject their own SAVEPOINT session factory.
        idempotency_store: Optional override for tests — use a fresh store per test.

    CR-01 v2 HIPAA BLOCK fix: EventEnvelope.tenant_id is extracted and passed
    to each handler so DB queries are scoped to the publishing tenant.
    """
    from .consumer import handle_claim_ingested, handle_exclusion_match_found  # noqa: PLC0415

    if session_factory is None:
        from src.db.session import get_db_session  # noqa: PLC0415
        session_factory = get_db_session

    store = idempotency_store if idempotency_store is not None else _idempotency_store

    async def _handle_claim_ingested(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="prescriber_dir.claim_ingested"):
            return
        # CR-01 v2 HIPAA: pass tenant_id to handler for DB query filtering
        with session_factory() as session:
            await handle_claim_ingested(
                envelope.payload,
                db=session,
                tenant_id=envelope.tenant_id,
            )
        await store.mark(key, consumer_name="prescriber_dir.claim_ingested")

    async def _handle_exclusion_match_found(envelope: EventEnvelope) -> None:
        key = envelope.idempotency_key
        if await store.seen(key, consumer_name="prescriber_dir.exclusion_match_found"):
            return
        # Exclusions are global reference data — tenant_id not required for Prescriber
        with session_factory() as session:
            await handle_exclusion_match_found(envelope.payload, db=session)
        await store.mark(key, consumer_name="prescriber_dir.exclusion_match_found")

    await bus.subscribe("claim.ingested", _handle_claim_ingested)
    await bus.subscribe("exclusion.match_found", _handle_exclusion_match_found)
    logger.info(
        "prescriber-directory.consumers_wired",
        extra={"svc_topics": "claim.ingested,exclusion.match_found"},
    )
