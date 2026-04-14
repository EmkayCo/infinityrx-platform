"""Tests for token bucket rate limiter."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.infrastructure.rate_limiter import (
    InMemoryBucketStore,
    RateLimitConfig,
    RateLimitMiddleware,
    TokenBucket,
)


# ---------------------------------------------------------------------------
# TokenBucket unit tests
# ---------------------------------------------------------------------------


def test_bucket_starts_full():
    b = TokenBucket(capacity=10, refill_rate=1.0)
    allowed, remaining, _ = b.consume(1)
    assert allowed is True
    assert remaining == 9.0


def test_bucket_exhaustion():
    b = TokenBucket(capacity=2, refill_rate=0.0)  # no refill
    assert b.consume(1)[0] is True
    assert b.consume(1)[0] is True
    allowed, remaining, _ = b.consume(1)
    assert allowed is False
    assert remaining == 0.0


def test_bucket_refill():
    b = TokenBucket(capacity=10, refill_rate=1000.0)  # fast refill for test
    b.consume(10)  # drain
    import time
    time.sleep(0.02)  # allow refill
    allowed, _, _ = b.consume(1)
    assert allowed is True


def test_bucket_consume_zero_does_not_reduce():
    b = TokenBucket(capacity=5, refill_rate=0.0)
    b.consume(0)
    _, remaining, _ = b.consume(0)
    assert remaining == 5.0


# ---------------------------------------------------------------------------
# InMemoryBucketStore
# ---------------------------------------------------------------------------


def test_store_get_or_create():
    store = InMemoryBucketStore()
    b1 = store.get_or_create("k1", 10, 1.0)
    b2 = store.get_or_create("k1", 10, 1.0)
    assert b1 is b2  # same instance


def test_store_clear():
    store = InMemoryBucketStore()
    store.get_or_create("k1", 10, 1.0)
    store.clear()
    b = store.get_or_create("k1", 10, 1.0)
    # Should be a fresh bucket (full capacity)
    assert b.tokens == 10.0


# ---------------------------------------------------------------------------
# Middleware integration
# ---------------------------------------------------------------------------


def _make_app(config: RateLimitConfig | None = None) -> FastAPI:
    app = FastAPI()
    store = InMemoryBucketStore()
    app.add_middleware(RateLimitMiddleware, config=config, store=store)

    @app.get("/test")
    async def _test(request: Request):
        return {"ok": True}

    @app.get("/health")
    async def _health():
        return {"status": "ok"}

    return app


def test_middleware_adds_rate_limit_headers():
    """Requests without tenant/user state skip rate limiting but succeed."""
    app = _make_app()
    client = TestClient(app)
    resp = client.get("/test")
    assert resp.status_code == 200


def test_middleware_skips_health():
    app = _make_app()
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-RateLimit-Limit" not in resp.headers


def test_middleware_returns_429_when_exhausted():
    """With a very low limit, should 429 quickly."""
    config = RateLimitConfig(tenant_rpm=2, user_rpm=2, burst_multiplier=1.0)
    app = FastAPI()
    store = InMemoryBucketStore()
    app.add_middleware(RateLimitMiddleware, config=config, store=store)

    @app.middleware("http")
    async def _inject_tenant(request: Request, call_next):
        request.state.tenant_id = "t1"
        request.state.user_id = "u1"
        return await call_next(request)

    @app.get("/test")
    async def _test():
        return {"ok": True}

    client = TestClient(app)
    # First 2 should succeed (capacity = 2 * 1.0 = 2)
    assert client.get("/test").status_code == 200
    assert client.get("/test").status_code == 200
    # Third should be rate limited
    resp = client.get("/test")
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.json()["detail"].startswith("Rate limit exceeded")
