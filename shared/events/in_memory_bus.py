"""In-memory event bus for tests and single-process dev.

Supports topic pattern matching via fnmatch, records every published
envelope for assertion, and propagates correlation ids automatically
when a publisher has one set on the context.
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging

from shared.events.bus import EventBus, EventHandler
from shared.events.context import current_correlation_id
from shared.events.types import EventEnvelope

_logger = logging.getLogger(__name__)


class InMemoryEventBus(EventBus):
    """Fan-out bus that dispatches envelopes to matching subscribers in-process."""

    def __init__(self) -> None:
        self._subs: list[tuple[str, EventHandler]] = []
        self._published: list[EventEnvelope] = []
        self._started = False
        self._handler_errors: list[BaseException] = []

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def publish(self, envelope: EventEnvelope) -> None:
        # Honour an ambient correlation id if the envelope was built without one
        ctx_cid = current_correlation_id()
        if ctx_cid is not None and envelope.correlation_id != ctx_cid:
            envelope = envelope.model_copy(update={"correlation_id": ctx_cid})
        self._published.append(envelope)
        for pattern, handler in list(self._subs):
            if fnmatch.fnmatchcase(envelope.event_type, pattern):
                try:
                    await handler(envelope)
                except Exception as exc:
                    self._handler_errors.append(exc)
                    _logger.error(
                        "in_memory_bus.handler_error",
                        extra={"pattern": pattern, "event_type": envelope.event_type},
                    )

    async def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        self._subs.append((topic_pattern, handler))

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------
    @property
    def published(self) -> list[EventEnvelope]:
        return list(self._published)

    @property
    def handler_errors(self) -> list[BaseException]:
        return list(self._handler_errors)

    def reset(self) -> None:
        self._subs.clear()
        self._published.clear()
        self._handler_errors.clear()

    async def drain(self) -> None:
        """No-op for the in-memory bus (publish is synchronous)."""
        await asyncio.sleep(0)
