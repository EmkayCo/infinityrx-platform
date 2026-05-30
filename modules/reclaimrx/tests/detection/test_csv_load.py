"""Task 2.4 — Streaming chunked CSV loader tests.

Planted fixture: modules/reclaimrx/tests/detection/fixtures/sample_claims.csv
  54 data rows, 75 columns.

  Pattern summary:
    Rows 1-3  (AUTHHASH001A/B/C): DUPLICATE cluster — same PTHASH001+NDC+DOS, B1 Paid.
              DUP-001 rule fires in Phase 3.
    Rows 4-6  (AUTHHASH002A/B/C): BILL-REVERSE-REBILL — PTHASH002+NDC+DOS shared;
              B1 Paid @100 -> B2 Reversal @-100 -> B1 Paid @150 within 14 days.
              BRB-001 rule fires in Phase 3.
    Row 7     (AUTHHASH003): NQ-INFLATION — (215.17+1.50)/186.19 = 1.1637 > 1.10.
              MFR-001 rule fires in Phase 3.
    Row 8     (AUTHHASH004): NON-INFLATION — (186.50+0)/171.50 = 1.0875 < 1.10.
              No MFR-001 flag.
    Rows 9-10 (AUTHHASH005/006): NULL-NDC — pharmacy_npi present -> resolution='declared';
              ndc-needing rules won't apply.
    Row 11    (AUTHHASH007): GARBAGE DOS — date_of_service=9999-09-09 -> parse_dos=None
              -> resolution_method='unmapped', note='invalid DOS'.
    Rows 12-19 (AUTHHASH008-015): MULTI-STATE PRESCRIBER — prescriber_npi=8887776661
              appears in 8 distinct patient_state values (TX,CA,NY,FL,OH,GA,NC,IL).
              TH-002 requires >10 states to fire; with 8 states here TH-002 will NOT fire
              on this fixture alone. Planted to exercise the data shape.
    Rows 20-54 (AUTHHASH016-050): ORDINARY Paid claims — valid data, no anomalies.

  Unmapped rows (counted in tests):
    - Row 11 (AUTHHASH007): invalid DOS -> unmapped (1 row)
  Declared rows:
    - All 53 remaining rows have pharmacy_npi present -> declared

Advisory locks (pg_advisory_xact_lock) are Postgres-only. The load_csv logic
is fully testable on SQLite: the advisory lock is patched out when creating
the run, and load_csv itself never calls the advisory lock.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TENANT_A = uuid.UUID("11111111-1111-1111-1111-111111111111")
_SYS_UID = uuid.UUID("00000000-0000-0000-0000-000000000001")

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "sample_claims.csv"
)

# The fixture has 54 data rows (see module docstring for breakdown).
_EXPECTED_ROWS = 54

# 1 unmapped row: AUTHHASH007 with garbage DOS 9999-09-09.
_EXPECTED_UNMAPPED = 1
_EXPECTED_DECLARED = _EXPECTED_ROWS - _EXPECTED_UNMAPPED


# ---------------------------------------------------------------------------
# Helper: create a DetectionRun without the advisory lock
# ---------------------------------------------------------------------------


def _make_run(db):
    """Return an in_progress DetectionRun for the fixture CSV, bypassing advisory lock."""
    from src.detection.csv_ingest import create_or_resume_run

    with patch("src.detection.csv_ingest._acquire_advisory_lock", return_value=None):
        return create_or_resume_run(
            db,
            tenant_id=_TENANT_A,
            path=str(_FIXTURE_PATH),
            created_by=_SYS_UID,
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoadCsvFullCoverage:
    """load_csv inserts all rows and sets resolution stats correctly."""

    def test_load_csv_returns_row_count(self, db):
        """load_csv returns the number of rows inserted."""
        from src.detection.csv_ingest import load_csv

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        assert n == _EXPECTED_ROWS

    def test_inserted_count_equals_expected_count(self, db):
        """After load_csv, inserted_count == expected_count (full-coverage gate satisfied)."""
        from src.detection.csv_ingest import load_csv

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        assert run.resolution_stats["inserted_count"] == run.resolution_stats["expected_count"]
        assert run.resolution_stats["inserted_count"] == n

    def test_csv_upload_rows_count_equals_n(self, db):
        """CsvUploadRow table has exactly n rows for this run after load_csv."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        row_count = (
            db.query(CsvUploadRow)
            .filter(CsvUploadRow.detection_run_id == run.id)
            .count()
        )
        assert row_count == n

    def test_declared_plus_unmapped_equals_n(self, db):
        """declared + unmapped == total rows inserted."""
        from src.detection.csv_ingest import load_csv

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        stats = run.resolution_stats
        assert stats["declared"] + stats["unmapped"] == n

    def test_unmapped_count_matches_expected(self, db):
        """Exactly 1 row is unmapped: the garbage-DOS row (AUTHHASH007)."""
        from src.detection.csv_ingest import load_csv

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        assert run.resolution_stats["unmapped"] == _EXPECTED_UNMAPPED
        assert run.resolution_stats["declared"] == _EXPECTED_DECLARED

    def test_garbage_dos_row_is_unmapped(self, db):
        """Row with date_of_service=9999-09-09 gets resolution_method='unmapped'."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        # Row 11 in the fixture is the garbage-DOS row (1-based row_number == 11).
        garbage_row = (
            db.query(CsvUploadRow)
            .filter(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.row_number == 11,
            )
            .one()
        )
        assert garbage_row.resolution_method == "unmapped"
        assert garbage_row.resolution_notes is not None
        assert "invalid DOS" in garbage_row.resolution_notes

    def test_null_ndc_rows_are_declared(self, db):
        """Rows 9 and 10 have empty NDC but valid pharmacy_npi -> declared."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        null_ndc_rows = (
            db.query(CsvUploadRow)
            .filter(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.resolved_ndc.is_(None),
            )
            .all()
        )
        # The garbage-DOS row (row 11) also has NDC but its resolution is unmapped.
        # Rows 9 and 10 have empty NDC and valid NPI -> declared.
        declared_null_ndc = [r for r in null_ndc_rows if r.resolution_method == "declared"]
        assert len(declared_null_ndc) == 2

    def test_row_numbers_are_monotonic_and_one_based(self, db):
        """row_number is 1-based and contiguous across all inserted rows."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        row_numbers = sorted(
            r.row_number
            for r in db.query(CsvUploadRow)
            .filter(CsvUploadRow.detection_run_id == run.id)
            .all()
        )
        assert row_numbers == list(range(1, n + 1))

    def test_row_data_contains_all_75_columns(self, db):
        """Every row_data JSONB dict has exactly 75 keys (all header columns)."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        first_row = (
            db.query(CsvUploadRow)
            .filter(CsvUploadRow.detection_run_id == run.id, CsvUploadRow.row_number == 1)
            .one()
        )
        assert len(first_row.row_data) == 75

    def test_tenant_id_set_on_all_rows(self, db):
        """All CsvUploadRow records carry the run's tenant_id."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=10)
        wrong_tenant = (
            db.query(CsvUploadRow)
            .filter(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.tenant_id != _TENANT_A,
            )
            .count()
        )
        assert wrong_tenant == 0

    def test_chunk_size_does_not_affect_total_count(self, db):
        """load_csv with chunk_size=1 inserts same count as chunk_size=100."""
        from src.detection.csv_ingest import create_or_resume_run, load_csv

        # First run: chunk_size=1
        run1 = _make_run(db)
        n1 = load_csv(db, run1, chunk_size=1)

        # Mark run1 completed so the second call creates a fresh run.
        run1.status = "completed"
        db.flush()

        # Second run on the same file with force=True: chunk_size=100
        with __import__("unittest.mock", fromlist=["patch"]).patch(
            "src.detection.csv_ingest._acquire_advisory_lock", return_value=None
        ):
            run2 = create_or_resume_run(
                db,
                tenant_id=_TENANT_A,
                path=str(_FIXTURE_PATH),
                created_by=_SYS_UID,
                force=True,
            )
        n2 = load_csv(db, run2, chunk_size=100)

        assert n1 == n2 == _EXPECTED_ROWS

    def test_by_reason_tracks_invalid_dos(self, db):
        """resolution_stats['by_reason'] contains an 'invalid DOS' entry."""
        from src.detection.csv_ingest import load_csv

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        by_reason = run.resolution_stats.get("by_reason", {})
        assert "invalid DOS" in by_reason
        assert by_reason["invalid DOS"] == 1


class TestLoadCsvStreaming:
    """load_csv never loads the whole file into memory — verified via chunk_size=1."""

    def test_tiny_chunk_size_still_inserts_all_rows(self, db):
        """chunk_size=1 forces flush after every row; all rows still inserted."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        n = load_csv(db, run, chunk_size=1)
        assert n == _EXPECTED_ROWS
        db_count = (
            db.query(CsvUploadRow)
            .filter(CsvUploadRow.detection_run_id == run.id)
            .count()
        )
        assert db_count == n


class TestLoadCsvResolutionMethodValues:
    """resolution_method values written to DB satisfy the CHECK constraint."""

    _ALLOWED = {"declared", "group_id_lookup", "ndc_lookup", "manual", "unmapped"}

    def test_all_resolution_methods_are_valid(self, db):
        """Every CsvUploadRow.resolution_method is in the allowed set."""
        from src.detection.csv_ingest import load_csv
        from src.models.detection_run_models import CsvUploadRow

        run = _make_run(db)
        load_csv(db, run, chunk_size=10)
        all_rows = (
            db.query(CsvUploadRow)
            .filter(CsvUploadRow.detection_run_id == run.id)
            .all()
        )
        for row in all_rows:
            assert row.resolution_method in self._ALLOWED, (
                f"row {row.row_number}: invalid resolution_method={row.resolution_method!r}"
            )
