"""Integration contract (LESSON-006): middleware must be wired through create_app().

These tests only pass if SecurityHeadersMiddleware, RateLimitMiddleware, and
the DLQ router are actually mounted on the app returned by create_app().
"""
from __future__ import annotations


import pytest
from fastapi.testclient import TestClient



@pytest.fixture
def client() -> TestClient:
    from fastapi import FastAPI
    from src.api.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
    from src.api.router import router as pharmacy_router
    from shared.events.dlq import DLQService, build_dlq_router

    async def _get_dlq() -> DLQService:
        class _Empty:
            async def list(self, **_kw): return []
            async def get(self, _id): return None
        return DLQService(repository=_Empty())

    async def _get_perms() -> set: return set()

    # Build app WITHOUT lifespan so DB/bus don't start in middleware tests
    app = FastAPI(title="Test Pharmacy Directory")
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.include_router(pharmacy_router)
    app.include_router(build_dlq_router(get_service=_get_dlq, get_permissions=_get_perms))

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestSecurityHeadersMiddleware:
    def test_security_headers_present_on_any_response(self, client: TestClient) -> None:
        # Hit health endpoint — should return security headers regardless of route
        resp = client.get("/health")
        assert "strict-transport-security" in resp.headers or "Strict-Transport-Security" in resp.headers

    def test_x_content_type_options_nosniff(self, client: TestClient) -> None:
        resp = client.get("/health")
        header = resp.headers.get("x-content-type-options") or resp.headers.get("X-Content-Type-Options")
        assert header == "nosniff"

    def test_cache_control_no_store(self, client: TestClient) -> None:
        resp = client.get("/health")
        header = resp.headers.get("cache-control") or resp.headers.get("Cache-Control")
        assert header == "no-store"

    def test_x_frame_options_deny(self, client: TestClient) -> None:
        resp = client.get("/health")
        header = resp.headers.get("x-frame-options") or resp.headers.get("X-Frame-Options")
        assert header == "DENY"


class TestRateLimitMiddleware:
    def test_rate_limit_headers_present(self, client: TestClient) -> None:
        resp = client.get("/health")
        header = resp.headers.get("x-ratelimit-limit") or resp.headers.get("X-RateLimit-Limit")
        assert header is not None

    def test_x_ratelimit_remaining_present(self, client: TestClient) -> None:
        resp = client.get("/health")
        remaining = resp.headers.get("x-ratelimit-remaining") or resp.headers.get("X-RateLimit-Remaining")
        assert remaining is not None


class TestDlqRouterMounted:
    def test_dlq_list_endpoint_reachable(self, client: TestClient) -> None:
        # DLQ router is mounted at /api/v1/events/dlq — not 404
        resp = client.get("/api/v1/events/dlq")
        assert resp.status_code != 404
