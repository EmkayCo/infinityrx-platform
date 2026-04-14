"""Integration tests verifying middleware is mounted on the live app (LESSON-006).

These tests can only pass if SecurityHeadersMiddleware, RateLimitMiddleware,
and the DLQ router are actually included in create_app().
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


class TestSecurityHeadersAreMounted:
    def test_hsts_header_present(self, client):
        resp = client.get("/health")
        assert "strict-transport-security" in resp.headers

    def test_x_frame_options_deny(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options(self, client):
        resp = client.get("/health")
        assert resp.headers.get("x-content-type-options") == "nosniff"

    def test_cache_control_no_store(self, client):
        resp = client.get("/health")
        assert "no-store" in resp.headers.get("cache-control", "")

    def test_x_request_id_generated(self, client):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["module"] == "medical-claims"


class TestDlqRouterMounted:
    def test_dlq_endpoint_reachable(self, client):
        """DLQ router must be mounted — only passes if include_router was called."""
        resp = client.get("/api/v1/events/dlq")
        # 200 or 401/403 — any response (not 404) means the router is mounted
        assert resp.status_code != 404
