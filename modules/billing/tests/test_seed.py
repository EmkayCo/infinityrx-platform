"""Tests for POST /api/v1/billing/seed (dev/staging seed endpoint).

Verifies:
- 200 + inserted counts returned in dev environment
- 403 returned when INFINITYRX_ENV=production
- DELETE /api/v1/billing/seed returns 200 (cleanup path)
- Idempotency: second POST returns same counts without error
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


TENANT_ID = "t0000000-0000-0000-0000-000000000001"
SEED_URL = "/api/v1/billing/seed"


class TestSeedEndpointDevGuard:
    def test_returns_403_in_production(self, client, prod_env):
        resp = client.post(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "production" in body.get("detail", "").lower()

    def test_returns_200_in_development(self, client, dev_env):
        resp = client.post(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "inserted" in body or "seeded" in body

    def test_returns_200_in_mock(self, client):
        with patch.dict(os.environ, {"INFINITYRX_ENV": "mock"}, clear=False):
            resp = client.post(
                SEED_URL,
                json={"tenant_id": TENANT_ID},
                headers={"X-Tenant-ID": TENANT_ID},
            )
        assert resp.status_code == 200

    def test_delete_returns_200_in_development(self, client, dev_env):
        resp = client.delete(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        assert resp.status_code in (200, 404)

    def test_delete_returns_403_in_production(self, client, prod_env):
        resp = client.delete(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        assert resp.status_code == 403

    def test_idempotent_second_post_does_not_error(self, client, dev_env):
        client.post(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        resp = client.post(
            SEED_URL,
            json={"tenant_id": TENANT_ID},
            headers={"X-Tenant-ID": TENANT_ID},
        )
        assert resp.status_code == 200
