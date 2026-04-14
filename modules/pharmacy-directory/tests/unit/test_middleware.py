"""Unit tests for pharmacy-directory middleware.

Covers _Bucket token refill, rate limit exceeded path, and
request-with-no-client fallback.
"""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.middleware import RateLimitMiddleware, _Bucket


class TestBucket:
    def test_consume_returns_true_when_tokens_available(self) -> None:
        bucket = _Bucket(10)
        assert bucket.consume(10) is True

    def test_consume_decrements_tokens(self) -> None:
        bucket = _Bucket(5)
        bucket.consume(5)
        assert bucket.tokens == 4

    def test_consume_returns_false_when_no_tokens(self) -> None:
        bucket = _Bucket(1)
        bucket.consume(1)
        assert bucket.consume(1) is False

    def test_consume_refills_tokens_after_elapsed_time(self) -> None:
        bucket = _Bucket(10)
        # Drain all tokens
        for _ in range(10):
            bucket.consume(10)
        # Simulate 60 seconds elapsed
        bucket.last_refill = time.monotonic() - 60.0
        result = bucket.consume(10)
        assert result is True

    def test_consume_caps_refill_at_capacity(self) -> None:
        bucket = _Bucket(5)
        # Simulate way more than 60 seconds elapsed
        bucket.last_refill = time.monotonic() - 9999.0
        bucket.tokens = 0
        bucket.consume(5)
        # After refill, tokens should be capped at capacity - 1 (just consumed)
        assert bucket.tokens <= 4

    def test_refill_updates_last_refill_timestamp(self) -> None:
        bucket = _Bucket(10)
        bucket.last_refill = time.monotonic() - 65.0
        old_refill = bucket.last_refill
        bucket.consume(10)
        assert bucket.last_refill > old_refill


class TestRateLimitMiddlewareUnit:
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self) -> None:
        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, limit=1)

        # Create a mock request
        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"

        mock_next = AsyncMock()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_next.return_value = mock_response

        # First request should succeed
        await middleware.dispatch(mock_request, mock_next)

        # Second request from same IP should be rate limited
        bucket = middleware._buckets["127.0.0.1"]
        bucket.tokens = 0  # Force exhaustion

        response = await middleware.dispatch(mock_request, mock_next)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_no_client_uses_unknown_key(self) -> None:
        mock_app = AsyncMock()
        middleware = RateLimitMiddleware(mock_app, limit=200)

        mock_request = MagicMock()
        mock_request.client = None  # No client info

        mock_next = AsyncMock()
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_next.return_value = mock_response

        await middleware.dispatch(mock_request, mock_next)
        assert "unknown" in middleware._buckets
