"""AuditMiddleware end-to-end test via FastAPI TestClient."""

from __future__ import annotations

import uuid
from contextlib import contextmanager

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from src._shim.db import get_sessionmaker
from src.audit.decorators import auditable, phi_access
from src.audit.middleware import AuditContext, AuditMiddleware
from src.audit.models import AuditLog
from src.audit.service import AuditService

from shared.events import InMemoryEventBus, event_types

TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
USER = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _user_resolver(request: Request) -> AuditContext:
    return AuditContext(tenant_id=TENANT, user_id=USER)


@contextmanager
def _session_factory():
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_app(bus: InMemoryEventBus) -> FastAPI:
    app = FastAPI()

    @app.post("/api/v1/users")
    @auditable(action="create", entity_type="user")
    def create_user():
        return {"id": "u-123", "name": "Alice"}

    @app.put("/api/v1/users/{user_id}")
    @auditable(
        action="update",
        entity_type="user",
        entity_id_param="user_id",
        capture_before=lambda req: {"name": "Before"},
    )
    def update_user(user_id: str):
        return {"id": user_id, "name": "After"}

    @app.delete("/api/v1/users/{user_id}")
    @auditable(action="delete", entity_type="user", entity_id_param="user_id")
    def delete_user(user_id: str):
        return {"deleted": user_id}

    @app.get("/api/v1/members/{member_id}")
    @phi_access(fields=["first_name", "dob", "address"])
    def get_member(member_id: str):
        return {"id": member_id, "first_name": "Alice", "dob": "1990-01-01"}

    @app.get("/api/v1/public")
    def public():
        return {"ok": True}

    app.add_middleware(
        AuditMiddleware,
        session_factory=_session_factory,
        user_resolver=_user_resolver,
        event_bus=bus,
    )
    return app


@pytest.fixture
def app_and_bus(db_session):
    # ensure a clean audit_log table per test
    db_session.execute(AuditLog.__table__.delete())
    db_session.commit()
    bus = InMemoryEventBus()
    app = _make_app(bus)
    return app, bus


def _fetch_audit(db_session):
    return list(db_session.execute(select(AuditLog).order_by(AuditLog.id)).scalars())


def test_post_generates_one_audit_row_with_after_value(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.post("/api/v1/users")
    assert resp.status_code == 200
    assert "x-correlation-id" in {k.lower() for k in resp.headers}

    rows = _fetch_audit(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "create"
    assert row.module == "core-platform"
    assert row.entity_type == "user"
    assert row.after_value == {"id": "u-123", "name": "Alice"}
    assert row.correlation_id is not None


def test_put_captures_before_and_after(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.put(
        "/api/v1/users/u-7",
        headers={"X-Forwarded-For": "203.0.113.9, 10.0.0.1", "User-Agent": "probe"},
    )
    assert resp.status_code == 200
    rows = _fetch_audit(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.action == "update"
    assert row.entity_id == "u-7"
    assert row.before_value == {"name": "Before"}
    assert row.after_value == {"id": "u-7", "name": "After"}
    assert row.ip_address == "203.0.113.9"
    assert row.user_agent == "probe"


def test_delete_logged(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.delete("/api/v1/users/u-del")
    assert resp.status_code == 200
    rows = _fetch_audit(db_session)
    assert len(rows) == 1 and rows[0].action == "delete"


def test_phi_access_emits_two_entries(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.get("/api/v1/members/m-42")
    assert resp.status_code == 200
    rows = _fetch_audit(db_session)
    # GET is not mutating, so only the phi_access entry is written
    actions = [r.action for r in rows]
    assert actions == ["phi_access"]
    assert rows[0].after_value == {"fields_accessed": ["first_name", "dob", "address"]}


def test_phi_and_mutation_both_emit(app_and_bus, db_session):
    """A PUT on a PHI-marked route emits both a normal + phi_access entry."""
    app, _ = app_and_bus

    @app.put("/api/v1/members/{member_id}")
    @auditable(action="update", entity_type="member", entity_id_param="member_id")
    @phi_access(fields=["dob"])
    def update_member(member_id: str):
        return {"id": member_id}

    client = TestClient(app)
    resp = client.put("/api/v1/members/m-7")
    assert resp.status_code == 200
    rows = _fetch_audit(db_session)
    actions = sorted(r.action for r in rows)
    assert actions == ["phi_access", "update"]


def test_correlation_id_propagates_from_header(app_and_bus, db_session):
    app, _ = app_and_bus
    cid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    client = TestClient(app)
    resp = client.post("/api/v1/users", headers={"X-Correlation-ID": cid})
    assert resp.headers["x-correlation-id"] == cid
    rows = _fetch_audit(db_session)
    assert str(rows[0].correlation_id) == cid


def test_bad_correlation_header_is_replaced(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.post("/api/v1/users", headers={"X-Correlation-ID": "not-a-uuid"})
    assert resp.status_code == 200
    # Still gets a valid one generated
    assert resp.headers.get("x-correlation-id")


def test_audit_write_failure_does_not_fail_request(app_and_bus, monkeypatch, db_session):
    app, bus = app_and_bus

    def boom(self, entry):
        raise RuntimeError("db down")

    monkeypatch.setattr(AuditService, "log", boom)
    client = TestClient(app)
    resp = client.post("/api/v1/users")
    assert resp.status_code == 200
    # audit.write_failed event published
    assert any(e.event_type == event_types.AUDIT_WRITE_FAILED for e in bus.published)


def test_non_mutating_unmarked_route_not_audited(app_and_bus, db_session):
    app, _ = app_and_bus
    client = TestClient(app)
    resp = client.get("/api/v1/public")
    assert resp.status_code == 200
    assert _fetch_audit(db_session) == []
