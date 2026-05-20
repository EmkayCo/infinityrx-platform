"""Integration tests for Payment Runs GET router (SP-1 Plan C Task B2).

Covers:
  - Auth gate (no token -> 401) on both endpoints
  - Tenant header mismatch (X-Tenant-Id != JWT tenant) -> 403
  - GET / returns 200 + bare array (empty is OK -- stub returns empty)
  - GET /{id} non-existent -> 404
  - Cache-Control: no-store on all responses
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"))
TENANT_B = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111111")

OPERATOR_USER = MagicMock(
    id=USER_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in BillingBase.metadata.tables.values():
        table.schema = None
    BillingBase.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def _session_factory(_engine):
    return sessionmaker(bind=_engine, expire_on_commit=False)


@pytest.fixture()
def _client(_engine, _session_factory):
    from src.api.dependencies import get_db
    from src.db.session import set_engine
    from src.main import app

    set_engine(_engine)

    def override_db() -> Iterator[Session]:
        session = _session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


class TestPaymentRunsAuthGate:
    def test_list_no_auth_returns_401(self, _client):
        resp = _client.get(
            "/api/v1/billing/payment-runs",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_get_by_id_no_auth_returns_401(self, _client):
        resp = _client.get(
            f"/api/v1/billing/payment-runs/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401


class TestPaymentRunsTenantMismatch:
    def test_list_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/payment-runs",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_get_by_id_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/payment-runs/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403


class TestPaymentRunsList:
    def test_list_returns_200_bare_array(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/payment-runs",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_returns_empty_array(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/payment-runs",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_cache_control_no_store(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/payment-runs",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.headers.get("cache-control") == "no-store"


class TestPaymentRunsGetById:
    def test_get_any_id_returns_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/payment-runs/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_get_cache_control_no_store_on_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/payment-runs/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        # 404 is served via HTTPException -> canonical handler sets Cache-Control: no-store
        assert resp.status_code == 404
        assert resp.headers.get("cache-control") == "no-store"
