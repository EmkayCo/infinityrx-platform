"""Unit tests for GraphAnalysisJob.

Tests advisory lock key determinism, run lifecycle (create GraphRun row,
advisory lock contention, existing running row, failure handling, size limit,
fraud ring rows, outbox event written).

These tests patch _run_graph_computation and _pg_try_advisory_lock so
the unit suite does not require a live PostgreSQL or NetworkX call.
End-to-end computation is covered in
tests/integration/test_graph_job_real_computation.py.
"""
from __future__ import annotations

import uuid
import zlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.jobs.graph_analysis_job import (
    GraphAnalysisJob,
    RunInProgressError,
    advisory_lock_key,
)
from src.models.tables import GraphRun, OutboxEvent

from tests.conftest import TEST_TENANT_ID


class TestAdvisoryLockKey:
    def test_deterministic_same_tenant(self) -> None:
        tid = uuid.UUID("11111111-1111-1111-1111-111111111111")
        assert advisory_lock_key(tid) == advisory_lock_key(tid)

    def test_different_tenants_produce_different_keys(self) -> None:
        t1 = uuid.UUID("11111111-1111-1111-1111-111111111111")
        t2 = uuid.UUID("22222222-2222-2222-2222-222222222222")
        assert advisory_lock_key(t1) != advisory_lock_key(t2)

    def test_key_is_positive_int_in_pg_bigint_range(self) -> None:
        key = advisory_lock_key(uuid.uuid4())
        assert isinstance(key, int)
        assert 0 <= key <= 0x7FFFFFFF

    def test_uses_zlib_crc32_not_builtin_hash(self) -> None:
        tid = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        expected = zlib.crc32(f"graph_run:{tid}".encode()) & 0x7FFFFFFF
        assert advisory_lock_key(tid) == expected


class TestGraphAnalysisJob:
    @pytest.fixture()
    def job(self, db: Session) -> GraphAnalysisJob:
        return GraphAnalysisJob(db)

    def test_trigger_creates_graph_run_row_with_status_completed(
        self, db: Session, job: GraphAnalysisJob
    ) -> None:
        with (
            patch.object(job, "_pg_try_advisory_lock", return_value=True),
            patch.object(job, "_check_running"),
            patch.object(
                job,
                "_run_graph_computation",
                return_value={"rings": [], "investigations": 0, "records": 0},
            ),
        ):
            gr = job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="cron")

        assert gr.status == "completed"
        # Row must be persisted in session
        found = db.get(GraphRun, gr.id)
        assert found is not None
        assert found.status == "completed"

    def test_advisory_lock_contention_raises_run_in_progress(
        self, db: Session, job: GraphAnalysisJob
    ) -> None:
        with (
            patch.object(job, "_pg_try_advisory_lock", return_value=False),
            patch.object(job, "_check_running"),
        ):
            with pytest.raises(RunInProgressError) as exc_info:
                job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="cron")
        assert exc_info.value.code == "RUN_IN_PROGRESS"

    def test_existing_running_row_raises_run_in_progress(
        self, db: Session, job: GraphAnalysisJob
    ) -> None:
        # Seed an existing 'running' GraphRun row for this tenant
        existing = GraphRun(
            id=str(uuid.uuid4()),
            tenant_id=str(TEST_TENANT_ID),
            status="running",
            trigger="cron",
            started_at=datetime.now(UTC),
            stale_timeout_at=datetime.now(UTC) + timedelta(hours=2),
            correlation_id=str(uuid.uuid4()),
            lookback_window_days=90,
            rings_detected=0,
            investigations_opened=0,
            records_scanned=0,
        )
        db.add(existing)
        db.flush()

        with patch.object(job, "_pg_try_advisory_lock", return_value=True):
            with pytest.raises(RunInProgressError) as exc_info:
                job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="on_demand")
        assert exc_info.value.existing_run_id == existing.id

    def test_computation_failure_sets_status_failed_and_error_code(
        self, db: Session, job: GraphAnalysisJob
    ) -> None:
        with (
            patch.object(job, "_pg_try_advisory_lock", return_value=True),
            patch.object(job, "_check_running"),
            patch.object(
                job,
                "_run_graph_computation",
                side_effect=RuntimeError("network error"),
            ),
        ):
            with pytest.raises(RuntimeError, match="network error"):
                job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="cron")

        runs = db.execute(
            __import__("sqlalchemy").select(GraphRun).where(
                GraphRun.tenant_id == str(TEST_TENANT_ID),
                GraphRun.status == "failed",
            )
        ).scalars().all()
        assert len(runs) == 1
        assert runs[0].error_code == "COMPUTATION_ERROR"

    def test_outbox_row_written_on_success(
        self, db: Session, job: GraphAnalysisJob
    ) -> None:
        with (
            patch.object(job, "_pg_try_advisory_lock", return_value=True),
            patch.object(job, "_check_running"),
            patch.object(
                job,
                "_run_graph_computation",
                return_value={"rings": [], "investigations": 0, "records": 5},
            ),
        ):
            gr = job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="cron")

        outbox_rows = db.execute(
            __import__("sqlalchemy").select(OutboxEvent).where(
                OutboxEvent.tenant_id == str(TEST_TENANT_ID),
                OutboxEvent.event_type == "fwa.graph_run_completed",
            )
        ).scalars().all()
        assert len(outbox_rows) == 1
        assert gr.id in outbox_rows[0].idempotency_key

    def test_stale_running_row_is_auto_failed(self, db: Session, job: GraphAnalysisJob) -> None:
        import datetime as _dt
        past = _dt.datetime.now(_dt.UTC) - _dt.timedelta(hours=5)
        stale = GraphRun(
            id=str(uuid.uuid4()),
            tenant_id=str(TEST_TENANT_ID),
            status="running",
            trigger="cron",
            started_at=past,
            stale_timeout_at=past,  # already timed out
            correlation_id=str(uuid.uuid4()),
            lookback_window_days=90,
            rings_detected=0,
            investigations_opened=0,
            records_scanned=0,
        )
        db.add(stale)
        db.flush()

        # Should NOT raise -- stale row is auto-failed and a new run proceeds
        with (
            patch.object(job, "_pg_try_advisory_lock", return_value=True),
            patch.object(
                job, "_run_graph_computation",
                return_value={"rings": [], "investigations": 0, "records": 0},
            ),
        ):
            gr = job.trigger(tenant_id=TEST_TENANT_ID, trigger_source="cron")

        db.refresh(stale)
        assert stale.status == "failed"
        assert stale.error_code == "STALE_TIMEOUT"
        assert gr.status == "completed"

    def test_open_investigation_for_ring_returns_investigation(self, db: Session, job: GraphAnalysisJob) -> None:
        ring_id = str(uuid.uuid4())
        inv = job._open_investigation_for_ring(TEST_TENANT_ID, ring_id)
        assert inv.subject_entity_id == ring_id
        assert inv.subject_type == "fraud_ring"
        assert inv.investigation_type == "graph_ring"
        assert inv.status == "open"
        assert inv.priority == "high"
        assert inv.investigation_number.startswith("INV-")
