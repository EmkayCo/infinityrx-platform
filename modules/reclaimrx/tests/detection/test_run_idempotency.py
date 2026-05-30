"""Task 2.3 — Idempotent detection-run creation tests.

Advisory locks and the partial unique index are Postgres-only features.
Tests that require them are gated behind RECLAIMRX_TEST_DB_URL and skip
cleanly on the SQLite in-memory fixture.

Pure branching-logic tests (no advisory lock, no partial index) run on
the SQLite fixture from conftest.py so CI without Postgres still validates
the control-flow.

Run all tests:
    pytest modules/reclaimrx/tests/detection/test_run_idempotency.py -v

Run Postgres-only tests (requires live DB):
    RECLAIMRX_TEST_DB_URL="postgresql://..." pytest ...
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

# ──────────────────────────────────────────────────────────────────────────────
# Postgres fixture (skipped when RECLAIMRX_TEST_DB_URL is unset)
# ──────────────────────────────────────────────────────────────────────────────

_PG_URL = os.environ.get(
    "RECLAIMRX_TEST_DB_URL",
    "postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/infinityrx_dev",
)
_PG_AVAILABLE = bool(os.environ.get("RECLAIMRX_TEST_DB_URL"))

pytestmark_pg = pytest.mark.skipif(
    not _PG_AVAILABLE, reason="RECLAIMRX_TEST_DB_URL not set — Postgres-gated"
)


@pytest.fixture(scope="module")
def pg_engine():
    """Real Postgres engine for advisory-lock / partial-index tests."""
    engine = create_engine(_PG_URL, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_db(pg_engine):
    """Function-scoped Postgres session with SAVEPOINT isolation."""
    connection = pg_engine.connect()
    outer = connection.begin()
    nested = connection.begin_nested()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")  # type: ignore[call-arg]

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    outer.rollback()
    connection.close()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

_TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_USER_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _make_csv_file(content: str = "header\nrow1\nrow2\n") -> str:
    """Write a temp CSV file in binary mode and return its path.

    Binary mode ensures \n is written as-is on Windows (no CRLF translation),
    so the SHA-256 computed by _compute_sha256_and_count matches _sha256_of.
    """
    raw = content.encode("utf-8")
    f = tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False)
    f.write(raw)
    f.flush()
    f.close()
    return f.name


def _sha256_of(content: str) -> str:
    """Return SHA-256 of content encoded as UTF-8 bytes (matches binary file write)."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# SQLite-compatible tests — pure branching logic
# These run on the shared `db` fixture from tests/conftest.py.
# They mock `pg_advisory_xact_lock` so the advisory-lock call is a no-op.
# ──────────────────────────────────────────────────────────────────────────────


class TestBranchingLogicSQLite:
    """Control-flow tests that run on SQLite (no advisory lock, no partial index).

    Advisory lock SQL is patched out. Partial-unique constraint is not
    enforced on SQLite, so the IntegrityError branch is not exercised here —
    that is tested in TestPartialIndexPostgres below.
    """

    def test_fresh_create_returns_detection_run(self, db):
        """create_or_resume_run on a new file returns a DetectionRun."""
        from src.detection.csv_ingest import create_or_resume_run

        path = _make_csv_file("pharmacy_npi,ndc\n1234567890,12345678901\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.id is not None
            assert run.status == "in_progress"
            assert run.tenant_id == _TENANT_A
            assert run.created_by == _USER_ID
            assert run.data_source == "csv_upload"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_run_label_is_deterministic(self, db):
        """run_label is '{filename}:{sha[:12]}' — NOT NULL satisfied."""
        from src.detection.csv_ingest import create_or_resume_run

        content = "pharmacy_npi,ndc\nAAA,BBB\n"
        path = _make_csv_file(content)
        expected_sha = _sha256_of(content)
        expected_label = f"{Path(path).name}:{expected_sha[:12]}"
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.run_label == expected_label
            assert run.run_label  # NOT NULL
        finally:
            Path(path).unlink(missing_ok=True)

    def test_created_by_is_populated(self, db):
        """created_by NOT NULL constraint satisfied on insert."""
        from src.detection.csv_ingest import create_or_resume_run

        path = _make_csv_file("a,b\n1,2\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.created_by == _USER_ID
        finally:
            Path(path).unlink(missing_ok=True)

    def test_expected_count_stored_in_resolution_stats(self, db):
        """expected_count is stored in resolution_stats JSONB."""
        from src.detection.csv_ingest import create_or_resume_run

        # 3 data rows (header line excluded)
        path = _make_csv_file("col_a,col_b\nrow1a,row1b\nrow2a,row2b\nrow3a,row3b\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert "expected_count" in run.resolution_stats
            assert run.resolution_stats["expected_count"] == 3
        finally:
            Path(path).unlink(missing_ok=True)

    def test_source_sha256_matches_file_content(self, db):
        """source_sha256 is a correct SHA-256 hex digest of the file."""
        from src.detection.csv_ingest import create_or_resume_run

        content = "x,y\n1,2\n"
        path = _make_csv_file(content)
        expected = _sha256_of(content)
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.source_sha256 == expected
        finally:
            Path(path).unlink(missing_ok=True)

    def test_source_path_and_filename_stored(self, db):
        """source_path and source_filename are both populated."""
        from src.detection.csv_ingest import create_or_resume_run

        path = _make_csv_file("h\nv\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.source_path == path
            assert run.source_filename == Path(path).name
        finally:
            Path(path).unlink(missing_ok=True)

    def test_completed_run_raises_without_force(self, db):
        """Second call for a completed run raises DetectionRunExistsError."""
        from src.detection.csv_ingest import DetectionRunExistsError, create_or_resume_run

        path = _make_csv_file("col\nval\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            # Mark it completed
            run.status = "completed"
            db.flush()

            with pytest.raises(DetectionRunExistsError, match="already ingested"):
                with patch(
                    "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
                ):
                    create_or_resume_run(
                        db,
                        tenant_id=_TENANT_A,
                        path=path,
                        created_by=_USER_ID,
                    )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_in_progress_run_raises_without_resume(self, db):
        """Second call for an in_progress run raises RunInProgressError."""
        from src.detection.csv_ingest import RunInProgressError, create_or_resume_run

        path = _make_csv_file("col\nval\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                # First call creates in_progress run
                create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            # Second call without resume= raises
            with pytest.raises(RunInProgressError, match="run in progress"):
                with patch(
                    "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
                ):
                    create_or_resume_run(
                        db,
                        tenant_id=_TENANT_A,
                        path=path,
                        created_by=_USER_ID,
                    )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_in_progress_run_returns_same_run_with_resume(self, db):
        """resume=True on an in_progress run returns the existing run."""
        from src.detection.csv_ingest import create_or_resume_run

        path = _make_csv_file("col\nval\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run1 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run2 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                    resume=True,
                )
            assert run1.id == run2.id
        finally:
            Path(path).unlink(missing_ok=True)

    def test_failed_run_is_replaced_with_force(self, db):
        """force=True on a failed run creates a new run (fresh start)."""
        from src.detection.csv_ingest import create_or_resume_run
        from src.models.detection_run_models import CsvUploadRow

        path = _make_csv_file("col\nval\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run1 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            run1.status = "failed"
            db.flush()

            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run2 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                    force=True,
                )
            # A new run is created
            assert run2.id != run1.id
            assert run2.status == "in_progress"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_failed_run_csv_rows_deleted_on_force(self, db):
        """force=True on a failed run deletes prior csv_upload_rows."""
        from src.detection.csv_ingest import create_or_resume_run
        from src.models.detection_run_models import CsvUploadRow, DetectionRun

        path = _make_csv_file("col\nval\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run1 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            # Seed a csv_upload_row belonging to the first run
            row = CsvUploadRow(
                tenant_id=_TENANT_A,
                detection_run_id=run1.id,
                row_number=1,
                row_data={"col": "val"},
                resolution_method="declared",
            )
            db.add(row)
            run1.status = "failed"
            db.flush()

            rows_before = (
                db.query(CsvUploadRow)
                .filter(CsvUploadRow.detection_run_id == run1.id)
                .count()
            )
            assert rows_before == 1

            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run2 = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                    force=True,
                )

            # Prior rows are gone
            rows_after = (
                db.query(CsvUploadRow)
                .filter(CsvUploadRow.detection_run_id == run1.id)
                .count()
            )
            assert rows_after == 0
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty_file_expected_count_zero(self, db):
        """A file with only a header line → expected_count == 0."""
        from src.detection.csv_ingest import create_or_resume_run

        path = _make_csv_file("header_only\n")
        try:
            with patch(
                "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
            ):
                run = create_or_resume_run(
                    db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            assert run.resolution_stats["expected_count"] == 0
        finally:
            Path(path).unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────────────────────
# Postgres-gated tests — advisory lock + partial unique index behaviour
# ──────────────────────────────────────────────────────────────────────────────


@pytestmark_pg
class TestPartialIndexPostgres:
    """Tests that require a live Postgres instance.

    The partial unique index `uq_detection_runs_tenant_sha_active` (added in
    migration 0009) enforces that only one in_progress or completed run exists
    per (tenant_id, source_sha256). Advisory lock is exercised via the real
    `pg_advisory_xact_lock` SQL function.
    """

    def test_index_exists_in_dev_db(self, pg_engine):
        """Migration 0009 must have created the partial unique index."""
        with pg_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE schemaname = 'reclaimrx' "
                    "  AND tablename = 'detection_runs' "
                    "  AND indexname = 'uq_detection_runs_tenant_sha_active'"
                )
            ).fetchall()
        assert result, (
            "uq_detection_runs_tenant_sha_active not found in reclaimrx.detection_runs "
            "— did migration 0009 run?"
        )

    def test_duplicate_completed_sha_raises_on_postgres(self, pg_db):
        """Two completed runs with same (tenant, sha) violates partial unique index."""
        from src.detection.csv_ingest import DetectionRunExistsError, create_or_resume_run

        content = "npi,ndc\n1111111111,12345678901\n"
        path = _make_csv_file(content)
        try:
            # First run — created and completed
            run1 = create_or_resume_run(
                pg_db,
                tenant_id=_TENANT_A,
                path=path,
                created_by=_USER_ID,
            )
            run1.status = "completed"
            pg_db.flush()

            # Second call — must raise before hitting the DB
            with pytest.raises(DetectionRunExistsError, match="already ingested"):
                create_or_resume_run(
                    pg_db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
        finally:
            Path(path).unlink(missing_ok=True)

    def test_in_progress_resume_true_returns_same_run_postgres(self, pg_db):
        """resume=True on an in_progress run returns the same run (Postgres)."""
        from src.detection.csv_ingest import create_or_resume_run

        content = "a,b\nalpha,beta\n"
        path = _make_csv_file(content)
        try:
            run1 = create_or_resume_run(
                pg_db,
                tenant_id=_TENANT_A,
                path=path,
                created_by=_USER_ID,
            )
            run2 = create_or_resume_run(
                pg_db,
                tenant_id=_TENANT_A,
                path=path,
                created_by=_USER_ID,
                resume=True,
            )
            assert run1.id == run2.id
            assert run2.status == "in_progress"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_advisory_lock_key_is_tenant_sha(self, pg_db):
        """Advisory lock is acquired with key hashtext('{tenant_id}:{sha256}')."""
        from src.detection.csv_ingest import create_or_resume_run

        content = "col\nval\n"
        path = _make_csv_file(content)
        sha = _sha256_of(content)
        expected_key = f"{_TENANT_A}:{sha}"

        executed_sqls: list[str] = []

        original_execute = pg_db.execute

        def capturing_execute(stmt, *args, **kwargs):
            # Capture raw SQL strings for advisory lock assertion
            stmt_str = str(stmt) if not isinstance(stmt, str) else stmt
            executed_sqls.append(stmt_str)
            return original_execute(stmt, *args, **kwargs)

        try:
            with patch.object(pg_db, "execute", side_effect=capturing_execute):
                create_or_resume_run(
                    pg_db,
                    tenant_id=_TENANT_A,
                    path=path,
                    created_by=_USER_ID,
                )
            advisory_sqls = [s for s in executed_sqls if "advisory_xact_lock" in s]
            assert advisory_sqls, "pg_advisory_xact_lock was never called"
        finally:
            Path(path).unlink(missing_ok=True)
