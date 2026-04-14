"""Tests that security middleware and DLQ router are mounted on the app.

P1 Item 5 of the emergency wiring pass: ``SecurityHeadersMiddleware`` and
``RateLimitMiddleware`` were written and tested in isolation but never
mounted on the production FastAPI app, and the DLQ router was unreachable.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src import main as main_module
from src.infrastructure.rate_limiter import RateLimitMiddleware
from src.infrastructure.security_headers import SecurityHeadersMiddleware


def _middleware_classes(app) -> set[type]:
    return {m.cls for m in app.user_middleware}


def test_security_headers_middleware_is_mounted() -> None:
    app = main_module.create_app()
    assert SecurityHeadersMiddleware in _middleware_classes(app), (
        "SecurityHeadersMiddleware must be added to the production app"
    )


def test_rate_limit_middleware_is_mounted() -> None:
    app = main_module.create_app()
    assert RateLimitMiddleware in _middleware_classes(app), (
        "RateLimitMiddleware must be added to the production app"
    )


def test_security_headers_present_on_responses() -> None:
    app = main_module.create_app()
    client = TestClient(app)
    response = client.get("/health/live")
    # /health may 404, but the middleware runs before routes — the HSTS
    # header must still land on the response.
    assert response.headers.get("Strict-Transport-Security") is not None
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Cache-Control") == "no-store"
    assert response.headers.get("X-Request-ID") is not None


def test_dlq_router_is_mounted() -> None:
    """GET /api/v1/events/dlq should exist (may return 401/403 without auth,
    but must NOT return 404 — the router is reachable)."""
    app = main_module.create_app()
    paths = {route.path for route in app.routes}
    assert any(p.startswith("/api/v1/events/dlq") for p in paths), (
        f"DLQ router not mounted; known routes: {sorted(paths)[:10]}"
    )
