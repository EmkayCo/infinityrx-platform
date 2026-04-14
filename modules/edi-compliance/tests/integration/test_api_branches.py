"""Branch coverage for API routes — error paths and missing coverage."""

from __future__ import annotations

import sys
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

import os
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from fastapi.testclient import TestClient

from tests.conftest import _FAKE_USER_FOR_TESTS  # noqa: E402

TENANT_ID = "11111111-1111-1111-1111-111111111111"


async def _mock_get_session():
    yield None


@pytest.fixture(scope="module")
def client():
    from src.main import create_app
    from shared.auth.dependencies import get_current_user
    app = create_app()
    try:
        from shared.db.session import get_session  # type: ignore[import]
        app.dependency_overrides[get_session] = _mock_get_session
    except (ImportError, Exception):
        pass
    app.dependency_overrides[get_current_user] = lambda: _FAKE_USER_FOR_TESTS
    return TestClient(app, raise_server_exceptions=False)


# ---- generate endpoint error paths ----

def test_generate_835_invalid_input(client):
    """Missing required fields returns 422."""
    resp = client.post(
        "/api/v1/edi/generate/835",
        json={"tenant_id": TENANT_ID},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422


def test_generate_837p_invalid_input(client):
    """Missing required 837P fields returns 422."""
    resp = client.post(
        "/api/v1/edi/generate/837p",
        json={"tenant_id": TENANT_ID},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422


def test_generate_270_invalid_input(client):
    """Missing required 270 fields returns 422 (Pydantic validation)."""
    resp = client.post(
        "/api/v1/edi/generate/270",
        json={"tenant_id": TENANT_ID},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422


# ---- parse endpoint error paths ----

def test_parse_835_invalid_edi(client):
    """Completely invalid EDI content returns 422."""
    resp = client.post(
        "/api/v1/edi/parse/835",
        json={"content": "NOTVALID EDI CONTENT"},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422


def test_parse_validate_invalid_edi(client):
    """Validate endpoint with invalid content returns 200 with is_valid=false."""
    resp = client.post(
        "/api/v1/edi/parse/validate",
        json={"content": "NOTVALID"},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert not data["is_valid"]


# ---- tenant header error paths ----

def test_generate_835_missing_tenant(client):
    """Missing x-tenant-id on generate/835 returns 401."""
    resp = client.post("/api/v1/edi/generate/835", json={})
    assert resp.status_code == 401


def test_generate_835_invalid_tenant(client):
    """Invalid UUID x-tenant-id on generate/835 returns 403."""
    resp = client.post(
        "/api/v1/edi/generate/835",
        json={},
        headers={"x-tenant-id": "not-a-uuid"},
    )
    assert resp.status_code == 403


def test_parse_835_missing_tenant(client):
    """Missing x-tenant-id on parse/835 returns 401."""
    resp = client.post("/api/v1/edi/parse/835", json={"content": "X"})
    assert resp.status_code == 401


def test_parse_835_invalid_tenant(client):
    """Invalid UUID x-tenant-id on parse/835 returns 403."""
    resp = client.post(
        "/api/v1/edi/parse/835",
        json={"content": "X"},
        headers={"x-tenant-id": "bad-uuid"},
    )
    assert resp.status_code == 403


def test_compliance_missing_tenant(client):
    """Missing x-tenant-id on compliance dashboard returns 401."""
    resp = client.get("/api/v1/edi/compliance")
    assert resp.status_code == 401


def test_compliance_invalid_tenant(client):
    """Invalid UUID x-tenant-id on compliance dashboard returns 403."""
    resp = client.get(
        "/api/v1/edi/compliance",
        headers={"x-tenant-id": "not-a-uuid"},
    )
    assert resp.status_code == 403


def test_trading_partners_missing_tenant(client):
    """Missing x-tenant-id on trading partners returns 401."""
    resp = client.get("/api/v1/edi/trading-partners")
    assert resp.status_code == 401


def test_trading_partners_invalid_tenant(client):
    """Invalid UUID x-tenant-id on trading partners returns 403."""
    resp = client.get(
        "/api/v1/edi/trading-partners",
        headers={"x-tenant-id": "not-a-valid-uuid"},
    )
    assert resp.status_code == 403


def test_create_trading_partner_missing_tenant(client):
    """Missing x-tenant-id on create trading partner returns 401."""
    resp = client.post("/api/v1/edi/trading-partners", json={})
    assert resp.status_code == 401


def test_create_trading_partner_invalid_tenant(client):
    """Invalid UUID x-tenant-id on create returns 403."""
    resp = client.post(
        "/api/v1/edi/trading-partners",
        json={},
        headers={"x-tenant-id": "bad"},
    )
    assert resp.status_code == 403


def test_create_trading_partner_invalid_body(client):
    """Create trading partner with missing required fields returns 422."""
    resp = client.post(
        "/api/v1/edi/trading-partners",
        json={"name": "only-name"},
        headers={"x-tenant-id": TENANT_ID},
    )
    assert resp.status_code == 422
