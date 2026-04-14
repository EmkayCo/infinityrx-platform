"""Shim event bus for reclaimrx — thin re-export of shared event primitives.

This shim maintains the synchronous publish(topic, payload) API used by
reclaimrx services (accumulator_service, payment_hold_service) until those
services are converted to async (CR-05 work by Teammate 3).

The canonical event bus is shared.events.bus.EventBus (async).  When the
module is converted to async, replace calls to this shim's publish() with
await bus.publish(EventEnvelope(...)) directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PublishedEvent:
    topic: str
    payload: dict[str, Any]


_published: list[PublishedEvent] = []


def publish(topic: str, payload: dict[str, Any]) -> None:
    """Record a published event.  In production the reclaimrx lifespan will
    replace this with a real bus call once async conversion is complete."""
    _published.append(PublishedEvent(topic=topic, payload=dict(payload)))


def published_events() -> list[PublishedEvent]:
    return list(_published)


def reset_events() -> None:
    _published.clear()
