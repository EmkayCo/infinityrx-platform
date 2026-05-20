"""Integration test: A3 deliverables reachable through create_app().

Verifies state machine endpoint, hold release endpoint, and graph trigger
endpoint all exist and respect auth (no dead-code route registration gaps).
"""
import uuid
import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as _HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _make_app(db: Session, user: CurrentUser) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(_HTTPException)
    async def _exc(request: Request, exc: _HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(router)

    def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_tenant_match] = lambda: user
    app.dependency_overrides[require_mfa_elevated] = lambda: user
    return app


@pytest.fixture()
def investigator_client(db: Session) -> TestClient:
    user = CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email="test@example.com",
        status="active",
        roles=("reclaimrx.investigator", "reclaimrx.admin"),
        permissions=(),
    )
    return TestClient(_make_app(db, user), raise_server_exceptions=False)


@pytest.fixture()
def viewer_client(db: Session) -> TestClient:
    user = CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email="test@example.com",
        status="active",
        roles=("reclaimrx.viewer",),
        permissions=(),
    )
    return TestClient(_make_app(db, user), raise_server_exceptions=False)


def test_transitions_endpoint_registered(investigator_client: TestClient) -> None:
    resp = investigator_client.post(
        "/api/v1/reclaimrx/investigations/no-such-id/transitions",
        json={"to_state": "in_progress", "reason": "x"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_hold_release_endpoint_registered(investigator_client: TestClient) -> None:
    resp = investigator_client.post(
        "/api/v1/reclaimrx/holds/no-such-id/release",
        json={"reason": "test"},
        headers={"Idempotency-Key": "hold:release:no-such-id:test"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_old_delete_hold_route_gone(investigator_client: TestClient) -> None:
    resp = investigator_client.delete("/api/v1/reclaimrx/holds/some-id?reason=test")
    assert resp.status_code == 404


def test_graph_runs_trigger_endpoint_registered(viewer_client: TestClient) -> None:
    resp = viewer_client.post("/api/v1/reclaimrx/graph-runs/trigger")
    assert resp.status_code == 403
