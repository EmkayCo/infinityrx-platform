"""Shim event bus: in-process publish with recording for tests.

Real implementation lives in shared/events/ (T3).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class PublishedEvent:
    topic: str
    payload: Dict[str, Any]


_published: List[PublishedEvent] = []


def publish(topic: str, payload: Dict[str, Any]) -> None:
    _published.append(PublishedEvent(topic=topic, payload=dict(payload)))


def published_events() -> List[PublishedEvent]:
    return list(_published)


def reset_events() -> None:
    _published.clear()
