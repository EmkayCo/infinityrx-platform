"""Integration test: full middleware stack is mounted in ai-nlp create_app().

LESSON-006 enforcement: test only passes if SecurityHeadersMiddleware is mounted
via create_app(). Removing it from create_app() causes this test to fail.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.app import create_app


def test_hsts_header_present_on_health_response() -> None:
    """HSTS must appear on /health — proves SecurityHeadersMiddleware is mounted."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers.get("Strict-Transport-Security") is not None, (
        "SecurityHeadersMiddleware not mounted in ai-nlp create_app() — LESSON-006"
    )
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Cache-Control") == "no-store"
