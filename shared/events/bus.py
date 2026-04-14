"""Abstract event bus protocol.

All concrete implementations (in-memory, RabbitMQ, Azure Service Bus)
conform to this interface so modules never couple to a broker.

Publishing modes
----------------
1. Direct publish (``bus.publish(envelope)``):
   Publishes immediately. Simple but NOT crash-safe — if the process dies
   between the DB commit and the publish() call, the event is lost.
   Use only for non-financial, non-critical notifications.

2. Transactional outbox (``enqueue_event(session, envelope)`` + OutboxRelay):
   Writes the event to the ``shared_events.outbox_entries`` table IN THE SAME
   transaction as the business data. The OutboxRelay polls and publishes to
   the bus with retries. Crash-safe: if the process dies, the relay picks up
   on restart. MUST be used for ALL financial events (payment_batch.submitted,
   claim.ingested, etc.).

   See ``shared.events.outbox`` for the OutboxEntry model and OutboxRelay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from shared.events.types import EventEnvelope

EventHandler = Callable[[EventEnvelope], Awaitable[None]]


class EventBus(ABC):
    """Base class for event bus implementations."""

    @abstractmethod
    async def publish(self, envelope: EventEnvelope) -> None:  # pragma: no cover - abstract
        """Publish an envelope. Correlation id is already on the envelope."""

    @abstractmethod
    async def subscribe(
        self, topic_pattern: str, handler: EventHandler
    ) -> None:  # pragma: no cover - abstract
        """Subscribe a handler to a topic pattern (supports ``module.*`` wildcards)."""

    @abstractmethod
    async def start(self) -> None:  # pragma: no cover - abstract
        """Open underlying resources (connections, consumers)."""

    @abstractmethod
    async def stop(self) -> None:  # pragma: no cover - abstract
        """Release underlying resources."""
