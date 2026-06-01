"""Regression tests for run_detection (batch_engine) DB-dialect guards.

Crash-recovery pin for Task 4c. The FDB-prefetch block in run_detection is guarded
by ``_is_postgres``, but the ALL-002 / ALL-003 reference-rule block was left
unguarded when the implementing session crashed mid-task. Those evaluators use
Postgres-only ``unnest(ARRAY[...]::text[])`` against ``reference.*`` FDW foreign
tables that do not exist in the SQLite unit-test fixtures.

Once the rule catalog flipped ALL-002 / ALL-003 ``deferred_data_feed`` -> False,
``register_rule_instances`` began creating instances for them, so every SQLite
``run_detection`` call seeding the full catalog hit the unguarded FDW query and
raised ``OperationalError`` -- cascading to ~92 unit-test failures.

This test pins the fix: ``run_detection`` MUST complete on SQLite with ALL-002 /
ALL-003 instances applicable, skipping the Postgres-only reference checks while
still exposing the ``data_quality`` keys.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from src.detection.batch_engine import run_detection
from src.detection.rule_type_registry import (
    register_rule_instances,
    register_rule_types,
)
from src.models.detection_run_models import CsvUploadRow, DetectionRun
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID

# Full column set -> every non-deferred rule (incl. ALL-002/ALL-003) is instantiated.
_FULL_COLUMNS: set[str] = {
    "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
    "transaction_code", "transaction_status",
    "day_supply",
    "pharmacy_npi", "prescriber_npi", "patient_state",
    "extended_wac", "ingredient_cost_paid", "dispensing_fee_paid",
    "quantity_dispensed",
    "reversed_check", "date_added_timestamp",
    "u_c", "pos_adjustment",
    "total_paid_amt",
}


def _seed_run_with_rows(db: Session) -> DetectionRun:
    run = DetectionRun(
        tenant_id=TEST_TENANT_ID,
        data_source="csv_upload",
        run_label="all002-all003-sqlite-guard-regression",
        status="in_progress",
        created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 2, "expected_count": 2},
    )
    db.add(run)
    db.flush()
    for i in range(1, 3):
        db.add(
            CsvUploadRow(
                tenant_id=TEST_TENANT_ID,
                detection_run_id=run.id,
                row_number=i,
                row_data={
                    "pharmacy_npi": "1234560001",
                    "prescriber_npi": "1598765432",
                    "ndc": "00069315066",
                    "date_of_service": "2026-01-15",
                    "transaction_code": "B1",
                    "transaction_status": "Paid",
                    "total_paid_amt": "75.00",
                },
                resolution_method="declared",
                resolved_pharmacy_npi="1234560001",
                resolved_ndc="00069315066",
            )
        )
    db.flush()
    return run


def test_run_detection_completes_on_sqlite_with_all002_all003_applicable(db: Session):
    """run_detection must not raise on SQLite when ALL-002/ALL-003 are gate-applicable.

    Pre-fix: the unguarded reference block executed unnest(ARRAY[...]::text[]) against
    SQLite and raised OperationalError. The _is_postgres guard skips those Postgres-only
    checks while the run still completes and exposes its data_quality keys.
    """
    register_rule_types(db)
    register_rule_instances(db, TEST_TENANT_ID, _FULL_COLUMNS, TEST_USER_ID)
    db.flush()
    run = _seed_run_with_rows(db)

    # Must NOT raise. (Pre-fix: sqlite3.OperationalError from the FDW unnest query.)
    run_detection(db, run)
    db.refresh(run)

    assert run.status == "completed"
    dq = run.resolution_stats.get("data_quality", {})
    for key in (
        "missing_pharmacy_npi",
        "invalid_pharmacy_npi",
        "missing_prescriber_npi",
        "invalid_prescriber_npi",
        "no_fdb_wac",
    ):
        assert key in dq, f"data_quality must expose '{key}', got keys={list(dq.keys())}"
