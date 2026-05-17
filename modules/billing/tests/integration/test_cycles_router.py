# modules/billing/tests/integration/test_cycles_router.py
# Integration tests for Cycles router (SP-1 Plan B -- B1 fix).
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

TENANT_A = str(uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaac"))
USER_OP = uuid.UUID("11111111-1111-1111-1111-111111111113")
OPERATOR_USER = MagicMock(
    id=USER_OP,
    tenant_id=uuid.UUID(TENANT_A),
    roles=("operator",),
    has_role=lambda r: r == "operator",
)


@pytest.fixture(scope="module")
def _engine():
    from src.models.tables import BillingBase
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _make_batch(tenant_id, batch_number="2026-05", status="generated", ap_count=5):
    from src.models.tables import PaymentBatch
    now = datetime.datetime.now(datetime.timezone.utc)
    return PaymentBatch(
        id=uuid.uuid4(), tenant_id=tenant_id, batch_number=batch_number,
        payment_route="ach", total_amount=Decimal("1000.00"),
        payment_count=ap_count, ap_count=ap_count, status=status,
        generated_at=now, created_at=now, updated_at=now,
    )


class TestCyclesAuthGate:
    def test_list_no_auth_returns_401(self, _client):
        resp = _client.get("/api/v1/billing/cycles", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 401

    def test_get_no_auth_returns_401(self, _client):
        resp = _client.get(f"/api/v1/billing/cycles/{uuid.uuid4()}", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 401

    def test_close_no_auth_returns_401(self, _client):
        resp = _client.post(f"/api/v1/billing/cycles/{uuid.uuid4()}/close", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 401


class TestCyclesListShape:
    def test_list_returns_cycle_shaped_list(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        batch = _make_batch(uuid.UUID(TENANT_A), batch_number="2026-05-list", ap_count=10)
        session = _session_factory()
        try:
            session.add(batch); session.commit(); batch_id = str(batch.id)
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/cycles", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        body = resp.json()
        assert "results" in body and "total" in body
        ids = [c["id"] for c in body["results"]]
        assert batch_id in ids
        cycle = next(c for c in body["results"] if c["id"] == batch_id)
        assert cycle["tenant_id"] == TENANT_A
        assert cycle["period_label"] == "2026-05-list"
        assert cycle["status"] == "open"
        for field in ("window_closed_at", "origin_upload_id", "total_billed_amount", "claim_count", "created_at", "updated_at"):
            assert field in cycle, f"missing field: {field}"

    def test_list_status_filter_closed(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        closed_batch = _make_batch(uuid.UUID(TENANT_A), batch_number="2026-03-closed", status="settled")
        open_batch = _make_batch(uuid.UUID(TENANT_A), batch_number="2026-04-open", status="generated")
        session = _session_factory()
        try:
            session.add(closed_batch); session.add(open_batch); session.commit()
        finally:
            session.close()
        resp = _client.get("/api/v1/billing/cycles?status=closed", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert all(c["status"] == "closed" for c in results)


class TestCyclesGetById:
    def test_get_by_id_returns_cycle_shape(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        batch = _make_batch(uuid.UUID(TENANT_A), batch_number="2026-05-get")
        session = _session_factory()
        try:
            session.add(batch); session.commit(); batch_id = str(batch.id)
        finally:
            session.close()
        resp = _client.get(f"/api/v1/billing/cycles/{batch_id}", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        cycle = resp.json()
        assert cycle["id"] == batch_id
        assert cycle["period_label"] == "2026-05-get"

    def test_get_unknown_returns_404(self, _client):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        resp = _client.get(f"/api/v1/billing/cycles/{uuid.uuid4()}", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 404


class TestCyclesClose:
    def test_close_transitions_to_closing(self, _client, _session_factory):
        from shared.auth.dependencies import get_current_user
        from src.main import app
        app.dependency_overrides[get_current_user] = lambda: OPERATOR_USER
        batch = _make_batch(uuid.UUID(TENANT_A), batch_number="2026-05-close", status="pending_close")
        session = _session_factory()
        try:
            session.add(batch); session.commit(); batch_id = str(batch.id)
        finally:
            session.close()
        resp = _client.post(f"/api/v1/billing/cycles/{batch_id}/close", headers={"X-Tenant-Id": TENANT_A})
        assert resp.status_code == 200
        assert resp.json()["status"] == "closing"