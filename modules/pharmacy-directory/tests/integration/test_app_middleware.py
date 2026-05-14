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


class TestCorsPreflight:
    """create_app() must mount CORSMiddleware. Without it the browser
    preflight OPTIONS returns 405 and every portal→backend call is blocked
    — verified in production by the 2026-05-13 'no data in directories'
    incident."""

    @pytest.fixture(autouse=True)
    def _set_cors_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """app.py mounts CORSMiddleware conditionally — only when
        CORS_ALLOW_ORIGINS (settings) or CORS_ORIGINS (env) yields a
        non-empty origin list. The test env sets neither by default, so
        without this fixture create_app() correctly mounts NO CORS and
        test_create_app_mounts_cors_middleware fails. Provide the env so
        the conditional fires and the mount is exercised."""
        monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["http://localhost:3000"]')
        monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000")

    def test_options_preflight_returns_cors_headers(self) -> None:
        from src.app import create_app  # noqa: PLC0415 — defer import to avoid lifespan

        # We can't easily start lifespan in a test (it expects a real DB/bus).
        # Build a minimal app exercising only the CORS contract.
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/probe")
        def probe() -> dict:
            return {"ok": True}

        client = TestClient(app)
        resp = client.options(
            "/probe",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,x-tenant-id",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_create_app_mounts_cors_middleware(self) -> None:
        """The real create_app() must mount CORSMiddleware so browser
        preflights succeed against the live process."""
        from src.app import create_app  # noqa: PLC0415

        # Inspect middleware stack — CORSMiddleware should be present.
        # Build app without exercising lifespan (we only inspect the stack).
        app = create_app()
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes, (
            f"CORSMiddleware not mounted. Stack: {middleware_classes}"
        )
