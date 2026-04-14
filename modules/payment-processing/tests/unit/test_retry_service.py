"""Unit tests for retry service."""
from __future__ import annotations

from datetime import datetime, timezone


from src.services.retry_service import next_retry_at, should_retry


class TestShouldRetry:
    def test_can_retry_when_under_max(self):
        assert should_retry(0, 3) is True
        assert should_retry(1, 3) is True
        assert should_retry(2, 3) is True

    def test_cannot_retry_at_max(self):
        assert should_retry(3, 3) is False

    def test_cannot_retry_above_max(self):
        assert should_retry(5, 3) is False


class TestNextRetryAt:
    def test_first_retry_is_one_hour(self):
        result = next_retry_at(0)
        now = datetime.now(timezone.utc)
        diff = result - now
        assert 3599 < diff.total_seconds() < 3601  # ~1 hour

    def test_second_retry_is_four_hours(self):
        result = next_retry_at(1)
        now = datetime.now(timezone.utc)
        diff = result - now
        assert 14399 < diff.total_seconds() < 14401  # ~4 hours

    def test_third_retry_is_twelve_hours(self):
        result = next_retry_at(2)
        now = datetime.now(timezone.utc)
        diff = result - now
        assert 43199 < diff.total_seconds() < 43201  # ~12 hours

    def test_exhausted_returns_none(self):
        result = next_retry_at(3)  # beyond default schedule length
        assert result is None

    def test_custom_schedule(self):
        result = next_retry_at(0, backoff_hours=[2, 8])
        now = datetime.now(timezone.utc)
        diff = result - now
        assert 7199 < diff.total_seconds() < 7201  # ~2 hours

    def test_custom_schedule_exhausted(self):
        result = next_retry_at(2, backoff_hours=[2, 8])
        assert result is None
