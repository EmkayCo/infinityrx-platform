"""Integration test: SecurityHeadersMiddleware is mounted in billing create_app().

LESSON-006 enforcement: this test only passes if SecurityHeadersMiddleware
is mounted on the app via create_app(). Removing it from create_app() will
cause this test to fail immediately.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import create_app


def test_hsts_header_present_on_health_response() -> None:
    """HSTS must appear on /health — proves SecurityHeadersMiddleware is mounted."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers.get("Strict-Transport-Security") is not None, (
        "SecurityHeadersMiddleware not mounted in billing create_app() — LESSON-006"
    )
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Cache-Control") == "no-store"


def test_create_app_returns_fresh_instance() -> None:
    """Each call to create_app() returns a distinct FastAPI instance."""
    app1 = create_app()
    app2 = create_app()
    assert app1 is not app2
