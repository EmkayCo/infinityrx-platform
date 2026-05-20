"""Integration tests for POST /investigations/{id}/transitions.

Uses TestClient with FastAPI dependency_overrides for auth/db.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as _HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router as _router
from src.models.tables import Base, Investigation


@pytest.fixture(scope="session")
def engine():
    # check_same_thread=False required for TestClient (runs in separate thread)
    return create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})


@pytest.fixture(scope="session", autouse=True)
def _create_tables(engine):
    Base.metadata.create_all(engine)


@pytest.fixture()
def db(engine):
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    txn.rollback()
    conn.close()


def _make_client(db: Session, roles: tuple[str, ...], tenant_id: str | None = None) -> tuple:
    """Create TestClient with dependency_overrides for db + current user."""
    tid_uuid = uuid.UUID(tenant_id) if tenant_id else uuid.uuid4()
    user = CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tid_uuid,
        email="test@example.com",
        status="active",
        roles=roles,
        permissions=(),
    )

    app = FastAPI()

    @app.exception_handler(_HTTPException)
    async def _exc_handler(request: Request, exc: _HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(_router)

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_tenant_match] = lambda: user
    app.dependency_overrides[require_mfa_elevated] = lambda: user

    return TestClient(app, raise_server_exceptions=False), user, tid_uuid


def _seed_investigation(db: Session, status: str = "open", tenant_id: str | None = None) -> tuple:
    tid = tenant_id or str(uuid.uuid4())
    inv_id = str(uuid.uuid4())
    inv = Investigation(
        id=inv_id, tenant_id=tid,
        investigation_number="INV-2026-T1",
        title="Test", subject_type="pharmacy",
        subject_entity_id="ph-1",
        investigation_type="rule_firing", status=status,
    )
    db.add(inv)
    db.flush()
    return inv_id, tid


class TestTransitionsEndpoint:
    def test_viewer_cannot_transition(self, db):
        inv_id, tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.viewer",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "start"},
        )
        assert resp.status_code == 403

    def test_investigator_can_transition_open_to_in_progress(self, db):
        inv_id, tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.investigator",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "Starting"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in_progress"

    def test_invalid_transition_returns_422(self, db):
        inv_id, tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.investigator",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "closed_confirmed", "reason": "skip"},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "INVALID_TRANSITION"
        assert "in_progress" in body["error"]["field"]

    def test_missing_reason_returns_422(self, db):
        inv_id, tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.investigator",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": ""},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MISSING_REQUIRED_FIELD"

    def test_unknown_investigation_returns_404(self, db):
        client, user, _ = _make_client(db, ("reclaimrx.investigator",))
        resp = client.post(
            "/api/v1/reclaimrx/investigations/does-not-exist/transitions",
            json={"to_state": "in_progress", "reason": "x"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_cross_tenant_returns_404(self, db):
        inv_id, _tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.investigator",))  # different tenant
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "x"},
        )
        assert resp.status_code == 404

    def test_escalated_to_in_progress_422_for_investigator(self, db):
        inv_id, tid = _seed_investigation(db, "escalated")
        client, user, _ = _make_client(db, ("reclaimrx.investigator",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "override"},
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "INSUFFICIENT_ROLE"

    def test_admin_can_move_escalated_to_in_progress(self, db):
        inv_id, tid = _seed_investigation(db, "escalated")
        client, user, _ = _make_client(db, ("reclaimrx.admin",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "admin override"},
        )
        assert resp.status_code == 200

    def test_closed_confirmed_to_in_progress_invalid_even_for_admin(self, db):
        inv_id, tid = _seed_investigation(db, "closed_confirmed")
        client, user, _ = _make_client(db, ("reclaimrx.admin",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "skip"},
        )
        assert resp.status_code == 422

    def test_transition_status_in_response(self, db):
        inv_id, tid = _seed_investigation(db)
        client, user, _ = _make_client(db, ("reclaimrx.investigator",), tid)
        resp = client.post(
            f"/api/v1/reclaimrx/investigations/{inv_id}/transitions",
            json={"to_state": "in_progress", "reason": "start"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in_progress"
        assert "id" in body
