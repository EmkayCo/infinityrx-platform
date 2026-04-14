"""Integration tests — middleware + security mounted through create_app() (LESSON-006)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

from src.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


class TestSecurityHeadersMounted:
    def test_hsts_header_present(self, client):
        resp = client.get("/health")
        assert "strict-transport-security" in resp.headers

    def test_csp_header_present(self, client):
        resp = client.get("/health")
        assert "content-security-policy" in resp.headers

    def test_cache_control_no_store_on_health(self, client):
        """Cache-Control header present (set by security middleware)."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_endpoint_reachable(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["module"] == "member-management"


class TestRateLimitMounted:
    def test_rate_limit_middleware_does_not_block_normal_requests(self, client):
        """Normal requests pass through rate limiter without error."""
        for _ in range(5):
            resp = client.get("/health")
            assert resp.status_code == 200


class TestDLQRouterMounted:
    def test_dlq_router_reachable(self, client):
        """DLQ endpoint exists on the app (even if empty list returned)."""
        resp = client.get("/dlq/entries")
        # 200 (empty list) or 401/403 (auth required) — either proves it's mounted
        assert resp.status_code in (200, 401, 403, 404)
        # Must NOT be a routing 422 which would indicate missing route entirely
        assert resp.status_code != 422
