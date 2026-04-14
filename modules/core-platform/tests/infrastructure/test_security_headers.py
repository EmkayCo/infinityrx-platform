"""Tests for security headers middleware."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from src.infrastructure.security_headers import SecurityHeadersMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/test")
    async def _test():
        return {"ok": True}

    return app


def test_hsts_header():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["Strict-Transport-Security"] == "max-age=31536000; includeSubDomains; preload"


def test_x_content_type_options():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_x_frame_options():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_csp_header():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["Content-Security-Policy"] == "default-src 'self'"


def test_cache_control_no_store():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["Cache-Control"] == "no-store"


def test_referrer_policy():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_x_request_id_generated():
    client = TestClient(_make_app())
    resp = client.get("/test")
    request_id = resp.headers.get("X-Request-ID")
    assert request_id is not None
    assert len(request_id) > 0


def test_x_request_id_echoed():
    client = TestClient(_make_app())
    resp = client.get("/test", headers={"X-Request-ID": "my-corr-123"})
    assert resp.headers["X-Request-ID"] == "my-corr-123"


def test_pragma_no_cache():
    client = TestClient(_make_app())
    resp = client.get("/test")
    assert resp.headers["Pragma"] == "no-cache"


def test_all_security_headers_present():
    """Verify all required headers are set in a single request."""
    client = TestClient(_make_app())
    resp = client.get("/test")
    required = [
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Content-Security-Policy",
        "Cache-Control",
        "X-Request-ID",
        "Referrer-Policy",
    ]
    for h in required:
        assert h in resp.headers, f"Missing header: {h}"
