"""Retry logic with exponential backoff for failed submissions.

Backoff schedule: 1h, 4h, 12h (configurable via constants).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..utils.constants import RETRY_BACKOFF_HOURS


def next_retry_at(retry_count: int, backoff_hours: list[int] | None = None) -> datetime | None:
    """Return the datetime for the next retry attempt, or None if exhausted."""
    schedule = backoff_hours or RETRY_BACKOFF_HOURS
    if retry_count >= len(schedule):
        return None
    delay_hours = schedule[retry_count]
    return datetime.now(UTC) + timedelta(hours=delay_hours)


def should_retry(retry_count: int, max_retries: int) -> bool:
    return retry_count < max_retries
