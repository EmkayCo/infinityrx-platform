"""Integration tests: JWT auth is required on all prescriber-directory routes (CR-03).

All routes in the prescriber-directory module must require a valid Bearer token.
These tests prove that:

1. Unauthenticated requests → 401 Unauthorized
2. Authenticated requests with a valid JWT → not-401 (200/422/404 is acceptable)

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

    def test_npi_lookup_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/prescribers/lookup/1234567890",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_search_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/prescribers/search",
            params={"q": "Smith"},
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_validate_npi_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/prescribers/validate/1234567890",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_taxonomies_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/prescribers/taxonomies",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401

    def test_specialties_requires_auth(self, client_and_token):
        client, _ = client_and_token
        resp = client.get(
            "/api/v1/prescribers/specialties",
            headers={"x-tenant-id": str(_TENANT_ID)},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Authenticated requests pass the auth gate
# ---------------------------------------------------------------------------

class TestAuthenticatedRequestsPassAuthGate:
    """With a valid JWT, the auth dependency resolves and does not return 401."""

    def test_npi_lookup_with_token_passes_auth_gate(self, client_and_token):
        """Auth gate passes; 404 is acceptable for a non-existent NPI."""
        client, token = client_and_token
        resp = client.get(
            "/api/v1/prescribers/lookup/1234567890",
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-id": str(_TENANT_ID),
            },
        )
        assert resp.status_code != 401, (
            f"Auth should pass with valid token, but got 401. "
            f"Response: {resp.text}"
        )

    def test_search_with_token_passes_auth_gate(self, client_and_token):
        client, token = client_and_token
        resp = client.get(
            "/api/v1/prescribers/search",
            params={"q": "Smith"},
            headers={
                "Authorization": f"Bearer {token}",
                "x-tenant-id": str(_TENANT_ID),
            },
        )
        assert resp.status_code != 401, (
            f"Auth should pass with valid token, got {resp.status_code}: {resp.text}"
        )
