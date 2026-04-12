"""Event bus factory / singleton.

In tests (or any process without RABBITMQ_URL set) we default to the
in-memory bus so suites run hermetically. Production sets
``EVENT_BUS_BACKEND=rabbitmq`` to wire the aio-pika implementation.
"""

from __future__ import annotations

import os

from shared.events.bus import EventBus
from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.rabbitmq_bus import RabbitMQEventBus

_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    global _bus
    if _bus is not None:
        return _bus
    backend = os.getenv("EVENT_BUS_BACKEND", "memory").lower()
    if backend == "rabbitmq":  # pragma: no cover - exercised only in integration
        url = os.getenv("RABBITMQ_URL", "amqp://infinityrx:infinityrx_dev@localhost:5672/")
        _bus = RabbitMQEventBus(url)
    else:
        _bus = InMemoryEventBus()
    return _bus


def set_event_bus(bus: EventBus) -> None:
    """Override the process-wide bus (tests only)."""
    global _bus
    _bus = bus


def reset_event_bus() -> None:
    global _bus
    _bus = None
