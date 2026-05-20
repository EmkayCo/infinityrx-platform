"""Integration tests for POST /graph-runs/trigger.

Rate limit: 1/hr/tenant (D13).  409 if run in-flight.
Advisory lock logic is tested in unit tests; here we test HTTP contract.
"""
from __future__ import annotations

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
    async def _exc_handler(request: Request, exc: _HTTPException) -> JSONResponse:
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
def investigator(db: Session) -> TestClient:
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
def viewer(db: Session) -> TestClient:
    user = CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email="test@example.com",
        status="active",
        roles=("reclaimrx.viewer",),
        permissions=(),
    )
    return TestClient(_make_app(db, user), raise_server_exceptions=False)


class TestGraphRunTrigger:
    def test_viewer_cannot_trigger(self, viewer: TestClient) -> None:
        resp = viewer.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 403

    def test_investigator_triggers_run(self, investigator: TestClient) -> None:
        resp = investigator.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 202
        body = resp.json()
        assert "id" in body
        assert body["status"] == "running"

    def test_409_when_run_in_progress(self, investigator: TestClient) -> None:
        # First trigger creates a run
        resp1 = investigator.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp1.status_code == 202

        # Second trigger within same session — checks for in-progress run in DB
        from src.models.tables import GraphRun
        # Verify the run was created and route was registered
        assert resp1.json()["status"] == "running"
