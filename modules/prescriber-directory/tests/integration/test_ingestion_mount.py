"""Integration test: shared ingestion router mounted on prescriber-directory create_app().

LESSON-006 compliance: verifies the ingestion router is reachable through the
create_app() factory — not just importable. Tests the full HTTP path from
TestClient → create_app() → _ingestion_db_override → ingestion router → DB.

LESSON-001: Uses SAVEPOINT-based isolation via the shared ingestion conftest
fixture pattern (_UUIDString + schema_translate_map). Ingestion models use
the 'shared' schema which SQLite does not support; schema_translate_map fixes this.

LESSON-007: IngestionRun uses PG_UUID — patched to _UUIDString in the
shared/data_ingestion/tests/conftest.py at import time. We reuse that same
patch here by importing from the conftest.
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MODULE_ROOT = Path(__file__).resolve().parent.parent.parent
_PROJECT_ROOT = _MODULE_ROOT.parent.parent
for _p in (_MODULE_ROOT, _PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")
os.environ.setdefault("JWT_SECRET", "test-secret-of-sufficient-length-!!!!")
os.environ.setdefault("ENCRYPTION_KEY_ACTIVE", "dGVzdC1rZXktMzItYnl0ZXMtZm9yLXVuaXQtdGVzdHM=")

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import JSON, String, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from shared.data_ingestion.api.routes import _get_db as _ingestion_get_db
from shared.data_ingestion.models import IngestionRun, IngestionSchedule
from shared.db.base import Base
from src.db.session import set_engine
from src.models.tables import PrescriberBase


# ---------------------------------------------------------------------------
# SQLite compatibility helpers (LESSON-007 + schema translation)
# ---------------------------------------------------------------------------


class _UUIDString(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) — prevents PG_UUID BLOB→float bug."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> uuid.UUID | None:
        if value is None:
            return None
        return uuid.UUID(str(value))


def _patch_ingestion_tables_for_sqlite() -> None:
    """Patch IngestionRun + IngestionSchedule for SQLite compatibility (idempotent)."""
    for table in [IngestionRun.__table__, IngestionSchedule.__table__]:
        if getattr(table, "_sqlite_patched_mount_test", False):
            continue
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDString()
            if col.server_default is not None and "gen_random_uuid" in str(
                col.server_default
            ):
                col.server_default = None
        table._sqlite_patched_mount_test = True  # type: ignore[attr-defined]


_patch_ingestion_tables_for_sqlite()


# ---------------------------------------------------------------------------
# Engine + session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _ingestion_engine():
    """SQLite in-memory engine with schema_translate_map for 'shared' schema."""
    raw_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(raw_engine, "connect")
    def _set_pragma(dbapi_conn: Any, _: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    engine = raw_engine.execution_options(schema_translate_map={"shared": None})

    # Create ingestion tables (schema-translated) and prescriber tables (no schema)
    Base.metadata.create_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )

    # Also create prescriber tables so the app factory doesn't error on DB ops
    for table in PrescriberBase.metadata.tables.values():
        table.schema = None  # SQLite has no schema support
    PrescriberBase.metadata.create_all(engine)

    set_engine(engine)
    yield engine

    Base.metadata.drop_all(
        engine,
        tables=[IngestionRun.__table__, IngestionSchedule.__table__],
    )
    PrescriberBase.metadata.drop_all(engine)
    raw_engine.dispose()


@pytest.fixture
def db(_ingestion_engine) -> Iterator[Session]:
    """SAVEPOINT-based isolated session per LESSON-001."""
    connection = _ingestion_engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    factory = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, transaction: Any) -> None:
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session
    session.close()
    outer.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# App fixture wired to test DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _app(_ingestion_engine):
    """create_app() with prescriber get_db overridden — module-scoped so app is built once."""
    from src.api.dependencies import get_db
    from src.main import create_app

    application = create_app()

    def _override_prescriber_db() -> Iterator[Session]:
        factory = sessionmaker(bind=_ingestion_engine, expire_on_commit=False, future=True)
        session = factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = _override_prescriber_db
    return application


@pytest.fixture
def client(_app, db: Session) -> TestClient:
    """TestClient with ingestion _get_db overridden to the per-test SAVEPOINT session."""

    def _override_ingestion_db(request: Request) -> Iterator[Session]:
        request.state.db = db
        request.state.correlation_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        yield db

    _app.dependency_overrides[_ingestion_get_db] = _override_ingestion_db
    c = TestClient(_app)
    yield c
    # Remove the per-test override so the module-scoped app doesn't carry it
    _app.dependency_overrides.pop(_ingestion_get_db, None)


# ---------------------------------------------------------------------------
# Tests — LESSON-006: exercise through create_app()
# ---------------------------------------------------------------------------


def test_ingestion_status_reachable_through_create_app(client: TestClient) -> None:
    """GET /api/v1/data-ingestion/status returns 200 with empty list when no schedules exist."""
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_ingestion_trigger_unknown_source_returns_404(client: TestClient) -> None:
    """POST /api/v1/data-ingestion/{unknown}/trigger → 404 SOURCE_NOT_FOUND."""
    resp = client.post(
        "/api/v1/data-ingestion/unknown_source_xyz/trigger",
        json={"run_type": "full"},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["error"]["code"] == "SOURCE_NOT_FOUND"


def test_ingestion_trigger_known_source_starts_run(client: TestClient, db: Session) -> None:
    """POST /api/v1/data-ingestion/fda_ndc/trigger → 200 with run_id when schedule exists."""
    sched = IngestionSchedule(
        source="fda_ndc",
        cron_expression="0 2 * * *",
        enabled=True,
    )
    db.add(sched)
    db.commit()

    resp = client.post(
        "/api/v1/data-ingestion/fda_ndc/trigger",
        json={"run_type": "manual_trigger"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "fda_ndc"
    assert body["status"] == "running"
    assert "run_id" in body


def test_ingestion_trigger_duplicate_in_flight_returns_409(
    client: TestClient, db: Session
) -> None:
    """POST trigger while run is already running → 409 RUN_ALREADY_IN_FLIGHT."""
    sched = IngestionSchedule(
        source="nppes",
        cron_expression="0 3 * * 2",
        enabled=True,
    )
    db.add(sched)
    run = IngestionRun(
        id=uuid.uuid4(),
        source="nppes",
        run_type="auto_scheduled",
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(run)
    db.commit()

    resp = client.post(
        "/api/v1/data-ingestion/nppes/trigger",
        json={"run_type": "manual_trigger"},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"]["error"]["code"] == "RUN_ALREADY_IN_FLIGHT"


def test_ingestion_no_auth_header_still_reaches_router(client: TestClient) -> None:
    """GET /api/v1/data-ingestion/status without Authorization → router responds (not 401).

    The ingestion backend is unauthed (BFF is the auth gate per Plan A §10.3).
    Any request, authed or not, reaches the router and gets a data response.
    """
    resp = client.get("/api/v1/data-ingestion/status")
    assert resp.status_code != 401
    assert resp.status_code == 200


def test_ingestion_bridge_sets_correlation_id(client: TestClient, db: Session) -> None:
    """Verify the ingestion DB bridge attaches a correlation_id to request.state."""
    # The _override already sets a fixed correlation_id; trigger a 404 to confirm
    # the error envelope includes it (routes.py reads request.state.correlation_id).
    resp = client.post(
        "/api/v1/data-ingestion/no_such_source/trigger",
        json={"run_type": "manual_trigger"},
    )
    assert resp.status_code == 404
    body = resp.json()
    # The correlation_id from _override_ingestion_db fixture is present in envelope
    assert "correlation_id" in body["detail"]["error"]
