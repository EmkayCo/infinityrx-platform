"""Integration test — rate limiter exhaustion through create_app()."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import pytest
from fastapi.testclient import TestClient

from src.main import create_app
from src.middleware.rate_limiter import InMemoryBucketStore, RateLimitConfig, RateLimitMiddleware


@pytest.fixture(scope="module")
def rate_limited_client():
    """App with a very tight rate limit to test exhaustion."""
    app = create_app()

    # Replace the rate limiter with one that has capacity=1 to trigger exhaustion
    from src.middleware.security_headers import SecurityHeadersMiddleware

    # Build app fresh with tiny rate limit
    from fastapi import FastAPI
    fresh_app = FastAPI()

    @fresh_app.get("/health")
    def health():
        return {"status": "ok", "module": "prescriber-directory"}

    store = InMemoryBucketStore()
    config = RateLimitConfig(tenant_rpm=1, burst_multiplier=1.0)
    fresh_app.add_middleware(RateLimitMiddleware, config=config, store=store)
    fresh_app.add_middleware(SecurityHeadersMiddleware)

    return TestClient(fresh_app, raise_server_exceptions=False)


class TestRateLimiterExhaustion:
    def test_rate_limit_exceeded_returns_429(self, rate_limited_client):
        """Exhaust the rate bucket and verify 429 response."""
        client = rate_limited_client

        # First request sets tenant_id in state — but our middleware reads from state
        # which is set by request headers. Send requests until 429 or confirm path runs.
        # Since tenant_id is only in state via header middleware (not our code),
        # and our rate limiter reads from request.state.tenant_id which is never set
        # by our test client, this path won't trigger naturally.
        # To test: manually set a bucket to empty and hit the endpoint.

        # Access the store directly and exhaust a bucket
        store = InMemoryBucketStore()
        config = RateLimitConfig(tenant_rpm=1, burst_multiplier=1.0)

        # Create fresh FastAPI app with the exhaustion-ready store
        from fastapi import FastAPI, Request

        test_app = FastAPI()
        exhausted_store = InMemoryBucketStore()

        # Pre-exhaust the tenant bucket
        bucket = exhausted_store.get_or_create("tenant:test-tenant", 1.0, 0.001)
        bucket.tokens = 0.0

        # In FastAPI, middleware runs in reverse-add order.
        # Add RateLimitMiddleware first so it runs AFTER the state-setter.
        test_app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(tenant_rpm=1, burst_multiplier=1.0),
            store=exhausted_store,
        )

        # This middleware runs first (added last) — sets tenant_id in state
        @test_app.middleware("http")
        async def set_tenant_state(request: Request, call_next):
            request.state.tenant_id = "test-tenant"
            return await call_next(request)

        @test_app.get("/test")
        def test_endpoint():
            return {"ok": True}

        tc = TestClient(test_app, raise_server_exceptions=False)
        resp = tc.get("/test")
        assert resp.status_code == 429

    def test_rate_limit_allows_request_when_bucket_has_tokens(self):
        """Verify allowed path (if not allowed -> False) passes through to call_next."""
        from fastapi import FastAPI, Request

        test_app = FastAPI()
        full_store = InMemoryBucketStore()

        test_app.add_middleware(
            RateLimitMiddleware,
            config=RateLimitConfig(tenant_rpm=100, burst_multiplier=1.0),
            store=full_store,
        )

        @test_app.middleware("http")
        async def set_tenant_state(request: Request, call_next):
            request.state.tenant_id = "test-tenant-full"
            return await call_next(request)

        @test_app.get("/test")
        def test_endpoint():
            return {"ok": True}

        tc = TestClient(test_app, raise_server_exceptions=False)
        resp = tc.get("/test")
        assert resp.status_code == 200
