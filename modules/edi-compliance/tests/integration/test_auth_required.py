"""Integration tests: JWT auth is required on all edi-compliance routes (CR-03).

Every route in generate.py, parse.py, compliance.py, and trading_partners.py
must require a valid Bearer token. These tests prove that:

1. Unauthenticated requests → 401 Unauthorized
2. Authenticated requests with a valid JWT → not-401 (200/422 is fine, but auth passes)

Uses configure_auth() with in-memory fakes so no DB setup is needed.
"""

from __future__ import annotations

import sys
import os
import uuid
from pathlib import Path

_MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(_MODULE_ROOT))

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")

import pytest
from fastapi.testclient import TestClient

from shared.auth.dependencies import CurrentUser, configure_auth
from shared.auth.jwt_tokens import create_access_token
from shared.auth.tokens_repo import InMemoryRevokedTokenRepo
from src.main import create_app

_TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_USER_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

_FAKE_USER = CurrentUser(
    id=_USER_ID,
    tenant_id=_TENANT_ID,
    email="test@example.com",
    status="active",
    roles=("tenant_admin",),
)


def _setup_auth() -> str:
    """Configure in-memory auth and return a valid bearer token."""
    revoked_repo = InMemoryRevokedTokenRepo()
    configure_auth(
        user_loader=lambda uid: _FAKE_USER if uid == _USER_ID else None,
        revoked_repo=revoked_repo,
    )
    token = create_access_token(_USER_ID, _TENANT_ID, ["tenant_admin"])
    return token


@pytest.fixture(scope="module")
def client_and_token():
    token = _setup_auth()
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    return client, token


# ---------------------------------------------------------------------------
# Unauthenticated requests → 401
# ---------------------------------------------------------------------------

class TestUnauthenticatedRequestsAreRejected:
    """Every route must return 401 when no Authorization header is present."""

    def test_parse_835_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.post(
            "/api/v1/edi/parse/835",
            json={"content": "ISA*00*..."},
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_parse_271_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.post(
            "/api/v1/edi/parse/271",
            json={"content": "ISA*00*..."},
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_generate_835_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.post(
            "/api/v1/edi/generate/835",
            json={},
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_generate_270_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.post(
            "/api/v1/edi/generate/270",
            json={},
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_compliance_dashboard_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/edi/compliance",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_trading_partners_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/edi/trading-partners",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated requests pass the auth gate (may fail for other reasons)
# ---------------------------------------------------------------------------

class TestAuthenticatedRequestsPassAuthGate:
    """With a valid JWT, the auth dependency resolves and does not return 401."""

    def test_parse_validate_with_token(self, client_and_token):
        """Validate endpoint accepts auth; returns 422 or 200 (not 401) on bad content."""
        client, token = client_and_token
        resp = client.post(
            "/api/v1/edi/parse/validate",
            json={"content": "not-valid-edi"},
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-id": str(_TENANT_ID),
            },
        )
        # Auth passes → not 401. Content may fail → 422 or 200 with errors; both are fine.
        assert resp.status_code != 401, (
            f"Auth should pass with valid token, but got 401. "
            f"Response: {resp.json()}"
        )

    def test_generate_999_with_token_passes_auth_gate(self, client_and_token):
        """Auth gate passes; payload validation may still fail (422) — that is correct."""
        client, token = client_and_token
        resp = client.post(
            "/api/v1/edi/generate/999",
            json={},  # missing required fields → 422, not 401
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-id": str(_TENANT_ID),
            },
        )
        assert resp.status_code != 401, (
            f"Auth should pass with valid token, got {resp.status_code}: {resp.text}"
        )
