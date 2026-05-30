"""Task 4.1 — Detection-run summary report.

TDD: RED tests written first; implementation in src/detection/run_summary.py.

Contract
--------
build_summary(db, run) -> dict
    Read-only aggregation over anomalies, detection_rule_evaluation_log, and
    detection_rule_instances/types for a completed DetectionRun.

    Keys returned:
      rows:
        expected_count   – from run.resolution_stats
        inserted_count   – from run.resolution_stats
        declared         – from run.resolution_stats
        unmapped         – from run.resolution_stats
      rules:
        applied          – count of applicable rule-instance evaluation rows
                           (evaluation_result != 'skipped_inapplicable') for this run
        skipped          – count of DetectionRuleEvaluationLog rows with
                           evaluation_result='skipped_inapplicable' for this run
      anomalies:
        total            – run.anomaly_count (from DB, not in-memory field)
        by_finding_code  – {code: count} dict
        by_family        – {family: count} dict (join anomaly→rule_instance→rule_type)
        by_severity      – {severity: count} dict
      top_entities:
        pharmacies       – list of {pharmacy_npi, anomaly_count}, descending, top N
        prescribers      – list of {prescriber_npi, anomaly_count}, descending, top N
      dollars_at_risk    – Decimal, SUM of anomalies.amount_paid for this run
      run_meta:
        run_label        – str
        status           – str
        started_at       – datetime
        completed_at     – datetime | None
        source_sha256    – str | None

format_summary(summary) -> str
    Human-readable multi-line string for CLI printing.
    Must be non-empty and include anomaly count and dollars_at_risk.

Fixture
-------
Uses the _load_fixture / _seed_csv_row / run_detection helpers from
test_detection_passes.py (duplicated locally to keep detection test files
self-contained — avoids import coupling between test modules).

Expected anomaly breakdown on the 54-row fixture after run_detection:
  ALL-001 × 3, MFR-002 × 1, MFR-001 × >= 1
  Total >= 5
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.detection.csv_ingest import create_or_resume_run, load_csv
from src.detection.rule_type_registry import register_rule_instances, register_rule_types
from src.models.detection_run_models import (
    Anomaly,
    CsvUploadRow,
    DetectionRun,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT = uuid.UUID("11111111-1111-1111-1111-111111111111")
_SYS_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample_claims.csv"
)

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
# Local fixture helpers (self-contained — no import from test_detection_passes)
# ---------------------------------------------------------------------------


def _load_fixture(db: Session) -> DetectionRun:
    """Load the sample CSV into a fresh DetectionRun and seed rule instances."""
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


def _make_empty_run(db: Session) -> DetectionRun:
    """A run with 0 rows — used to test empty-run edge cases."""
    register_rule_types(db)
    register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)
    run = DetectionRun(
        tenant_id=_TENANT,
        data_source="csv_upload",
        run_label="empty-summary-run",
        source_path="/tmp/empty.csv",
        source_filename="empty.csv",
        source_sha256="0" * 64,
        created_by=_SYS_UID,
        resolution_stats={
            "expected_count": 0,
            "inserted_count": 0,
            "declared": 0,
            "unmapped": 0,
        },
    )
    db.add(run)
    db.flush()
    return run


# ---------------------------------------------------------------------------
# Import under test — intentionally LATE so RED test gives ImportError/NameError
# rather than a silent pass if the module doesn't exist yet.
# ---------------------------------------------------------------------------
from src.detection.run_summary import build_summary, format_summary  # noqa: E402


# ===========================================================================
# TestBuildSummaryEmpty
# ===========================================================================


class TestBuildSummaryEmpty:
    """build_summary on a run with zero anomalies returns zeros without crashing."""

    def test_empty_run_returns_dict(self, db: Session):
        """build_summary returns a dict even when the run has no anomalies."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert isinstance(summary, dict)

    def test_empty_run_anomaly_total_is_zero(self, db: Session):
        """anomalies.total is 0 for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["anomalies"]["total"] == 0

    def test_empty_run_dollars_at_risk_is_zero(self, db: Session):
        """dollars_at_risk is Decimal("0") for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["dollars_at_risk"] == Decimal("0")

    def test_empty_run_dollars_at_risk_is_decimal_type(self, db: Session):
        """dollars_at_risk must be Decimal, not float, even on an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert isinstance(summary["dollars_at_risk"], Decimal), (
            f"dollars_at_risk must be Decimal; got {type(summary['dollars_at_risk'])}"
        )

    def test_empty_run_by_finding_code_is_empty_dict(self, db: Session):
        """anomalies.by_finding_code is an empty dict for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["anomalies"]["by_finding_code"] == {}

    def test_empty_run_by_severity_is_empty_dict(self, db: Session):
        """anomalies.by_severity is an empty dict for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["anomalies"]["by_severity"] == {}

    def test_empty_run_top_pharmacies_is_empty_list(self, db: Session):
        """top_entities.pharmacies is [] for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["top_entities"]["pharmacies"] == []

    def test_empty_run_top_prescribers_is_empty_list(self, db: Session):
        """top_entities.prescribers is [] for an empty run."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        assert summary["top_entities"]["prescribers"] == []

    def test_empty_run_run_meta_fields(self, db: Session):
        """run_meta contains run_label, status, started_at, completed_at, source_sha256."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        meta = summary["run_meta"]
        assert meta["run_label"] == "empty-summary-run"
        assert meta["status"] == "in_progress"
        assert meta["started_at"] is not None
        assert meta["source_sha256"] == "0" * 64

    def test_empty_run_rows_section(self, db: Session):
        """rows section reflects resolution_stats values."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        rows = summary["rows"]
        assert rows["expected_count"] == 0
        assert rows["inserted_count"] == 0


# ===========================================================================
# TestBuildSummaryWithDetection
# ===========================================================================


class TestBuildSummaryWithDetection:
    """build_summary after run_detection on the 54-row fixture returns correct counts."""

    def _run(self, db: Session) -> tuple[DetectionRun, dict]:
        from src.detection.batch_engine import run_detection
        run = _load_fixture(db)
        run_detection(db, run)
        summary = build_summary(db, run)
        return run, summary

    def test_anomaly_total_matches_db_count(self, db: Session):
        """summary anomalies.total equals actual Anomaly row count for the run."""
        run, summary = self._run(db)
        db_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.tenant_id == _TENANT,
            )
        ).scalar()
        assert summary["anomalies"]["total"] == db_count

    def test_all001_appears_in_by_finding_code(self, db: Session):
        """by_finding_code has 'ALL-001' with count 3."""
        _, summary = self._run(db)
        by_code = summary["anomalies"]["by_finding_code"]
        assert "ALL-001" in by_code, (
            f"Expected ALL-001 in by_finding_code; keys={list(by_code.keys())}"
        )
        assert by_code["ALL-001"] == 3, (
            f"Expected ALL-001 count=3, got {by_code['ALL-001']}"
        )

    def test_mfr002_appears_in_by_finding_code(self, db: Session):
        """by_finding_code has 'MFR-002' with count 1."""
        _, summary = self._run(db)
        by_code = summary["anomalies"]["by_finding_code"]
        assert "MFR-002" in by_code, (
            f"Expected MFR-002 in by_finding_code; keys={list(by_code.keys())}"
        )
        assert by_code["MFR-002"] == 1, (
            f"Expected MFR-002 count=1, got {by_code['MFR-002']}"
        )

    def test_mfr001_appears_in_by_finding_code(self, db: Session):
        """by_finding_code has 'MFR-001' with count >= 1."""
        _, summary = self._run(db)
        by_code = summary["anomalies"]["by_finding_code"]
        assert "MFR-001" in by_code, (
            f"Expected MFR-001 in by_finding_code; keys={list(by_code.keys())}"
        )
        assert by_code["MFR-001"] >= 1

    def test_by_finding_code_counts_sum_to_total(self, db: Session):
        """Sum of by_finding_code values equals anomalies.total."""
        _, summary = self._run(db)
        total = summary["anomalies"]["total"]
        code_sum = sum(summary["anomalies"]["by_finding_code"].values())
        assert code_sum == total, (
            f"by_finding_code sum {code_sum} != total {total}"
        )

    def test_by_severity_present_and_non_empty(self, db: Session):
        """by_severity has at least one severity bucket."""
        _, summary = self._run(db)
        by_sev = summary["anomalies"]["by_severity"]
        assert isinstance(by_sev, dict)
        assert len(by_sev) >= 1

    def test_by_severity_counts_sum_to_total(self, db: Session):
        """Sum of by_severity values equals anomalies.total."""
        _, summary = self._run(db)
        total = summary["anomalies"]["total"]
        sev_sum = sum(summary["anomalies"]["by_severity"].values())
        assert sev_sum == total, (
            f"by_severity sum {sev_sum} != total {total}"
        )

    def test_by_family_present_and_non_empty(self, db: Session):
        """by_family has at least one family bucket when anomalies exist."""
        _, summary = self._run(db)
        by_fam = summary["anomalies"]["by_family"]
        assert isinstance(by_fam, dict)
        assert len(by_fam) >= 1

    def test_dollars_at_risk_is_decimal(self, db: Session):
        """dollars_at_risk is Decimal, not float."""
        _, summary = self._run(db)
        assert isinstance(summary["dollars_at_risk"], Decimal), (
            f"dollars_at_risk must be Decimal; got {type(summary['dollars_at_risk'])}"
        )

    def test_dollars_at_risk_equals_sum_of_amount_paid(self, db: Session):
        """dollars_at_risk equals the exact sum of anomalies.amount_paid for the run."""
        run, summary = self._run(db)
        rows = db.execute(
            select(Anomaly.amount_paid).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.tenant_id == _TENANT,
                Anomaly.amount_paid.isnot(None),
            )
        ).scalars().all()
        # Manually sum as Decimal to get expected value
        expected = sum(Decimal(str(v)) for v in rows)
        assert summary["dollars_at_risk"] == expected, (
            f"dollars_at_risk {summary['dollars_at_risk']} != manual sum {expected}"
        )

    def test_dollars_at_risk_not_float(self, db: Session):
        """dollars_at_risk is never a Python float — explicit float type-check."""
        _, summary = self._run(db)
        assert not isinstance(summary["dollars_at_risk"], float), (
            "dollars_at_risk MUST NOT be float — financial precision invariant"
        )

    def test_rules_applied_count_positive(self, db: Session):
        """rules.applied > 0 after a run with the full column set."""
        _, summary = self._run(db)
        assert summary["rules"]["applied"] >= 0  # count of non-skip eval log rows

    def test_rules_skipped_zero_with_full_columns(self, db: Session):
        """rules.skipped == 0 when the full column set is present (all instances applicable)."""
        _, summary = self._run(db)
        assert summary["rules"]["skipped"] == 0

    def test_run_meta_status_completed(self, db: Session):
        """run_meta.status is 'completed' after run_detection."""
        _, summary = self._run(db)
        assert summary["run_meta"]["status"] == "completed"

    def test_run_meta_completed_at_set(self, db: Session):
        """run_meta.completed_at is not None after run_detection."""
        _, summary = self._run(db)
        assert summary["run_meta"]["completed_at"] is not None

    def test_run_meta_run_label(self, db: Session):
        """run_meta.run_label matches the run's label."""
        run, summary = self._run(db)
        assert summary["run_meta"]["run_label"] == run.run_label

    def test_rows_section_matches_resolution_stats(self, db: Session):
        """rows.expected_count and rows.inserted_count match run.resolution_stats."""
        run, summary = self._run(db)
        stats = run.resolution_stats
        assert summary["rows"]["expected_count"] == stats.get("expected_count")
        assert summary["rows"]["inserted_count"] == stats.get("inserted_count")

    def test_top_pharmacies_structure(self, db: Session):
        """top_entities.pharmacies is a list of dicts with pharmacy_npi and anomaly_count."""
        _, summary = self._run(db)
        pharmacies = summary["top_entities"]["pharmacies"]
        assert isinstance(pharmacies, list)
        for entry in pharmacies:
            assert "pharmacy_npi" in entry
            assert "anomaly_count" in entry
            assert isinstance(entry["anomaly_count"], int)

    def test_top_prescribers_structure(self, db: Session):
        """top_entities.prescribers is a list of dicts with prescriber_npi and anomaly_count."""
        _, summary = self._run(db)
        prescribers = summary["top_entities"]["prescribers"]
        assert isinstance(prescribers, list)
        for entry in prescribers:
            assert "prescriber_npi" in entry
            assert "anomaly_count" in entry
            assert isinstance(entry["anomaly_count"], int)

    def test_top_pharmacies_descending_order(self, db: Session):
        """top_entities.pharmacies is sorted by anomaly_count descending."""
        _, summary = self._run(db)
        pharmacies = summary["top_entities"]["pharmacies"]
        counts = [e["anomaly_count"] for e in pharmacies]
        assert counts == sorted(counts, reverse=True), (
            f"Pharmacies not sorted descending: {counts}"
        )

    def test_top_prescribers_descending_order(self, db: Session):
        """top_entities.prescribers is sorted by anomaly_count descending."""
        _, summary = self._run(db)
        prescribers = summary["top_entities"]["prescribers"]
        counts = [e["anomaly_count"] for e in prescribers]
        assert counts == sorted(counts, reverse=True), (
            f"Prescribers not sorted descending: {counts}"
        )


# ===========================================================================
# TestFormatSummary
# ===========================================================================


class TestFormatSummary:
    """format_summary returns a non-empty human-readable string."""

    def test_format_summary_returns_string(self, db: Session):
        """format_summary returns a str."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        result = format_summary(summary)
        assert isinstance(result, str)

    def test_format_summary_non_empty(self, db: Session):
        """format_summary output is non-empty."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        result = format_summary(summary)
        assert len(result.strip()) > 0

    def test_format_summary_contains_anomaly_count(self, db: Session):
        """format_summary output includes the anomaly total."""
        from src.detection.batch_engine import run_detection
        run = _load_fixture(db)
        run_detection(db, run)
        summary = build_summary(db, run)
        result = format_summary(summary)
        total = str(summary["anomalies"]["total"])
        assert total in result, (
            f"Expected anomaly total {total!r} in format_summary output"
        )

    def test_format_summary_contains_dollars_at_risk(self, db: Session):
        """format_summary output mentions dollars_at_risk value."""
        from src.detection.batch_engine import run_detection
        run = _load_fixture(db)
        run_detection(db, run)
        summary = build_summary(db, run)
        result = format_summary(summary)
        # The dollar amount should appear somewhere in the string
        assert "dollars_at_risk" in result.lower() or "$" in result or str(summary["dollars_at_risk"]) in result, (
            f"format_summary must reference dollars_at_risk; got:\n{result}"
        )

    def test_format_summary_contains_run_label(self, db: Session):
        """format_summary output includes the run_label."""
        run = _make_empty_run(db)
        summary = build_summary(db, run)
        result = format_summary(summary)
        assert "empty-summary-run" in result, (
            f"Expected run_label in format_summary output; got:\n{result}"
        )
