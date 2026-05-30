"""Task 4.2 - detect CLI with its own RLS-enforced sync session.

TDD: RED tests written first; implementation in src/cli/detect.py.

Contract
--------
run_detect(file, *, tenant, created_by, engine=None, resume=False, force=False)
    Phase 1: register_rule_types(db); register_rule_instances(db, tenant, cols, created_by)
    Phase 2: create_or_resume_run + load_csv
    Phase 3: run_detection  [enforces full-coverage gate]
    Phase 4: build_summary  -> print(format_summary(summary))

    On exception: mark run status='failed' + failure_reason in a SEPARATE transaction
                  then re-raise / exit non-zero.

tenant_txn(engine, tenant_id) context manager
    - Begins a transaction via connection.begin()
    - SET LOCAL app.current_tenant_id = '<tenant_id>'  (GUC that RLS reads)
    - Sets shared.db.tenant_context current_tenant_id contextvar (belt-and-suspenders)
    - Yields a Session bound to that connection
    - Commits on clean exit; rollback on exception

RLS isolation (Postgres-gated, RECLAIMRX_TEST_DB_URL env var):
    - The CLI engine MUST use ifx_dev_app role (non-BYPASSRLS)
    - SET LOCAL app.current_tenant_id = TENANT_B  -> sees 0 anomaly rows
    - GUC unset (empty string / NULL)            -> sees 0 anomaly rows
    - Proves RLS enforces at the DB layer, not just the ORM filter.

All Postgres-gated assertions are clearly marked with the
``reclaimrx_pg`` pytest mark. They are skipped unless
``RECLAIMRX_TEST_DB_URL`` is set in the environment.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import JSON, String, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeDecorator

# ---------------------------------------------------------------------------
# Marks
# ---------------------------------------------------------------------------

reclaimrx_pg = pytest.mark.skipif(
    not os.environ.get("RECLAIMRX_TEST_DB_URL"),
    reason=(
        "RECLAIMRX_TEST_DB_URL not set - Postgres required for real RLS/GUC tests. "
        "Set RECLAIMRX_TEST_DB_URL to a Postgres DSN using ifx_dev_app role to run."
    ),
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_TENANT_B = uuid.UUID("22222222-2222-2222-2222-222222222222")
_SYS_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_FIXTURE_CSV = (
    Path(__file__).resolve().parent / "fixtures" / "sample_claims.csv"
)


# ---------------------------------------------------------------------------
# SQLite engine helper (isolated per test, models imported + types swapped)
# ---------------------------------------------------------------------------


class _UUIDStringHelper(TypeDecorator):
    """SQLite-compatible UUID stored as VARCHAR(36) (LESSON-007)."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # type: ignore[override]
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):  # type: ignore[override]
        return uuid.UUID(value) if value is not None else None


def _make_isolated_engine():
    """Build a fresh SQLite in-memory engine with all reclaimrx ORM tables.

    Imports all model modules first (so Base.metadata is fully populated),
    applies LESSON-007 type swap, then creates all tables.

    Returns (engine, connection) -- caller must conn.close(); eng.dispose().
    """
    # Import models BEFORE the swap so Base.metadata is fully populated.
    import src.models.tables  # noqa: F401
    import src.models.detection_run_models  # noqa: F401

    from src._shim.db import Base

    eng = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
    )

    for table in Base.metadata.tables.values():
        table.schema = None
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, PG_UUID):
                col.type = _UUIDStringHelper()
            elif isinstance(col.type, ARRAY):
                col.type = JSON()

    conn = eng.connect()
    Base.metadata.create_all(conn)
    conn.commit()
    return eng, conn


# ---------------------------------------------------------------------------
# Import under test (late, so conftest can set up sys.path first)
# ---------------------------------------------------------------------------


def _import_cli():
    """Import src.cli.detect; raises ImportError on first RED run (before impl)."""
    from src.cli import detect as _detect_mod
    return _detect_mod


# ---------------------------------------------------------------------------
# Postgres engine helper
# ---------------------------------------------------------------------------


def _pg_engine():
    """Build a Postgres engine from RECLAIMRX_TEST_DB_URL."""
    url = os.environ["RECLAIMRX_TEST_DB_URL"]
    return create_engine(url, future=True)


# ===========================================================================
# TestArgParsing
# ===========================================================================


class TestArgParsing:
    """CLI argument parsing: --file/--tenant required; --resume/--force optional flags."""

    def test_parse_args_requires_file(self):
        """Calling _parse_args without --file raises SystemExit."""
        _mod = _import_cli()
        with pytest.raises(SystemExit):
            _mod._parse_args(["--tenant", str(_TENANT_A)])

    def test_parse_args_requires_tenant(self):
        """Calling _parse_args without --tenant raises SystemExit."""
        _mod = _import_cli()
        with pytest.raises(SystemExit):
            _mod._parse_args(["--file", str(_FIXTURE_CSV)])

    def test_parse_args_defaults(self, tmp_path):
        """Default values: resume=False, force=False, created_by=None."""
        _mod = _import_cli()
        fake_file = tmp_path / "test.csv"
        fake_file.write_text("header\n")
        args = _mod._parse_args(["--file", str(fake_file), "--tenant", str(_TENANT_A)])
        assert args.file == str(fake_file)
        assert args.tenant == str(_TENANT_A)
        assert args.resume is False
        assert args.force is False
        assert args.created_by is None

    def test_parse_args_resume_flag(self, tmp_path):
        """--resume flag sets resume=True."""
        _mod = _import_cli()
        fake_file = tmp_path / "test.csv"
        fake_file.write_text("header\n")
        args = _mod._parse_args(
            ["--file", str(fake_file), "--tenant", str(_TENANT_A), "--resume"]
        )
        assert args.resume is True

    def test_parse_args_force_flag(self, tmp_path):
        """--force flag sets force=True."""
        _mod = _import_cli()
        fake_file = tmp_path / "test.csv"
        fake_file.write_text("header\n")
        args = _mod._parse_args(
            ["--file", str(fake_file), "--tenant", str(_TENANT_A), "--force"]
        )
        assert args.force is True

    def test_parse_args_created_by(self, tmp_path):
        """--created-by sets created_by to the given UUID string."""
        _mod = _import_cli()
        fake_file = tmp_path / "test.csv"
        fake_file.write_text("header\n")
        uid = str(_SYS_UID)
        args = _mod._parse_args(
            ["--file", str(fake_file), "--tenant", str(_TENANT_A), "--created-by", uid]
        )
        assert args.created_by == uid


# ===========================================================================
# TestTenantTxnContextManager
# ===========================================================================


class TestTenantTxnContextManager:
    """tenant_txn(engine, tenant_id) yields a Session with the GUC set."""

    def test_tenant_txn_yields_session(self):
        """tenant_txn yields a Session object."""
        _mod = _import_cli()
        eng = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
        with patch.object(_mod, "_set_guc_for_connection", return_value=None):
            with _mod.tenant_txn(eng, _TENANT_A) as sess:
                assert isinstance(sess, Session)
        eng.dispose()

    def test_tenant_txn_sets_contextvar(self):
        """tenant_txn sets the shared tenant contextvar."""
        _mod = _import_cli()
        from shared.db.tenant_context import current_tenant_id
        eng = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
        with patch.object(_mod, "_set_guc_for_connection", return_value=None):
            with _mod.tenant_txn(eng, _TENANT_A) as _sess:
                tid = current_tenant_id.get()
                assert tid == _TENANT_A
        eng.dispose()

    def test_tenant_txn_clears_contextvar_on_exit(self):
        """tenant_txn clears the contextvar after exiting."""
        _mod = _import_cli()
        from shared.db.tenant_context import current_tenant_id
        eng = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
        with patch.object(_mod, "_set_guc_for_connection", return_value=None):
            with _mod.tenant_txn(eng, _TENANT_A):
                pass
        assert current_tenant_id.get() is None
        eng.dispose()

    def test_tenant_txn_clears_contextvar_on_exception(self):
        """tenant_txn clears the contextvar even when the body raises."""
        _mod = _import_cli()
        from shared.db.tenant_context import current_tenant_id
        eng = create_engine("sqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
        with patch.object(_mod, "_set_guc_for_connection", return_value=None):
            try:
                with _mod.tenant_txn(eng, _TENANT_A):
                    raise ValueError("simulated error")
            except ValueError:
                pass
        assert current_tenant_id.get() is None
        eng.dispose()

    @reclaimrx_pg
    def test_tenant_txn_sets_pg_guc(self):
        """On Postgres, tenant_txn actually executes SET LOCAL app.current_tenant_id."""
        _mod = _import_cli()
        eng = _pg_engine()
        try:
            with _mod.tenant_txn(eng, _TENANT_A) as sess:
                result = sess.execute(
                    text("SELECT current_setting('app.current_tenant_id', true)")
                ).scalar()
                assert result == str(_TENANT_A)
        finally:
            eng.dispose()


# ===========================================================================
# TestRunDetectEndToEnd (SQLite-backed, advisory lock patched)
# ===========================================================================


class TestRunDetectEndToEnd:
    """run_detect over the fixture CSV: run completed, anomaly_count > 0, summary printed."""

    def test_run_detect_completes_and_returns_summary(self, capsys):
        """run_detect over sample_claims.csv completes and prints a summary."""
        _mod = _import_cli()
        eng, conn = _make_isolated_engine()
        try:
            with (
                patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
                patch.object(_mod, "_set_guc_for_connection", return_value=None),
            ):
                summary = _mod.run_detect(
                    str(_FIXTURE_CSV),
                    tenant=_TENANT_A,
                    created_by=_SYS_UID,
                    engine=eng,
                )
        finally:
            conn.close()
            eng.dispose()

        assert isinstance(summary, dict)
        assert summary["run_meta"]["status"] == "completed"
        captured = capsys.readouterr()
        assert "Detection Run" in captured.out or "detection" in captured.out.lower()

    def test_run_detect_anomaly_count_gt_zero(self):
        """run_detect over sample_claims.csv produces > 0 anomalies."""
        _mod = _import_cli()
        eng, conn = _make_isolated_engine()
        try:
            with (
                patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
                patch.object(_mod, "_set_guc_for_connection", return_value=None),
            ):
                summary = _mod.run_detect(
                    str(_FIXTURE_CSV),
                    tenant=_TENANT_A,
                    created_by=_SYS_UID,
                    engine=eng,
                )
        finally:
            conn.close()
            eng.dispose()

        assert summary["anomalies"]["total"] > 0, (
            f"Expected >0 anomalies on sample_claims.csv; got {summary['anomalies']['total']}"
        )

    def test_run_detect_all001_fires(self):
        """ALL-001 anomalies (>= 3) are present in the summary by_finding_code."""
        _mod = _import_cli()
        eng, conn = _make_isolated_engine()
        try:
            with (
                patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
                patch.object(_mod, "_set_guc_for_connection", return_value=None),
            ):
                summary = _mod.run_detect(
                    str(_FIXTURE_CSV),
                    tenant=_TENANT_A,
                    created_by=_SYS_UID,
                    engine=eng,
                )
        finally:
            conn.close()
            eng.dispose()

        by_code = summary["anomalies"]["by_finding_code"]
        assert "ALL-001" in by_code, f"Expected ALL-001 in by_finding_code; got {by_code}"
        assert by_code["ALL-001"] >= 3


# ===========================================================================
# TestFailurePath
# ===========================================================================


class TestFailurePath:
    """On exception in load_csv, run is marked status='failed' in a SEPARATE transaction."""

    def test_failure_marks_run_failed_separate_txn(self):
        """A load error marks run.status='failed' + failure_reason set."""
        _mod = _import_cli()
        from sqlalchemy import select
        from src.models.detection_run_models import DetectionRun

        eng, conn = _make_isolated_engine()
        conn.close()  # Close setup conn; engine stays alive for queries

        with (
            patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
            patch.object(_mod, "_set_guc_for_connection", return_value=None),
            patch("src.detection.csv_ingest.load_csv", side_effect=RuntimeError("simulated load failure")),
        ):
            with pytest.raises(RuntimeError, match="simulated load failure"):
                _mod.run_detect(
                    str(_FIXTURE_CSV),
                    tenant=_TENANT_A,
                    created_by=_SYS_UID,
                    engine=eng,
                )

        # The run row must exist and be failed.
        with Session(eng) as verify_sess:
            run = verify_sess.execute(
                select(DetectionRun).where(DetectionRun.tenant_id == _TENANT_A)
            ).scalar_one_or_none()
            assert run is not None, "Run row must have been created before the failure"
            assert run.status == "failed", f"Expected status='failed', got {run.status!r}"
            assert run.failure_reason is not None, "failure_reason must be set on failed run"

        eng.dispose()

    def test_failure_path_run_detect_re_raises(self):
        """run_detect re-raises the exception after marking the run failed."""
        _mod = _import_cli()
        eng, conn = _make_isolated_engine()
        conn.close()

        with (
            patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
            patch.object(_mod, "_set_guc_for_connection", return_value=None),
            patch("src.detection.csv_ingest.load_csv", side_effect=ValueError("bad load")),
        ):
            with pytest.raises(ValueError, match="bad load"):
                _mod.run_detect(
                    str(_FIXTURE_CSV),
                    tenant=_TENANT_A,
                    created_by=_SYS_UID,
                    engine=eng,
                )

        eng.dispose()


# ===========================================================================
# TestRlsIsolation - POSTGRES-GATED
# ===========================================================================


class TestRlsIsolation:
    """RLS isolation proofs: TENANT_B sees 0 rows; unset GUC sees 0 rows.

    ALL assertions in this class require Postgres + ifx_dev_app role.
    Skipped unless RECLAIMRX_TEST_DB_URL is set.
    """

    @reclaimrx_pg
    def test_tenant_b_sees_zero_anomalies_after_tenant_a_run(self):
        """Seed TENANT_A via run_detect; in a TENANT_B txn see 0 anomaly rows.

        Proves RLS at the DB layer: ifx_dev_app cannot read TENANT_A data
        when GUC is set to TENANT_B.
        """
        _mod = _import_cli()
        eng = _pg_engine()
        try:
            summary = _mod.run_detect(
                str(_FIXTURE_CSV),
                tenant=_TENANT_A,
                created_by=_SYS_UID,
                engine=eng,
                force=True,
            )
            assert summary["anomalies"]["total"] > 0, (
                "TENANT_A run must produce anomalies for isolation proof to be meaningful"
            )

            with eng.connect() as conn:
                txn = conn.begin()
                conn.execute(
                    text("SET LOCAL app.current_tenant_id = :tid"),
                    {"tid": str(_TENANT_B)},
                )
                count = conn.execute(
                    text("SELECT count(*) FROM reclaimrx.anomalies")
                ).scalar()
                txn.rollback()

            assert count == 0, (
                f"TENANT_B must see 0 anomaly rows (RLS should deny); got {count}. "
                "If non-zero, RLS policy is not enforcing."
            )
        finally:
            eng.dispose()

    @reclaimrx_pg
    def test_unset_guc_sees_zero_anomalies(self):
        """With GUC unset (empty string), RLS denies all rows.

        Proves the NULLIF predicate in migration 0002 rejects blank GUC.
        """
        _mod = _import_cli()
        eng = _pg_engine()
        try:
            _mod.run_detect(
                str(_FIXTURE_CSV),
                tenant=_TENANT_A,
                created_by=_SYS_UID,
                engine=eng,
                force=True,
            )

            with eng.connect() as conn:
                txn = conn.begin()
                conn.execute(text("SET LOCAL app.current_tenant_id = ''"))
                count = conn.execute(
                    text("SELECT count(*) FROM reclaimrx.anomalies")
                ).scalar()
                txn.rollback()

            assert count == 0, (
                f"Unset/empty GUC must see 0 rows (NULLIF predicate fails closed); got {count}. "
                "If non-zero, RLS NULLIF guard is broken."
            )
        finally:
            eng.dispose()

    @reclaimrx_pg
    def test_correct_tenant_guc_sees_own_rows(self):
        """TENANT_A with correct GUC sees its own anomaly rows (> 0)."""
        _mod = _import_cli()
        eng = _pg_engine()
        try:
            summary = _mod.run_detect(
                str(_FIXTURE_CSV),
                tenant=_TENANT_A,
                created_by=_SYS_UID,
                engine=eng,
                force=True,
            )
            expected_count = summary["anomalies"]["total"]
            assert expected_count > 0

            with eng.connect() as conn:
                txn = conn.begin()
                conn.execute(
                    text("SET LOCAL app.current_tenant_id = :tid"),
                    {"tid": str(_TENANT_A)},
                )
                count = conn.execute(
                    text("SELECT count(*) FROM reclaimrx.anomalies WHERE tenant_id = :tid::uuid"),
                    {"tid": str(_TENANT_A)},
                ).scalar()
                txn.rollback()

            assert count == expected_count, (
                f"TENANT_A should see {expected_count} rows; got {count}"
            )
        finally:
            eng.dispose()

    @reclaimrx_pg
    def test_engine_uses_app_role_not_superuser(self):
        """The CLI engine must connect as ifx_dev_app, not infinityrx superuser."""
        _mod = _import_cli()
        eng = _pg_engine()
        try:
            with eng.connect() as conn:
                role = conn.execute(text("SELECT current_user")).scalar()
            assert role == "ifx_dev_app", (
                f"CLI engine must connect as ifx_dev_app; got {role!r}. "
                "RECLAIMRX_TEST_DB_URL must use the ifx_dev_app role credentials."
            )
        finally:
            eng.dispose()
