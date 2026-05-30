"""TDD: transaction isolation + statement_timeout fixes for 2.6M-row dry-run failure.

Root cause of the dry-run rollback
------------------------------------
1. ALL-006 baseline (pharmacy_weekday_volume) hit the Postgres 30s statement_timeout
   and raised QueryCanceled.
2. That exception aborted the in-flight transaction in run_detection, which shared
   the same transaction as the Phase 3 `tenant_txn` context in detect.py.
3. Every subsequent statement in that transaction raised InFailedSqlTransaction.
4. The surrounding tenant_txn rolled back on exception, losing the entire detection
   session including run.status and anomalies.
5. Because ingest (Phase 2b) ran in its own committed transaction, the csv_upload_rows
   survived -- but that run is now stuck 'in_progress' with no detection results.

Fix contract
------------
1. Statement timeout disabled: run_detection accepts `statement_timeout_ms` (default 0 =
   unlimited) and executes SET [LOCAL] statement_timeout = :ms on the batch session at
   the start of detection.  On SQLite (tests) this is a no-op / patched out.
   The value defaults to RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS env var, else 0.

2. Per-unit transaction isolation in _run_baselines: each baseline computation runs in
   its own nested try/except.  If one baseline raises, it is logged and recorded in
   resolution_stats["errors"], and the next baseline continues.  One baseline timeout
   MUST NOT abort the detection session.

3. Per-unit isolation in Pass 2 grouping rules: each grouping rule is already wrapped in
   try/except in _evaluate_grouping_rules; this test verifies the isolation chain works
   end-to-end through run_detection.

4. Run finalization: after a partial failure, run.status must be 'completed' (detection
   finished) with errors recorded in resolution_stats["errors"].  The run MUST NOT be
   left 'in_progress'.

5. Ingest durability: csv_upload_rows and the detection_run row survive even when a
   baseline raises.  The failure must not roll back ingest data committed in Phase 2b.
   (This is enforced by the phase boundaries in detect.py -- run_detection is called in
   its own tenant_txn; if run_detection raises, the run is marked 'failed' via
   _mark_run_failed in a separate transaction, but csv_upload_rows from Phase 2b remain.)

Tests
-----
RED tests are written first; they fail before the implementation changes are applied.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.detection.csv_ingest import create_or_resume_run, load_csv
from src.detection.rule_type_registry import register_rule_instances, register_rule_types
from src.models.detection_run_models import (
    Anomaly,
    DetectionRun,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
_SYS_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "sample_claims.csv"

_FULL_CSV_COLUMNS: set[str] = {
    "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
    "transaction_code", "transaction_status",
    "day_supply",
    "pharmacy_npi", "prescriber_npi", "patient_state",
    "extended_wac", "ingredient_cost_paid", "dispensing_fee_paid",
    "quantity_dispensed",
    "reversed_check", "date_added_timestamp",
    "statement_account",
    "u_c", "pos_adjustment",
    "total_paid_amt",
    "client_id",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture(db: Session) -> DetectionRun:
    """Seed rule types + instances, load sample CSV, return DetectionRun."""
    register_rule_types(db)
    register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

    with patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None):
        run = create_or_resume_run(
            db,
            tenant_id=_TENANT,
            path=str(_FIXTURE_PATH),
            created_by=_SYS_UID,
        )
    load_csv(db, run, chunk_size=10)
    db.flush()
    return run


# ===========================================================================
# TestStatementTimeoutDisabled
# ===========================================================================


class TestStatementTimeoutDisabled:
    """run_detection accepts statement_timeout_ms and issues SET statement_timeout."""

    def test_run_detection_accepts_statement_timeout_ms_kwarg(self, db: Session):
        """run_detection must accept a statement_timeout_ms keyword argument.

        Calling it with statement_timeout_ms=0 must not raise TypeError.
        This is a RED test -- fails before the parameter is added.
        """
        from src.detection.batch_engine import run_detection

        run = _load_fixture(db)
        # Must not raise TypeError("unexpected keyword argument 'statement_timeout_ms'")
        count = run_detection(db, run, statement_timeout_ms=0)
        assert isinstance(count, int)

    def test_set_statement_timeout_called_on_batch_session(self, db: Session):
        """run_detection must call _set_batch_statement_timeout on the db session.

        The helper is a module-level function so it can be patched in tests.
        On Postgres it issues SET [LOCAL] statement_timeout = :ms.
        On SQLite it is a no-op (guards against unsupported syntax).

        This test patches the helper at the module level to confirm it is called
        with the correct timeout value.
        """
        import src.detection.batch_engine as _be

        calls: list[int] = []

        def _capture(session, ms: int) -> None:
            calls.append(ms)

        run = _load_fixture(db)
        with patch.object(_be, "_set_batch_statement_timeout", side_effect=_capture):
            _be.run_detection(db, run, statement_timeout_ms=999)

        assert len(calls) == 1, (
            "_set_batch_statement_timeout must be called exactly once per run_detection call"
        )
        assert calls[0] == 999, (
            f"Expected timeout_ms=999, got {calls[0]}"
        )

    def test_default_timeout_is_zero(self, db: Session):
        """Default statement_timeout_ms is 0 (unlimited) when not supplied.

        Verifies the env-var-driven default produces 0 when
        RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS is unset.
        """
        import src.detection.batch_engine as _be

        calls: list[int] = []

        def _capture(session, ms: int) -> None:
            calls.append(ms)

        # Ensure the env var is unset for this test.
        env_patch = {k: v for k, v in os.environ.items() if k != "RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS"}
        run = _load_fixture(db)
        with patch.dict(os.environ, env_patch, clear=True), \
             patch.object(_be, "_set_batch_statement_timeout", side_effect=_capture):
            _be.run_detection(db, run)

        assert calls == [0], f"Default timeout must be 0; got {calls}"


# ===========================================================================
# TestBaselineFailureIsolation
# ===========================================================================


class TestBaselineFailureIsolation:
    """One baseline failure must not abort the detection run or lose other results.

    The critical invariant from the 2.6M dry-run post-mortem:
      - A single compute_baseline raising (simulating a statement_timeout) must NOT
        cause run_detection to raise.
      - All other baselines and Pass 2 rules must still execute.
      - csv_upload_rows (ingest) must remain accessible.
      - run.status must be terminal ('completed'), never 'in_progress'.
      - resolution_stats["errors"] must record the failed baseline.
    """

    def test_baseline_failure_does_not_raise_from_run_detection(self, db: Session):
        """run_detection completes (returns int) even when one compute_baseline raises.

        RED: currently _run_baselines propagates the exception, aborting run_detection.
        GREEN: each baseline is isolated; failure logged; run_detection returns normally.
        """
        from src.detection.batch_engine import run_detection

        run = _load_fixture(db)

        # Patch compute_baseline to raise on the FIRST call (simulating ALL-006 timeout),
        # then succeed on subsequent calls.
        call_count = {"n": 0}
        original_compute = __import__(
            "src.detection.baselines", fromlist=["compute_baseline"]
        ).compute_baseline

        def _flaky_baseline(session, run_obj, *, kind, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated statement_timeout on baseline kind=" + kind)
            return original_compute(session, run_obj, kind=kind, **kwargs)

        with patch("src.detection.baselines.compute_baseline", side_effect=_flaky_baseline), \
             patch("src.detection.batch_engine.compute_baseline", side_effect=_flaky_baseline):
            # Must NOT raise -- failure is isolated per unit.
            result = run_detection(db, run)

        assert isinstance(result, int), (
            f"run_detection must return int even after baseline failure; got {type(result)}"
        )

    def test_baseline_failure_run_status_is_terminal(self, db: Session):
        """After a baseline failure, run.status must be 'completed', never 'in_progress'.

        The run must always reach a terminal state regardless of per-unit errors.
        """
        from src.detection.batch_engine import run_detection

        run = _load_fixture(db)
        call_count = {"n": 0}
        original_compute = __import__(
            "src.detection.baselines", fromlist=["compute_baseline"]
        ).compute_baseline

        def _flaky_baseline(session, run_obj, *, kind, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated timeout")
            return original_compute(session, run_obj, kind=kind, **kwargs)

        with patch("src.detection.baselines.compute_baseline", side_effect=_flaky_baseline), \
             patch("src.detection.batch_engine.compute_baseline", side_effect=_flaky_baseline):
            run_detection(db, run)

        assert run.status == "completed", (
            f"run.status must be 'completed' after partial failure; got {run.status!r}"
        )

    def test_baseline_failure_recorded_in_resolution_stats_errors(self, db: Session):
        """Failed baseline must appear in resolution_stats['errors'].

        Each error entry must include at least the baseline 'kind' and 'reason' keys
        so operators can diagnose which baseline failed and why.
        """
        from src.detection.batch_engine import run_detection

        run = _load_fixture(db)
        failing_kind: list[str] = []

        original_compute = __import__(
            "src.detection.baselines", fromlist=["compute_baseline"]
        ).compute_baseline

        call_count = {"n": 0}

        def _flaky_baseline(session, run_obj, *, kind, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                failing_kind.append(kind)
                raise RuntimeError("timeout on " + kind)
            return original_compute(session, run_obj, kind=kind, **kwargs)

        with patch("src.detection.baselines.compute_baseline", side_effect=_flaky_baseline), \
             patch("src.detection.batch_engine.compute_baseline", side_effect=_flaky_baseline):
            run_detection(db, run)

        stats = run.resolution_stats or {}
        errors = stats.get("errors", [])
        assert isinstance(errors, list), (
            f"resolution_stats['errors'] must be a list; got {type(errors)}"
        )
        assert len(errors) >= 1, (
            "resolution_stats['errors'] must contain at least one entry for the failed baseline"
        )
        first_error = errors[0]
        assert "kind" in first_error, (
            f"Error entry must have 'kind' key; got {first_error}"
        )
        assert "reason" in first_error, (
            f"Error entry must have 'reason' key; got {first_error}"
        )
        assert first_error["kind"] == failing_kind[0], (
            f"Error 'kind' must be {failing_kind[0]!r}; got {first_error['kind']!r}"
        )

    def test_other_rules_still_produce_anomalies_after_baseline_failure(self, db: Session):
        """Pass 2 grouping/single-row rules fire even when a baseline fails.

        ALL-001 (duplicate claim) does not need a baseline. It must still fire
        even when ALL-006 (pharmacy_weekday_volume baseline) raises.
        """
        from src.detection.batch_engine import run_detection

        run = _load_fixture(db)

        # Make all baselines fail.
        def _always_fail(session, run_obj, *, kind, **kwargs):
            raise RuntimeError("simulated timeout: " + kind)

        with patch("src.detection.baselines.compute_baseline", side_effect=_always_fail), \
             patch("src.detection.batch_engine.compute_baseline", side_effect=_always_fail):
            count = run_detection(db, run)

        # ALL-001 fires on the fixture regardless of baselines (requires >= 2 auth hashes).
        assert count > 0, (
            "Grouping rules (ALL-001) must still fire even when all baselines fail; "
            f"got anomaly count = {count}"
        )

        # Verify ALL-001 anomalies are in the DB.
        all001_count = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalars().all()
        assert len(all001_count) >= 3, (
            f"Expected >= 3 ALL-001 anomalies; got {len(all001_count)}"
        )

    def test_csv_upload_rows_accessible_after_baseline_failure(self, db: Session):
        """CsvUploadRow data is queryable after a baseline failure in run_detection.

        Proves ingest rows are NOT rolled back by a detection-phase failure.
        (In production these rows are in a committed Phase 2b transaction; in
        tests they share the SAVEPOINT session, so this verifies the session
        is still in a usable state after the failure.)
        """
        from src.detection.batch_engine import run_detection
        from src.models.detection_run_models import CsvUploadRow
        from sqlalchemy import func

        run = _load_fixture(db)
        row_count_before = db.execute(
            select(func.count()).select_from(CsvUploadRow).where(
                CsvUploadRow.detection_run_id == run.id
            )
        ).scalar()

        def _always_fail(session, run_obj, *, kind, **kwargs):
            raise RuntimeError("simulated timeout")

        with patch("src.detection.baselines.compute_baseline", side_effect=_always_fail), \
             patch("src.detection.batch_engine.compute_baseline", side_effect=_always_fail):
            run_detection(db, run)

        row_count_after = db.execute(
            select(func.count()).select_from(CsvUploadRow).where(
                CsvUploadRow.detection_run_id == run.id
            )
        ).scalar()

        assert row_count_after == row_count_before, (
            f"CsvUploadRow count changed after baseline failure: "
            f"before={row_count_before} after={row_count_after}. "
            "Ingest rows must not be lost due to a detection-phase failure."
        )


# ===========================================================================
# TestIngestDurabilityViaDetect
# ===========================================================================


class TestIngestDurabilityViaDetect:
    """run_detect: ingest (csv_upload_rows + detection_run row) survives a
    detection-phase failure.

    Uses the real detect.run_detect() with a patched engine so we exercise
    the full Phase 1 / Phase 2a / Phase 2b / Phase 3 boundary.
    """

    def test_run_row_persists_after_detection_phase_failure(self):
        """Detection failure leaves the run row with a terminal status (failed or completed).

        Phase 2a commits the run row before detection starts.  If Phase 3 raises,
        _mark_run_failed writes status='failed' in a separate transaction.  The run row
        must never disappear.
        """
        from src.cli.detect import run_detect
        from src.models.detection_run_models import DetectionRun

        # Build a fresh SQLite engine using the same helper as test_cli_and_isolation.
        from tests.detection.test_cli_and_isolation import _make_isolated_engine

        eng, conn = _make_isolated_engine()
        conn.close()

        try:
            with (
                patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
                patch("src.cli.detect._set_guc_for_connection", return_value=None),
                # Make run_detection raise (simulates detection-phase failure after ingest).
                patch(
                    "src.detection.batch_engine.run_detection",
                    side_effect=RuntimeError("simulated detection failure"),
                ),
            ):
                with pytest.raises(RuntimeError, match="simulated detection failure"):
                    run_detect(
                        str(_FIXTURE_PATH),
                        tenant=_TENANT,
                        created_by=_SYS_UID,
                        engine=eng,
                    )

            # The run row must exist (committed in Phase 2a) and must be 'failed'.
            with Session(eng) as verify:
                run = verify.execute(
                    select(DetectionRun).where(DetectionRun.tenant_id == _TENANT)
                ).scalar_one_or_none()

            assert run is not None, (
                "DetectionRun row must survive a detection-phase failure (committed in Phase 2a)"
            )
            assert run.status == "failed", (
                f"Run status must be 'failed' after detection failure; got {run.status!r}"
            )
        finally:
            eng.dispose()

    def test_csv_upload_rows_persist_after_detection_failure(self):
        """csv_upload_rows committed in Phase 2b survive a Phase 3 (detection) failure.

        This is the core durability guarantee: Phase 2b commits before Phase 3 starts,
        so a detection failure must never roll back ingest data.
        """
        from src.cli.detect import run_detect
        from src.models.detection_run_models import CsvUploadRow
        from sqlalchemy import func

        from tests.detection.test_cli_and_isolation import _make_isolated_engine

        eng, conn = _make_isolated_engine()
        conn.close()

        try:
            with (
                patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None),
                patch("src.cli.detect._set_guc_for_connection", return_value=None),
                patch(
                    "src.detection.batch_engine.run_detection",
                    side_effect=RuntimeError("detection blow-up"),
                ),
            ):
                with pytest.raises(RuntimeError, match="detection blow-up"):
                    run_detect(
                        str(_FIXTURE_PATH),
                        tenant=_TENANT,
                        created_by=_SYS_UID,
                        engine=eng,
                    )

            # csv_upload_rows must be non-zero (committed in Phase 2b).
            with Session(eng) as verify:
                row_count = verify.execute(
                    select(func.count()).select_from(CsvUploadRow).where(
                        CsvUploadRow.tenant_id == _TENANT
                    )
                ).scalar()

            assert row_count > 0, (
                f"csv_upload_rows must be durable after detection failure; "
                f"got row_count={row_count}. "
                "Phase 2b (ingest) must commit before Phase 3 (detection) begins."
            )
        finally:
            eng.dispose()
