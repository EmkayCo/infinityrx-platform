"""Tests for rate limiter middleware — token bucket behavior."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from src.middleware.rate_limiter import (
    InMemoryBucketStore,
    RateLimitConfig,
    TokenBucket,
)


class TestTokenBucket:
    def test_bucket_starts_full(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        assert bucket.tokens == 10.0

    def test_consume_returns_true_when_tokens_available(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=1.0)
        allowed, remaining, reset = bucket.consume()
        assert allowed is True
        assert remaining < 10.0

    def test_consume_returns_false_when_bucket_empty(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.01)
        bucket.tokens = 0.0
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert remaining == 0.0
        assert reset > 0

    def test_consume_with_zero_refill_rate_returns_wait_60(self):
        bucket = TokenBucket(capacity=1.0, refill_rate=0.0)
        bucket.tokens = 0.0
        allowed, remaining, reset = bucket.consume()
        assert allowed is False
        assert reset == 60

    def test_seconds_to_full_zero_refill_rate(self):
        bucket = TokenBucket(capacity=10.0, refill_rate=0.0)
        allowed, remaining, reset = bucket.consume()
        assert allowed is True
        assert reset == 0


class TestInMemoryBucketStore:
    def test_creates_bucket_on_first_access(self):
        store = InMemoryBucketStore()
        bucket = store.get_or_create("key1", 10.0, 1.0)
        assert bucket is not None

    def test_returns_same_bucket_on_second_access(self):
        store = InMemoryBucketStore()
        b1 = store.get_or_create("key1", 10.0, 1.0)
        b2 = store.get_or_create("key1", 10.0, 1.0)
        assert b1 is b2


class TestRateLimitMiddlewareUnit:
    def test_config_defaults(self):
        config = RateLimitConfig()
        assert config.tenant_rpm == 1000
        assert config.burst_multiplier == 1.5
