"""TDD tests for POST /api/v1/reclaimrx/detection-runs (ingest endpoint).

Uses lazy imports for shared.auth.dependencies to avoid PyJWT at collection.
Advisory lock (pg_advisory_xact_lock) is Postgres-only -- patched to no-op
on SQLite test fixtures (same pattern as test_csv_load.py).

Tests cover:
- Happy-path ingest on sample_claims.csv: run completes, anomaly_count set
- Response shape (DetectionRunRead fields)
- Max-rows guard: 413 when file exceeds RECLAIMRX_MAX_UPLOAD_ROWS env var
- Cache-Control: no-store
- Run is scoped to caller tenant
- Auth required
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser
from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID

SAMPLE_CSV = Path(__file__).parent / "fixtures" / "sample_claims.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(tenant_id: uuid.UUID = TEST_TENANT_ID) -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        tenant_id=tenant_id,
        email="test@example.com",
        roles=["reclaimrx.investigator", "reclaimrx.admin"],
    )


def build_app(db: Session, tenant_id: uuid.UUID = TEST_TENANT_ID) -> FastAPI:
    from shared.auth.dependencies import get_current_user  # noqa: PLC0415

    app = FastAPI()
    app.include_router(router)
    _user = _make_user(tenant_id)

    def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[require_tenant_match] = lambda: _user
    app.dependency_overrides[require_mfa_elevated] = lambda: _user
    return app


# Patch pg_advisory_xact_lock to a no-op for all SQLite tests.
# Same pattern used by test_csv_load.py.
_NO_ADVISORY_LOCK = patch(
    "src.detection.csv_ingest._acquire_advisory_lock",
    return_value=None,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db: Session) -> TestClient:
    app = build_app(db)
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests: response shape
# ---------------------------------------------------------------------------


class TestIngestResponseShape:
    def test_post_returns_detection_run_read(self, client: TestClient) -> None:
        """POST with sample CSV returns DetectionRunRead with required fields."""
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
                data={"run_label": "test-run-001"},
            )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        required_fields = [
            "id",
            "run_label",
            "status",
            "data_source",
            "source_filename",
            "record_count",
            "anomaly_count",
            "started_at",
        ]
        for f in required_fields:
            assert f in data, f"Missing field: {f}"

    def test_post_run_completes(self, client: TestClient) -> None:
        """After synchronous ingest, status is completed."""
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
            )
        assert resp.status_code == 201
        assert resp.json()["status"] == "completed"

    def test_post_anomaly_count_gte_zero(self, client: TestClient) -> None:
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
            )
        assert resp.status_code == 201
        assert resp.json()["anomaly_count"] >= 0

    def test_cache_control_no_store(self, client: TestClient) -> None:
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
            )
        assert resp.status_code == 201
        assert resp.headers.get("cache-control") == "no-store"

    def test_run_label_field_present(self, client: TestClient) -> None:
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
                data={"run_label": "my-custom-label"},
            )
        assert resp.status_code == 201
        assert "run_label" in resp.json()

    def test_source_filename_set(self, client: TestClient) -> None:
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK:
            resp = client.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("my_upload.csv", csv_content, "text/csv")},
            )
        assert resp.status_code == 201
        assert resp.json()["source_filename"] is not None


# ---------------------------------------------------------------------------
# Tests: tenant scoping
# ---------------------------------------------------------------------------


class TestIngestTenantScoping:
    def test_uploaded_run_scoped_to_caller_tenant(self, db: Session) -> None:
        from sqlalchemy import select  # noqa: PLC0415
        from src.models.detection_run_models import DetectionRun  # noqa: PLC0415

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        csv_content = SAMPLE_CSV.read_bytes()
        with _NO_ADVISORY_LOCK, TestClient(app, raise_server_exceptions=True) as c:
            resp = c.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
            )
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        run = db.execute(
            select(DetectionRun).where(DetectionRun.id == uuid.UUID(run_id))
        ).scalar_one_or_none()
        assert run is not None
        assert run.tenant_id == TEST_TENANT_ID


# ---------------------------------------------------------------------------
# Tests: max-rows guard (413)
# ---------------------------------------------------------------------------


class TestIngestMaxRowsGuard:
    def test_oversized_file_returns_413(self, db: Session) -> None:
        """File row count exceeding RECLAIMRX_MAX_UPLOAD_ROWS returns HTTP 413."""
        original = os.environ.get("RECLAIMRX_MAX_UPLOAD_ROWS")
        # sample CSV has ~54 data rows; set limit to 1 to trigger the guard
        os.environ["RECLAIMRX_MAX_UPLOAD_ROWS"] = "1"
        try:
            app = build_app(db)
            csv_content = SAMPLE_CSV.read_bytes()
            with _NO_ADVISORY_LOCK, TestClient(app, raise_server_exceptions=False) as c:
                resp = c.post(
                    "/api/v1/reclaimrx/detection-runs",
                    files={"file": ("sample_claims.csv", csv_content, "text/csv")},
                )
            assert resp.status_code == 413
        finally:
            if original is None:
                os.environ.pop("RECLAIMRX_MAX_UPLOAD_ROWS", None)
            else:
                os.environ["RECLAIMRX_MAX_UPLOAD_ROWS"] = original


# ---------------------------------------------------------------------------
# Tests: auth
# ---------------------------------------------------------------------------


class TestIngestAuth:
    def test_requires_auth(self) -> None:
        app = FastAPI()
        app.include_router(router)
        csv_content = SAMPLE_CSV.read_bytes()
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/api/v1/reclaimrx/detection-runs",
                files={"file": ("sample_claims.csv", csv_content, "text/csv")},
            )
        assert resp.status_code in (401, 422)