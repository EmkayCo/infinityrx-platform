"""ReclaimRx event publishers, consumers, and startup wiring.

wire_consumers() subscribes all CONSUMER_ROUTING handlers to the shared EventBus.
Each subscription wrapper:
  1. Short-circuits on duplicate deliveries via the idempotency store.
  2. Opens a SQLAlchemy Session for this delivery (via session_factory)
     so handlers can run the real FWA detection pipeline. Context manager
     handles commit on clean exit, rollback on exception.
  3. Dispatches the handler with the full EventEnvelope + db session.

Tests can override session_factory to inject a no-op MagicMock session
when they only care about routing/idempotency semantics.

A2 §6c: InMemoryIdempotencyStore replaced with PostgresIdempotencyStore
(R1 BLOCK 6 fix). The durable store survives worker restarts; the in-memory
stub was a correctness gap — duplicate deliveries across restarts would be
processed twice.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from shared.events.bus import EventBus
from shared.events.idempotency import (
    PostgresIdempotencyStore,
    idempotent_handler,
)
from shared.events.types import EventEnvelope

from .consumers import CONSUMER_ROUTING

logger = logging.getLogger("reclaimrx.events")

# Module-level singleton -- built once from the async engine at startup.
# Consumer wiring imports this via get_idempotency_store().
# R9 BLOCK-27: NOT imported at module scope to allow tests to monkeypatch
# get_async_engine_for_idempotency before the store is constructed.
_idempotency_store: PostgresIdempotencyStore | None = None


def get_idempotency_store() -> PostgresIdempotencyStore:
    """Lazy accessor -- wire_consumers() calls this once at startup.

    R9 BLOCK-27 fix: the engine factory import lives INSIDE this function,
    not at module scope. A module-scope import of get_async_engine_for_idempotency
    would bind the factory at first import of src.events, defeating any later
    monkeypatch.setattr on src._shim.db.get_async_engine_for_idempotency. Importing
    per-call lets tests stub the factory before get_idempotency_store() is invoked.
    """
    global _idempotency_store
    if _idempotency_store is None:
        from src._shim.db import get_async_engine_for_idempotency  # noqa: PLC0415
        engine = get_async_engine_for_idempotency()
        _idempotency_store = PostgresIdempotencyStore(engine=engine)
    return _idempotency_store


@contextmanager
def _default_session_cm() -> Iterator[Any]:
    """Default session provider -- deferred import so tests that never set
    RECLAIMRX_DATABASE_URL do not blow up at module import time.
    """
    from src._shim.db import get_sessionmaker  # noqa: PLC0415

    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def wire_consumers(
    bus: EventBus,
    *,
    session_factory: Callable[[], Any] | None = None,
) -> None:
    """Subscribe every CONSUMER_ROUTING handler to the bus with:
      * idempotency wrapper (duplicate envelopes short-circuit)
      * per-delivery DB session (injected as db= into the handler)
    """
    store = get_idempotency_store()
    session_cm = session_factory if session_factory is not None else _default_session_cm

    import modules.reclaimrx.src.events.consumers as _consumers

    for topic in list(CONSUMER_ROUTING.keys()):
        consumer_name = f"reclaimrx.{topic.replace('.', '_')}"

        def _make_async_wrapper(topic_name: str, cname: str):  # noqa: ANN001
            async def _async_handler(envelope: EventEnvelope) -> None:
                key = envelope.idempotency_key
                if await store.seen(key, consumer_name=cname):
                    return
                # Always resolve the handler at call time so tests that patch
                # CONSUMER_ROUTING or the individual consumer module observe
                # the replacement.
                handler = _consumers.CONSUMER_ROUTING[topic_name]
                with session_cm() as session:
                    await handler(envelope, db=session, bus=bus)
                await store.mark(key, consumer_name=cname)

            _async_handler.__name__ = f"reclaimrx_{cname}"
            return _async_handler

        await bus.subscribe(topic, _make_async_wrapper(topic, consumer_name))

    logger.info(
        "reclaimrx.consumers_wired",
        extra={"svc_topics": ",".join(CONSUMER_ROUTING.keys())},
    )
