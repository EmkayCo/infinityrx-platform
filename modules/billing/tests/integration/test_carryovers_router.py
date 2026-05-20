"""Integration tests for Carryovers GET router (SP-1 Plan C Task B2).

Covers:
  - Auth gate (no token -> 401) on both endpoints
  - Tenant header mismatch (X-Tenant-Id != JWT tenant) -> 403
  - GET / returns 200 + bare array (empty is OK)
  - GET /{id} non-existent -> 404
  - GET /{id} returns correct carryover for tenant
  - Cache-Control: no-store on all responses
  - Cross-tenant isolation: Tenant A cannot see Tenant B carryovers
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Iterator
from decimal import Decimal
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


def _make_carryover(
    *,
    tenant_id: str,
    ap_record_id: uuid.UUID | None = None,
) -> dict:
    """Return kwargs for a Carryover ORM instance."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "id": uuid.uuid4(),
        "tenant_id": uuid.UUID(tenant_id),
        "ap_record_id": ap_record_id or uuid.uuid4(),
        "amount": Decimal("123.45"),
        "reason": "insufficient funds",
        "upload_id": None,
        "resolved": False,
        "resolved_at": None,
        "resolved_by": None,
        "created_at": now,
        "updated_at": now,
    }


class TestCarryoversAuthGate:
    def test_list_no_auth_returns_401(self, _client):
        resp = _client.get(
            "/api/v1/billing/carryovers",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401

    def test_get_by_id_no_auth_returns_401(self, _client):
        resp = _client.get(
            f"/api/v1/billing/carryovers/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 401


class TestCarryoversTenantMismatch:
    def test_list_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/carryovers",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403

    def test_get_by_id_wrong_tenant_header_returns_403(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/carryovers/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_B},
        )
        assert resp.status_code == 403


class TestCarryoversList:
    def test_list_returns_200_bare_array(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/carryovers",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_cache_control_no_store(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            "/api/v1/billing/carryovers",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.headers.get("cache-control") == "no-store"

    def test_list_returns_tenant_a_carryovers(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Carryover

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        kwargs = _make_carryover(tenant_id=TENANT_A)
        carryover_id = kwargs["id"]
        session = _session_factory()
        try:
            session.add(Carryover(**kwargs))
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            "/api/v1/billing/carryovers",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()]
        assert str(carryover_id) in ids


class TestCarryoversGetById:
    def test_get_nonexistent_returns_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(
            f"/api/v1/billing/carryovers/{uuid.uuid4()}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404

    def test_get_returns_correct_fields(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Carryover

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        ap_id = uuid.uuid4()
        kwargs = _make_carryover(tenant_id=TENANT_A, ap_record_id=ap_id)
        carryover_id = kwargs["id"]
        session = _session_factory()
        try:
            session.add(Carryover(**kwargs))
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/carryovers/{carryover_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(carryover_id)
        assert body["tenant_id"] == TENANT_A
        assert body["ap_record_id"] == str(ap_id)
        assert body["resolved"] is False
        assert resp.headers.get("cache-control") == "no-store"

    def test_get_tenant_b_carryover_as_tenant_a_returns_404(
        self, _client, _session_factory
    ):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        from src.models.tables import Carryover

        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER

        kwargs = _make_carryover(tenant_id=TENANT_B)
        carryover_id = kwargs["id"]
        session = _session_factory()
        try:
            session.add(Carryover(**kwargs))
            session.commit()
        finally:
            session.close()

        resp = _client.get(
            f"/api/v1/billing/carryovers/{carryover_id}",
            headers={"X-Tenant-Id": TENANT_A},
        )
        assert resp.status_code == 404
