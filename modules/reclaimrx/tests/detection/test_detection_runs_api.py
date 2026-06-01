"""TDD tests for GET /api/v1/reclaimrx/detection-runs and /detection-runs/{id}.

Uses lazy imports for shared.auth.dependencies to avoid PyJWT requirement at
collection time. Auth/tenant deps overridden via FastAPI dependency_overrides.

Tests cover:
- List: fields, newest-first order, data_quality extraction, empty DB
- Detail: same fields + per_rule_breakdown (GROUP BY anomaly.finding_code)
- Cross-tenant isolation on both list and detail endpoints
- Cache-Control: no-store on every response
- Auth required
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src._shim.auth import CurrentUser
from src.api.dependencies import get_db, require_mfa_elevated, require_tenant_match
from src.api.router import router
from src.models.detection_run_models import Anomaly, DetectionRun

from tests.conftest import OTHER_TENANT_ID, TEST_TENANT_ID, TEST_USER_ID


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


def _make_run(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    status: str = "completed",
    anomaly_count: int = 0,
    record_count: int = 100,
    source_filename: str = "test.csv",
    run_label: str = "test-run",
    data_quality: dict | None = None,
    period_start: date | None = date(2024, 1, 1),
    period_end: date | None = date(2024, 3, 31),
) -> DetectionRun:
    dq = data_quality or {"no_fdb_wac": 5, "missing_pharmacy_npi": 2}
    run = DetectionRun(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        run_label=run_label,
        source_filename=source_filename,
        status=status,
        record_count=record_count,
        anomaly_count=anomaly_count,
        period_start=period_start,
        period_end=period_end,
        resolution_stats={"data_quality": dq},
        created_by=TEST_USER_ID,
    )
    db.add(run)
    db.flush()
    return run


def _make_anomaly(
    db: Session,
    tenant_id: uuid.UUID,
    run_id: uuid.UUID,
    finding_code: str = "MFR-001",
    severity: str = "high",
) -> Anomaly:
    a = Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        data_source="csv_upload",
        data_source_run_id=run_id,
        source_table="csv_upload_rows",
        source_row_id=uuid.uuid4(),
        detection_kind="rule",
        severity=severity,
        confidence=Decimal("0.9000"),
        finding_code=finding_code,
        finding_summary="Test finding",
        finding_details={},
        status="open",
    )
    db.add(a)
    db.flush()
    return a


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(db: Session) -> TestClient:
    app = build_app(db)
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests: GET /detection-runs (list)
# ---------------------------------------------------------------------------


class TestDetectionRunsList:
    def test_empty_db_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_cache_control_no_store(self, client: TestClient, db: Session) -> None:
        _make_run(db, TEST_TENANT_ID)
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        assert resp.headers.get("cache-control") == "no-store"

    def test_returns_tenant_runs(self, client: TestClient, db: Session) -> None:
        _make_run(db, TEST_TENANT_ID, run_label="run-1")
        _make_run(db, TEST_TENANT_ID, run_label="run-2")
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        data = resp.json()
        assert len(data) == 2

    def test_list_fields_present(self, client: TestClient, db: Session) -> None:
        _make_run(db, TEST_TENANT_ID, anomaly_count=5)
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        item = resp.json()[0]
        required_fields = [
            "id",
            "run_label",
            "status",
            "data_source",
            "source_filename",
            "record_count",
            "anomaly_count",
            "period_start",
            "period_end",
            "started_at",
            "completed_at",
            "failure_reason",
            "data_quality",
        ]
        for f in required_fields:
            assert f in item, f"Missing field: {f}"

    def test_data_quality_extracted_from_resolution_stats(
        self, client: TestClient, db: Session
    ) -> None:
        dq = {"no_fdb_wac": 3, "missing_pharmacy_npi": 1}
        _make_run(db, TEST_TENANT_ID, data_quality=dq)
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        assert resp.json()[0]["data_quality"] == dq

    def test_data_quality_none_when_absent(self, client: TestClient, db: Session) -> None:
        run = DetectionRun(
            id=uuid.uuid4(),
            tenant_id=TEST_TENANT_ID,
            data_source="csv_upload",
            run_label="no-dq-run",
            status="completed",
            record_count=10,
            anomaly_count=0,
            resolution_stats={},  # no data_quality key
            created_by=TEST_USER_ID,
        )
        db.add(run)
        db.flush()
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        assert resp.json()[0]["data_quality"] is None

    def test_newest_first_ordering(self, client: TestClient, db: Session) -> None:
        _make_run(db, TEST_TENANT_ID, run_label="first")
        _make_run(db, TEST_TENANT_ID, run_label="second")
        _make_run(db, TEST_TENANT_ID, run_label="third")
        resp = client.get("/api/v1/reclaimrx/detection-runs")
        items = resp.json()
        timestamps = [item["started_at"] for item in items]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_cross_tenant_isolation(self, db: Session) -> None:
        _make_run(db, TEST_TENANT_ID, run_label="tenant-a-run")
        _make_run(db, OTHER_TENANT_ID, run_label="tenant-b-run")

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.get("/api/v1/reclaimrx/detection-runs")

        data = resp.json()
        assert len(data) == 1
        assert data[0]["run_label"] == "tenant-a-run"

    def test_requires_auth(self) -> None:
        app = FastAPI()
        app.include_router(router)
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.get("/api/v1/reclaimrx/detection-runs")
        assert resp.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Tests: GET /detection-runs/{id} (detail)
# ---------------------------------------------------------------------------


class TestDetectionRunsDetail:
    def test_not_found_returns_404(self, client: TestClient) -> None:
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_cache_control_no_store(self, client: TestClient, db: Session) -> None:
        run = _make_run(db, TEST_TENANT_ID)
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")
        assert resp.headers.get("cache-control") == "no-store"

    def test_detail_fields_present(self, client: TestClient, db: Session) -> None:
        run = _make_run(db, TEST_TENANT_ID, anomaly_count=2)
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="HP-005", severity="medium")
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")
        assert resp.status_code == 200
        data = resp.json()
        base_fields = [
            "id",
            "run_label",
            "status",
            "data_source",
            "source_filename",
            "record_count",
            "anomaly_count",
            "period_start",
            "period_end",
            "started_at",
            "completed_at",
            "failure_reason",
            "data_quality",
            "per_rule_breakdown",
        ]
        for f in base_fields:
            assert f in data, f"Missing field: {f}"

    def test_per_rule_breakdown_group_by_finding_code(
        self, client: TestClient, db: Session
    ) -> None:
        run = _make_run(db, TEST_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="HP-005", severity="medium")
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")
        breakdown = resp.json()["per_rule_breakdown"]
        assert isinstance(breakdown, list)
        codes = {row["finding_code"]: row["count"] for row in breakdown}
        assert codes["MFR-001"] == 2
        assert codes["HP-005"] == 1

    def test_per_rule_breakdown_has_severity(
        self, client: TestClient, db: Session
    ) -> None:
        run = _make_run(db, TEST_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001", severity="high")
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")
        breakdown = resp.json()["per_rule_breakdown"]
        assert len(breakdown) == 1
        assert breakdown[0]["severity"] == "high"
        assert breakdown[0]["finding_code"] == "MFR-001"
        assert breakdown[0]["count"] == 1

    def test_per_rule_breakdown_empty_when_no_anomalies(
        self, client: TestClient, db: Session
    ) -> None:
        run = _make_run(db, TEST_TENANT_ID)
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")
        assert resp.json()["per_rule_breakdown"] == []

    def test_detail_cross_tenant_isolation(self, db: Session) -> None:
        """Cannot retrieve another tenant's run by ID."""
        run_b = _make_run(db, OTHER_TENANT_ID)

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.get(f"/api/v1/reclaimrx/detection-runs/{run_b.id}")

        assert resp.status_code == 404

    def test_breakdown_only_this_run_anomalies(
        self, client: TestClient, db: Session
    ) -> None:
        """Per-rule breakdown must not include anomalies from other runs."""
        run1 = _make_run(db, TEST_TENANT_ID)
        run2 = _make_run(db, TEST_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run1.id, finding_code="MFR-001")
        _make_anomaly(db, TEST_TENANT_ID, run2.id, finding_code="HP-005")
        resp = client.get(f"/api/v1/reclaimrx/detection-runs/{run1.id}")
        breakdown = resp.json()["per_rule_breakdown"]
        codes = {row["finding_code"] for row in breakdown}
        assert "MFR-001" in codes
        assert "HP-005" not in codes

    def test_breakdown_excludes_other_tenant_anomalies(self, db: Session) -> None:
        """Breakdown query must be tenant-scoped."""
        run = _make_run(db, TEST_TENANT_ID)
        _make_anomaly(db, TEST_TENANT_ID, run.id, finding_code="MFR-001")
        # Anomaly for other tenant referencing same run_id (adversarial row)
        other_anomaly = Anomaly(
            id=uuid.uuid4(),
            tenant_id=OTHER_TENANT_ID,
            data_source="csv_upload",
            data_source_run_id=run.id,
            source_table="csv_upload_rows",
            source_row_id=uuid.uuid4(),
            detection_kind="rule",
            severity="critical",
            confidence=Decimal("0.9000"),
            finding_code="ALL-001",
            finding_summary="cross-tenant test",
            finding_details={},
            status="open",
        )
        db.add(other_anomaly)
        db.flush()

        app = build_app(db, tenant_id=TEST_TENANT_ID)
        with TestClient(app, raise_server_exceptions=True) as c:
            resp = c.get(f"/api/v1/reclaimrx/detection-runs/{run.id}")

        breakdown = resp.json()["per_rule_breakdown"]
        codes = {row["finding_code"] for row in breakdown}
        assert "MFR-001" in codes
        assert "ALL-001" not in codes, "Must not include other-tenant anomalies"
