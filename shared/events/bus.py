"""Abstract event bus protocol.

All concrete implementations (in-memory, RabbitMQ, Azure Service Bus)
conform to this interface so modules never couple to a broker.
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
