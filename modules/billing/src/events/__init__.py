"""Billing event publishers, consumers, and startup wiring.

wire_consumers() is called from the module lifespan to activate all
consumer subscriptions on the shared EventBus.

Each subscription wrapper:
  1. Short-circuits on duplicate deliveries via the idempotency store.
  2. Opens a SQLAlchemy session from ``src.db.session.get_db_session``
     for this delivery, so handlers can persist records. The context
     manager handles commit on clean exit and rollback on exception.
  3. Dispatches through the consumers module at call time so tests that
     patch ``modules.billing.src.events.consumers.*`` still observe the
     wrapped handler.

A ``session_factory`` override is accepted so tests can inject their own
sessionmaker (see tests/integration/test_consumer_app_wired.py).
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import InMemoryIdempotencyStore
from shared.events.types import EventEnvelope

logger = logging.getLogger("billing.events")

# Shared idempotency store (replaced with PostgresIdempotencyStore at startup)
_idempotency_store = InMemoryIdempotencyStore()


@contextmanager
def _default_session_cm() -> Iterator[Any]:
    """Default session provider — deferred import so test code that never
    sets BILLING_DATABASE_URL doesn't blow up at module import time.
    """
    from ..db.session import get_db_session  # noqa: PLC0415

    with get_db_session() as session:
        yield session


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Subscribe all billing consumers at application startup.

    Each handler is wrapped with idempotency checks per event-bus rules
    and receives a fresh DB session per delivery.

    Handlers are dispatched through the consumers module at call time so that
    test patches applied to ``modules.billing.src.events.consumers.*`` are
    respected even after wiring (LESSON-006: test the wire, not the component).
    """
    import modules.billing.src.events.consumers as _consumers

    store = _idempotency_store
    session_cm = session_factory if session_factory is not None else _default_session_cm

    def _make_wrapper(handler_attr: str, consumer_name: str):
        async def _async_handler(envelope: EventEnvelope) -> None:
            key = envelope.idempotency_key
            if await store.seen(key, consumer_name=consumer_name):
                return
            handler = getattr(_consumers, handler_attr)
            with session_cm() as session:
                await handler(envelope, db=session, bus=bus)
            await store.mark(key, consumer_name=consumer_name)

        _async_handler.__name__ = f"billing_{consumer_name}"
        return _async_handler

    await bus.subscribe(
        "claim.adjudicated",
        _make_wrapper("handle_claim_adjudicated", "billing.claim_adjudicated"),
    )
    await bus.subscribe(
        "claim.reversed",
        _make_wrapper("handle_claim_reversed", "billing.claim_reversed"),
    )
    await bus.subscribe(
        "payment.auto_posted",
        _make_wrapper("handle_payment_auto_posted", "billing.payment_auto_posted"),
    )
    await bus.subscribe(
        "member.enrolled",
        _make_wrapper("handle_member_enrolled", "billing.member_enrolled"),
    )
    logger.info(
        "billing.consumers_wired",
        extra={
            "svc_topics": "claim.adjudicated,claim.reversed,payment.auto_posted,member.enrolled"
        },
    )
