"""InfinityRx event bus abstraction."""

from shared.events import event_types
from shared.events.bus import EventBus
from shared.events.context import (
    current_correlation_id,
    new_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from shared.events.factory import get_event_bus, reset_event_bus, set_event_bus
from shared.events.in_memory_bus import InMemoryEventBus
from shared.events.rabbitmq_bus import RabbitMQEventBus
from shared.events.types import EventEnvelope

__all__ = [
    "EventBus",
    "EventEnvelope",
    "InMemoryEventBus",
    "RabbitMQEventBus",
    "current_correlation_id",
    "event_types",
    "get_event_bus",
    "new_correlation_id",
    "reset_correlation_id",
    "reset_event_bus",
    "set_correlation_id",
    "set_event_bus",
]
