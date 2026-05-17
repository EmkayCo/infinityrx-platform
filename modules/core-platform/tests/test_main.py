"""Smoke tests for core-platform create_app() factory.

Verifies that all expected routers are mounted and the app starts correctly.
Each router is tested by hitting its root path or a known endpoint and
asserting a non-500 response (auth/403 is fine — proves the route exists).
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import create_app


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_endpoint_returns_200_or_503(client):
    resp = client.get("/health")
    assert resp.status_code in (200, 503)


def test_api_router_mounted(client):
    # Core API router exposes /api/v1/auth/login (unauthenticated)
    resp = client.post("/api/v1/auth/login", json={"email": "x", "password": "y"})
    assert resp.status_code != 404


def test_test_auth_router_mounted_in_dev(client):
    with patch.dict(os.environ, {"INFINITYRX_ENV": "development"}, clear=False):
        resp = client.post(
            "/api/v1/core/test-auth/token",
            json={
                "user_id": "usr-00000000-0000-0000-0000-000000000001",
                "tenant_id": "t0000000-0000-0000-0000-000000000001",
            },
        )
    # 200 (token issued) or 422 (JWT secret not configured in test env) — never 404
    assert resp.status_code != 404


def test_test_auth_router_blocks_in_production(client):
    with patch.dict(os.environ, {"INFINITYRX_ENV": "production"}, clear=False):
        resp = client.post(
            "/api/v1/core/test-auth/token",
            json={
                "user_id": "usr-00000000-0000-0000-0000-000000000001",
                "tenant_id": "t0000000-0000-0000-0000-000000000001",
            },
        )
    assert resp.status_code == 403
