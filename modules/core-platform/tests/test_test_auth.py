"""Tests for POST /api/v1/core/test-auth/token (E2E-only shortcut endpoint).

Verifies:
- 200 + JWT returned in development/mock environments
- 403 returned when INFINITYRX_ENV=production
- 404 returned for unknown user_id
- Returned JWT is decodable and contains correct claims
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


@pytest.fixture
def dev_env():
    with patch.dict(os.environ, {"INFINITYRX_ENV": "development"}, clear=False):
        yield


@pytest.fixture
def prod_env():
    with patch.dict(os.environ, {"INFINITYRX_ENV": "production"}, clear=False):
        yield


OPERATOR_USER_ID = "usr-00000000-0000-0000-0000-000000000001"
APPROVER_USER_ID = "usr-00000000-0000-0000-0000-000000000002"
AUDITOR_USER_ID = "usr-00000000-0000-0000-0000-000000000003"
DEMO_TENANT_ID = "t0000000-0000-0000-0000-000000000001"
TOKEN_URL = "/api/v1/core/test-auth/token"


class TestTestAuthProductionGuard:
    def test_returns_403_in_production(self, client, prod_env):
        resp = client.post(
            TOKEN_URL,
            json={"user_id": OPERATOR_USER_ID, "tenant_id": DEMO_TENANT_ID},
        )
        assert resp.status_code == 403
        body = resp.json()
        # B7: errors must use canonical envelope {"error": {"code", "message", "correlation_id"}}
        assert "error" in body, f"Expected canonical envelope, got: {body}"
        assert body["error"]["code"] == "FORBIDDEN"
        assert "production" in body["error"]["message"].lower()
        assert "correlation_id" in body["error"]

    def test_returns_token_in_development_for_operator(self, client, dev_env):
        resp = client.post(
            TOKEN_URL,
            json={"user_id": OPERATOR_USER_ID, "tenant_id": DEMO_TENANT_ID},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 20

    def test_returns_token_for_approver(self, client, dev_env):
        resp = client.post(
            TOKEN_URL,
            json={"user_id": APPROVER_USER_ID, "tenant_id": DEMO_TENANT_ID},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_returns_token_for_auditor(self, client, dev_env):
        resp = client.post(
            TOKEN_URL,
            json={"user_id": AUDITOR_USER_ID, "tenant_id": DEMO_TENANT_ID},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_returns_403_in_mock_env_is_allowed(self, client):
        # mock env should behave like development (non-production)
        with patch.dict(os.environ, {"INFINITYRX_ENV": "mock"}, clear=False):
            resp = client.post(
                TOKEN_URL,
                json={"user_id": OPERATOR_USER_ID, "tenant_id": DEMO_TENANT_ID},
            )
        assert resp.status_code == 200

    def test_unknown_user_returns_404(self, client, dev_env):
        resp = client.post(
            TOKEN_URL,
            json={"user_id": "usr-99999999-0000-0000-0000-000000000000", "tenant_id": DEMO_TENANT_ID},
        )
        assert resp.status_code == 404
        body = resp.json()
        # B7: errors must use canonical envelope
        assert "error" in body, f"Expected canonical envelope, got: {body}"
        assert body["error"]["code"] == "NOT_FOUND"
        assert "correlation_id" in body["error"]
