"""Integration tests for POST /graph-runs/trigger.

Rate limit: 1/hr/tenant (D13).  409 if run in-flight.
Advisory lock logic is tested in unit tests; here we test HTTP contract.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser, set_current_user
from src.api.dependencies import get_current_user, get_db
from src.api.router import router
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as _HTTPException
from fastapi.responses import JSONResponse

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _make_app(db: Session, user: CurrentUser) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(_HTTPException)
    async def _exc_handler(request: Request, exc: _HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    app.include_router(router)
    set_current_user(user)

    def _db():
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest.fixture()
def investigator(db: Session) -> TestClient:
    user = CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        roles=["reclaimrx.investigator", "reclaimrx.admin"],
    )
    return TestClient(_make_app(db, user), raise_server_exceptions=False)


@pytest.fixture()
def viewer(db: Session) -> TestClient:
    user = CurrentUser(
        id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        roles=["reclaimrx.viewer"],
    )
    return TestClient(_make_app(db, user), raise_server_exceptions=False)


class TestGraphRunTrigger:
    def test_viewer_cannot_trigger(self, viewer: TestClient) -> None:
        resp = viewer.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 403

    def test_investigator_triggers_run(self, investigator: TestClient) -> None:
        from src.jobs.graph_analysis_job import GraphAnalysisJob
        with (
            patch.object(GraphAnalysisJob, "_pg_try_advisory_lock", return_value=True),
            patch.object(GraphAnalysisJob, "_check_running", return_value=None),
            patch.object(
                GraphAnalysisJob, "_run_graph_computation",
                return_value={"rings": [], "investigations": 0, "records": 0},
            ),
        ):
            resp = investigator.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 202
        body = resp.json()
        assert "graph_run_id" in body
        assert body["status"] == "completed"

    def test_409_when_run_in_progress(self, investigator: TestClient) -> None:
        from src.jobs.graph_analysis_job import GraphAnalysisJob
        with patch.object(GraphAnalysisJob, "_pg_try_advisory_lock", return_value=False):
            resp = investigator.post("/api/v1/reclaimrx/graph-runs/trigger")
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "RUN_IN_PROGRESS"
