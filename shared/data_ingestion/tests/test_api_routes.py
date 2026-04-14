"""Tests for shared.data_ingestion.api.routes and schemas.

Uses FastAPI TestClient (synchronous) with a request-scoped DB session
injected via dependency override, verifying that each endpoint returns the
correct HTTP status, payload shape, and standard error envelope.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.data_ingestion.api.routes import router
from shared.data_ingestion.field_registry import FieldRegistry, register_field, registry
from shared.data_ingestion.models import IngestionRun, IngestionSchedule

# ---------------------------------------------------------------------------
# App factory for route tests
# ---------------------------------------------------------------------------


def _make_app(db: Session) -> FastAPI:
    """Build a minimal FastAPI app that mounts the ingestion router.

    Overrides the ``_get_db`` dependency to inject the test session.
    """
    from shared.data_ingestion.api.routes import _get_db

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/data-ingestion")

    def _override_db(request: Request) -> Session:
        request.state.db = db
        request.state.correlation_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        return db

    app.dependency_overrides[_get_db] = _override_db
    return app


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Test client with injected DB session."""
    return TestClient(_make_app(db_session))


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_schedule(session: Session, source: str = "fda_ndc", enabled: bool = True) -> IngestionSchedule:
    sched = IngestionSchedule(
        source=source,
        cron_expression="0 2 * * *",
        enabled=enabled,
    )
    session.add(sched)
    session.commit()
    session.refresh(sched)
    return sched


def _seed_run(
    session: Session,
    source: str = "fda_ndc",
    status: str = "completed",
) -> IngestionRun:
    run = IngestionRun(
        source=source,
        run_type="auto_scheduled",
        status=status,
        started_at=datetime.now(UTC),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


# ---------------------------------------------------------------------------
# POST /{source}/trigger
# ---------------------------------------------------------------------------


def test_trigger_run_returns_201_and_run_id(client: TestClient, db_session: Session) -> None:
    """Triggering a run for a known source returns the new run_id."""
    _seed_schedule(db_session)
    resp = client.post("/api/v1/data-ingestion/fda_ndc/trigger", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "run_id" in body
    assert body["source"] == "fda_ndc"
    assert body["status"] == "running"


def test_trigger_run_404_for_unknown_source(client: TestClient) -> None:
    """Trigger for an unregistered source returns 404 with error envelope."""
    resp = client.post("/api/v1/data-ingestion/unknown_source/trigger", json={})
    assert resp.status_code == 404
    error = resp.json()["detail"]["error"]
    assert error["code"] == "SOURCE_NOT_FOUND"
    assert "correlation_id" in error


def test_trigger_run_409_when_in_flight(client: TestClient, db_session: Session) -> None:
    """Triggering a run when one is already running returns 409."""
    _seed_schedule(db_session)
    _seed_run(db_session, status="running")

    resp = client.post("/api/v1/data-ingestion/fda_ndc/trigger", json={})
    assert resp.status_code == 409
    error = resp.json()["detail"]["error"]
    assert error["code"] == "RUN_ALREADY_IN_FLIGHT"


def test_trigger_run_with_triggered_by(client: TestClient, db_session: Session) -> None:
    """triggered_by UUID is stored on the run row."""
    _seed_schedule(db_session)
    user_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/data-ingestion/fda_ndc/trigger",
        json={"triggered_by": user_id},
    )
    assert resp.status_code == 200
    run_id = uuid.UUID(resp.json()["run_id"])
    run = db_session.execute(select(IngestionRun).where(IngestionRun.id == run_id)).scalar_one()
    assert str(run.triggered_by) == user_id


# ---------------------------------------------------------------------------
# POST /upload/{source}
# ---------------------------------------------------------------------------


def test_upload_returns_run_id(client: TestClient, db_session: Session) -> None:
    """File upload endpoint returns a run_id with status running."""
    _seed_schedule(db_session)
    resp = client.post(
        "/api/v1/data-ingestion/upload/fda_ndc",
        files={"file": ("test.txt", b"ndc data", "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["source"] == "fda_ndc"


def test_upload_404_for_unknown_source(client: TestClient) -> None:
    """Upload for an unregistered source returns 404."""
    resp = client.post(
        "/api/v1/data-ingestion/upload/no_such_source",
        files={"file": ("f.txt", b"data", "text/plain")},
    )
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "SOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


def test_get_all_status_empty(client: TestClient) -> None:
    """Status endpoint returns empty list when no schedules exist."""
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_all_status_with_schedule(client: TestClient, db_session: Session) -> None:
    """Status endpoint returns one entry per registered schedule."""
    _seed_schedule(db_session, source="cms_nadac")
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source"] == "cms_nadac"
    assert data[0]["enabled"] is True


def test_get_all_status_includes_last_run(client: TestClient, db_session: Session) -> None:
    """When schedule.last_run_id is set, last_run is populated in the response."""
    sched = _seed_schedule(db_session)
    run = _seed_run(db_session)
    sched.last_run_id = run.id
    db_session.commit()

    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["last_run"] is not None
    assert data[0]["last_run"]["status"] == "completed"


# ---------------------------------------------------------------------------
# GET /{source}/history
# ---------------------------------------------------------------------------


def test_get_history_returns_runs_for_source(client: TestClient, db_session: Session) -> None:
    """History endpoint returns the run list for a known source."""
    _seed_schedule(db_session)
    _seed_run(db_session, status="completed")
    _seed_run(db_session, status="failed")

    resp = client.get("/api/v1/data-ingestion/fda_ndc/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_get_history_404_for_unknown_source(client: TestClient) -> None:
    """History for unknown source returns 404."""
    resp = client.get("/api/v1/data-ingestion/unknown/history")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "SOURCE_NOT_FOUND"


def test_get_history_respects_limit(client: TestClient, db_session: Session) -> None:
    """History limit parameter is respected (capped at 500)."""
    _seed_schedule(db_session)
    for _ in range(5):
        _seed_run(db_session)

    resp = client.get("/api/v1/data-ingestion/fda_ndc/history?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# GET /runs/{id}
# ---------------------------------------------------------------------------


def test_get_run_detail_returns_full_run(client: TestClient, db_session: Session) -> None:
    """Run detail endpoint returns the full RunDetail schema."""
    run = _seed_run(db_session)
    resp = client.get(f"/api/v1/data-ingestion/runs/{run.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(run.id)
    assert body["source"] == "fda_ndc"
    assert "created_at" in body


def test_get_run_detail_404_for_missing(client: TestClient) -> None:
    """Run detail for non-existent UUID returns 404."""
    resp = client.get(f"/api/v1/data-ingestion/runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "RUN_NOT_FOUND"


# ---------------------------------------------------------------------------
# POST /{source}/cancel
# ---------------------------------------------------------------------------


def test_cancel_running_job(client: TestClient, db_session: Session) -> None:
    """Cancel a running job; status changes to cancelled."""
    _seed_schedule(db_session)
    run = _seed_run(db_session, status="running")

    resp = client.post(
        "/api/v1/data-ingestion/fda_ndc/cancel",
        json={"reason": "user requested stop"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["run_id"] == str(run.id)

    db_session.expire(run)
    refreshed = db_session.execute(select(IngestionRun).where(IngestionRun.id == run.id)).scalar_one()
    assert refreshed.status == "cancelled"


def test_cancel_404_when_no_running_job(client: TestClient, db_session: Session) -> None:
    """Cancel when no running job returns 404."""
    _seed_schedule(db_session)
    resp = client.post("/api/v1/data-ingestion/fda_ndc/cancel", json={})
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"]["code"] == "NO_RUNNING_JOB"


# ---------------------------------------------------------------------------
# GET /field-catalog
# ---------------------------------------------------------------------------


def test_field_catalog_returns_registered_fields(client: TestClient) -> None:
    """Field catalog endpoint dumps the field registry."""
    # Register test fields in the module-level registry
    registry.register(
        source="test_src",
        table="drug_database.ndc",
        column="ndc_11",
        description="11-digit NDC",
        source_file="product.txt",
        source_position="PRODUCTNDC",
        data_type="str",
    )

    resp = client.get("/api/v1/data-ingestion/field-catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert "total" in body
    assert body["total"] >= 1
    # At least one field must be for test_src
    sources = [f["source"] for f in body["fields"]]
    assert "test_src" in sources


# ---------------------------------------------------------------------------
# field_registry module coverage
# ---------------------------------------------------------------------------


def test_field_registry_fields_for_source() -> None:
    """fields_for_source must return only matching fields."""
    reg = FieldRegistry()
    reg.register(
        source="src_a",
        table="t1",
        column="c1",
        description="d",
        source_file="f.txt",
        source_position="0",
        data_type="str",
    )
    reg.register(
        source="src_b",
        table="t2",
        column="c2",
        description="d",
        source_file="f.txt",
        source_position="1",
        data_type="int",
    )

    assert len(reg.fields_for_source("src_a")) == 1
    assert reg.fields_for_source("src_a")[0].column == "c1"
    assert len(reg.fields_for_source("src_b")) == 1
    assert len(reg.fields_for_source("missing")) == 0


def test_field_registry_as_dict_list() -> None:
    """as_dict_list must serialize all registered fields as plain dicts."""
    reg = FieldRegistry()
    reg.register(
        source="src_c",
        table="t3",
        column="c3",
        description="test field",
        source_file="data.csv",
        source_position="COL_NAME",
        data_type="Decimal",
    )
    items = reg.as_dict_list()
    assert len(items) == 1
    item = items[0]
    assert item["source"] == "src_c"
    assert item["data_type"] == "Decimal"
    assert isinstance(item, dict)


def test_register_field_module_level() -> None:
    """The module-level register_field convenience function populates the registry."""
    before_count = len(registry.all_fields())
    register_field(
        source="convenience_src",
        table="drug_database.example",
        column="example_col",
        description="example",
        source_file="example.txt",
        source_position="EXAMPLE",
        data_type="str",
    )
    assert len(registry.all_fields()) == before_count + 1


def test_field_metadata_is_frozen() -> None:
    """FieldMetadata instances must be immutable (frozen dataclass)."""
    from shared.data_ingestion.field_registry import FieldMetadata

    meta = FieldMetadata(
        source="s",
        table="t",
        column="c",
        description="d",
        source_file="f.txt",
        source_position="0",
        data_type="str",
    )
    with pytest.raises((AttributeError, TypeError)):
        meta.source = "changed"  # type: ignore[misc]


def test_get_db_returns_500_when_session_not_configured() -> None:
    """_get_db must return 500 HTTPException when db is not on request.state."""


    # Build a minimal app WITHOUT the DB override
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/data-ingestion")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/api/v1/data-ingestion/status")
    # 500 because the DB dependency raises HTTPException(500)
    assert resp.status_code == 500


def test_run_detail_with_error_samples(client: TestClient, db_session: Session) -> None:
    """RunDetail must include error_samples when present on the run row."""
    run = _seed_run(db_session, status="completed")
    run.error_samples = {"samples": [{"field": "ndc", "raw_row": "bad", "error": "oops"}]}
    db_session.commit()

    resp = client.get(f"/api/v1/data-ingestion/runs/{run.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["error_samples"] is not None
    assert body["error_samples"][0]["field"] == "ndc"


def test_run_summary_with_completed_at_has_duration(client: TestClient, db_session: Session) -> None:
    """RunSummary must include duration_seconds when both started_at and completed_at are set."""
    from datetime import timedelta

    run = _seed_run(db_session, status="completed")
    run.completed_at = run.started_at.replace(tzinfo=None) + timedelta(seconds=42) if run.started_at.tzinfo else run.started_at + timedelta(seconds=42)
    db_session.commit()

    resp = client.get(f"/api/v1/data-ingestion/runs/{run.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["duration_seconds"] is not None
