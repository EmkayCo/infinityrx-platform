"""Shim event bus for payment-processing — in-process publish with recording for tests."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PublishedEvent:
    topic: str
    payload: dict[str, Any]


_published: list[PublishedEvent] = []


def publish(topic: str, payload: dict[str, Any]) -> None:
    _published.append(PublishedEvent(topic=topic, payload=dict(payload)))


def published_events() -> list[PublishedEvent]:
    return list(_published)


def reset_events() -> None:
    _published.clear()
