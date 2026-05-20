"""Integration tests for POST /holds/{id}/release.

Tests all three §7.2 idempotency cases:
  Case A: same actor + reason + investigation_id (already released) -> 200
  Case B: already released by different actor or different reason -> 409
  Case C: hold in non-active/non-released state -> 422
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
from src.api.router import router
from src.models.tables import Base, Investigation, OutboxEvent, PaymentHold


@pytest.fixture(scope="session")
def engine():
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


def _make_client(db: Session, user: CurrentUser) -> TestClient:
    app = FastAPI()

    @app.exception_handler(_HTTPException)
    async def _exc_handler(request: Request, exc: _HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(router)

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_tenant_match] = lambda: user
    app.dependency_overrides[require_mfa_elevated] = lambda: user
    return TestClient(app, raise_server_exceptions=False)


def _make_user(tenant_id: str | uuid.UUID, roles: tuple[str, ...]) -> CurrentUser:
    if isinstance(tenant_id, str):
        tenant_id = uuid.UUID(tenant_id)
    return CurrentUser(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="test@example.com",
        status="active",
        roles=roles,
        permissions=(),
    )


def _seed(db: Session):
    tid = str(uuid.uuid4())
    inv_id = str(uuid.uuid4())
    hold_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    inv = Investigation(
        id=inv_id, tenant_id=tid,
        investigation_number="INV-2026-H", title="Hold test",
        subject_type="pharmacy", subject_entity_id="ph-1",
        investigation_type="rule_firing", status="in_progress",
    )
    db.add(inv)

    hold = PaymentHold(
        id=hold_id, tenant_id=tid,
        entity_type="pharmacy", entity_id="ph-1",
        investigation_id=inv_id,
        placed_by=user_id,
        status="active",
        amount_threshold=Decimal("500.00"),
        is_active=True,
    )
    db.add(hold)
    db.flush()
    return tid, inv_id, hold_id, user_id


def _idem(hold_id: str, actor=None) -> dict:
    """Build Idempotency-Key header."""
    return {"Idempotency-Key": f"hold:release:{hold_id}:{actor or 'test'}"}


class TestHoldRelease:
    def test_old_delete_route_is_gone(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        resp = client.delete(f"/api/v1/reclaimrx/holds/{hold_id}?reason=done")
        assert resp.status_code == 404  # DELETE path not registered

    def test_viewer_cannot_release(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.viewer",))
        client = _make_client(db, user)
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "releasing", "investigation_id": inv_id},
            headers=_idem(hold_id, user.id),
        )
        assert resp.status_code == 403

    def test_normal_release_returns_200(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "Resolved -- no fraud", "investigation_id": inv_id},
            headers=_idem(hold_id, user.id),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "released"
        assert body["released_by"] == str(user.id)

    def test_missing_reason_returns_422(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "", "investigation_id": inv_id},
            headers=_idem(hold_id, user.id),
        )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "REASON_REQUIRED"

    def test_investigation_mismatch_returns_403(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        resp = client.post(
            f"/api/v1/reclaimrx/holds/{hold_id}/release",
            json={"reason": "done", "investigation_id": str(uuid.uuid4())},  # wrong inv
            headers=_idem(hold_id, user.id),
        )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "HOLD_INVESTIGATION_MISMATCH"

    # ── Idempotency Case A: same actor + reason + investigation_id -> 200 ──────

    def test_idempotency_case_a_same_actor_and_reason_returns_200(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        payload = {"reason": "Same reason", "investigation_id": inv_id}
        idem = _idem(hold_id, user.id)

        resp1 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json=payload, headers=idem)
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json=payload, headers=idem)
        assert resp2.status_code == 200
        assert resp2.json()["idempotent_replay"] is True

    # ── Idempotency Case B: different actor -> 409 ─────────────────────────────

    def test_idempotency_case_b_different_actor_returns_409(self, db):
        tid, inv_id, hold_id, _ = _seed(db)

        user_a = _make_user(tid, ("reclaimrx.investigator",))
        client_a = _make_client(db, user_a)
        resp1 = client_a.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                              json={"reason": "Reason A", "investigation_id": inv_id},
                              headers=_idem(hold_id, user_a.id))
        assert resp1.status_code == 200

        user_b = _make_user(tid, ("reclaimrx.investigator",))
        client_b = _make_client(db, user_b)
        resp2 = client_b.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                              json={"reason": "Reason A", "investigation_id": inv_id},
                              headers=_idem(hold_id, user_b.id))
        assert resp2.status_code == 409
        body = resp2.json()
        assert body["error"]["code"] == "ALREADY_RELEASED"
        assert "released_at" in body["error"]

    def test_idempotency_case_b_different_reason_same_actor_returns_409(self, db):
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)

        resp1 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "First reason", "investigation_id": inv_id},
                            headers=_idem(hold_id, user.id))
        assert resp1.status_code == 200

        resp2 = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                            json={"reason": "Different reason", "investigation_id": inv_id},
                            headers={"Idempotency-Key": f"hold:release:{hold_id}:{user.id}:retry"})
        assert resp2.status_code == 409

    # ── Idempotency Case C: hold in non-active non-released state -> 422 ───────

    def test_idempotency_case_c_expired_hold_returns_422(self, db):
        tid = str(uuid.uuid4())
        inv_id = str(uuid.uuid4())
        hold_id = str(uuid.uuid4())
        inv = Investigation(id=inv_id, tenant_id=tid, investigation_number="INV-EXP",
                            title="Expired", subject_type="pharmacy",
                            subject_entity_id="ph-x", investigation_type="rule_firing",
                            status="in_progress")
        hold = PaymentHold(id=hold_id, tenant_id=tid, entity_type="pharmacy",
                           entity_id="ph-x", investigation_id=inv_id,
                           placed_by=str(uuid.uuid4()),
                           status="expired",
                           amount_threshold=Decimal("100.00"), is_active=False)
        db.add_all([inv, hold])
        db.flush()

        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)
        resp = client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                           json={"reason": "try to release expired", "investigation_id": inv_id},
                           headers=_idem(hold_id, user.id))
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "HOLD_NOT_ACTIVE"
        assert "expired" in body["error"]["field"]

    def test_outbox_row_written_on_release(self, db):
        """Verify outbox event row is inserted atomically with hold update."""
        tid, inv_id, hold_id, _ = _seed(db)
        user = _make_user(tid, ("reclaimrx.investigator",))
        client = _make_client(db, user)

        before_count = db.query(OutboxEvent).count()
        client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release",
                    json={"reason": "Resolved", "investigation_id": inv_id},
                    headers=_idem(hold_id, user.id))
        after_count = db.query(OutboxEvent).count()
        assert after_count == before_count + 1

        row = db.query(OutboxEvent).order_by(OutboxEvent.created_at.desc()).first()
        assert row.event_type == "payment.hold_released"
        assert row.status == "pending"
        assert row.idempotency_key == f"hold:release:{hold_id}"
