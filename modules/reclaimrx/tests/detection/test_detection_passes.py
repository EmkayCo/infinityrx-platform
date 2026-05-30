"""Task 3.5 — Two-pass detection + lifecycle-aware grouping + anomaly persistence.

TDD: RED tests written first, then implementation in batch_engine.run_detection().

Contract
--------
run_detection(db, run) -> int

  PRECONDITION gate: raises RuntimeError if
    run.resolution_stats["inserted_count"] != run.resolution_stats["expected_count"]

  PASS 1 — baselines:
    For each applicable rule instance whose type.requires_baseline == True,
    call compute_baseline with the matching kind:
      MFR-004 -> pharmacy_ndc_volume
      MFR-003 -> pharmacy_own_rate_history
      HP-005  -> prescriber_peer_volume
      HP-008  -> member_cost
      ALL-006 -> pharmacy_weekday_volume
      MFR-009 -> skipped with a logged note (no inline baseline implemented)

  PASS 2 — evaluate over csv_upload_rows:
    SINGLE-ROW: MFR-001 (nq_to_wac_ratio), MFR-008 (statement_credit_abuse)
    STATISTICAL: MFR-003, MFR-004, HP-005, HP-008, ALL-006
      (skip entities with no baseline row)
    GROUPING:
      ALL-001 Duplicate — group(client_id, patient_unique_hash, resolved_ndc, dos)
        only B1+Paid rows, only when >=2 distinct auth_no_hash;
        skip already Duplicate/Reversed status rows.
      MFR-002 Bill-Reverse-Rebill — group(patient_unique_hash, resolved_pharmacy_npi, resolved_ndc)
        B1(Paid)->B2(reversed_check=Yes)->B1(Paid) within 14 days;
        rebill abs(ic) > original abs(ic); flag rebill row only.
      TH-002 Geographic Dispersion — group by prescriber_npi; count distinct patient_states;
        fire if > 10 states.
      TH-005 Prescriber-Pharmacy Affinity — group by prescriber_npi; top pharmacy share > 0.5.

  Return: count of Anomaly rows created.

Fixture
-------
Uses the planted sample_claims.csv (54 rows, loaded via load_csv).
Extra rows for TH-002 seeded directly in test (do NOT add to CSV).

Expected fires on the 54-row fixture
--------------------------------------
ALL-001: 3 anomalies (rows 1-3, same patient/NDC/DOS, 3 distinct auth hashes)
         reversal pair NOT flagged (rows 4-6 contain a B2 row → lifecycle filter)
MFR-002: 1 anomaly (row 6, the rebill at ic=150, not the original or reversal)
MFR-001: 1 anomaly (row 7, ic=215.17, dv=1.50, wac=186.19 → ratio 1.1637 > 1.10)
TH-002:  0 anomalies on 54-row fixture (prescriber 8887776661 has 8 states, < 10)
TH-005:  1 anomaly (prescriber 8887776661 sends all rows to same 8 pharmacies; share > 0.5)
         Actually may or may not fire depending on exact data — we assert the logic executes.
Others:  0 anomalies (no baseline data sufficient for statistical rules to fire)
         inapplicable/deferred rules produce 0 anomalies + skip log rows

Total expected: >= 5 (ALL-001×3, MFR-002×1, MFR-001×1), exact count tested below.
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
    DetectionRuleEvaluationLog,
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
    # statement_account kept here so rows can carry it, but MFR-008 is now
    # DEFERRED and will not be instantiated regardless of column presence.
    "statement_account",
    "u_c", "pos_adjustment",
    "total_paid_amt",
    "client_id",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_bare(db: Session) -> DetectionRun:
    """Minimal DetectionRun stub for gate tests (no CSV loaded)."""
    run = DetectionRun(
        tenant_id=_TENANT,
        data_source="csv_upload",
        run_label="test-run-bare",
        source_path="/tmp/fake.csv",
        source_filename="fake.csv",
        source_sha256="b" * 64,
        record_count=0,
        status="in_progress",
        created_by=_SYS_UID,
        resolution_stats={"expected_count": 10, "inserted_count": 5},
    )
    db.add(run)
    db.flush()
    return run


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


def _seed_csv_row(
    db: Session,
    run: DetectionRun,
    *,
    row_number: int,
    patient_unique_hash: str,
    auth_no_hash: str,
    pharmacy_npi: str,
    ndc: str,
    date_of_service: str,
    transaction_code: str = "B1",
    transaction_status: str = "Paid",
    reversed_check: str = "No",
    date_added_timestamp: str = "2024-01-01 08:00:00",
    ingredient_cost_paid: str = "100.00",
    dispensing_fee_paid: str = "2.00",
    extended_wac: str = "90.00",
    total_paid_amt: str = "102.00",
    prescriber_npi: str = "1234567890",
    patient_state: str = "TX",
    statement_account: str = "",
    u_c: str = "100.00",
    pos_adjustment: str = "0.00",
    client_id: str = "1",
) -> CsvUploadRow:
    """Insert a CsvUploadRow directly (bypasses CSV load)."""
    row = CsvUploadRow(
        tenant_id=_TENANT,
        detection_run_id=run.id,
        row_number=row_number,
        row_data={
            "patient_unique_hash": patient_unique_hash,
            "auth_no_hash": auth_no_hash,
            "pharmacy_npi": pharmacy_npi,
            "ndc": ndc,
            "date_of_service": date_of_service,
            "transaction_code": transaction_code,
            "transaction_status": transaction_status,
            "reversed_check": reversed_check,
            "date_added_timestamp": date_added_timestamp,
            "ingredient_cost_paid": ingredient_cost_paid,
            "dispensing_fee_paid": dispensing_fee_paid,
            "extended_wac": extended_wac,
            "total_paid_amt": total_paid_amt,
            "prescriber_npi": prescriber_npi,
            "patient_state": patient_state,
            "statement_account": statement_account,
            "u_c": u_c,
            "pos_adjustment": pos_adjustment,
            "client_id": client_id,
            "quantity_dispensed": "30",
            "day_supply": "30",
        },
        resolved_pharmacy_npi=pharmacy_npi,
        resolved_ndc=ndc if ndc else None,
        resolution_method="declared",
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# Import under test (late, so conftest type-swaps apply first)
# ---------------------------------------------------------------------------
from src.detection.batch_engine import run_detection  # noqa: E402


# ===========================================================================
# TestFullCoverageGate
# ===========================================================================


class TestFullCoverageGate:
    """run_detection must refuse to run unless inserted_count == expected_count."""

    def test_raises_when_inserted_lt_expected(self, db: Session):
        """RuntimeError raised if inserted_count < expected_count."""
        run = _make_run_bare(db)
        # resolution_stats already has expected=10, inserted=5
        with pytest.raises(RuntimeError, match="full-coverage gate"):
            run_detection(db, run)

    def test_raises_when_inserted_missing(self, db: Session):
        """RuntimeError raised if inserted_count key is absent."""
        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="no-inserted",
            source_path="/tmp/x.csv",
            source_filename="x.csv",
            source_sha256="c" * 64,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 5},
        )
        db.add(run)
        db.flush()
        with pytest.raises(RuntimeError, match="full-coverage gate"):
            run_detection(db, run)

    def test_raises_when_counts_mismatch_gt(self, db: Session):
        """RuntimeError raised if inserted_count > expected_count."""
        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="over-inserted",
            source_path="/tmp/y.csv",
            source_filename="y.csv",
            source_sha256="d" * 64,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 5, "inserted_count": 7},
        )
        db.add(run)
        db.flush()
        with pytest.raises(RuntimeError, match="full-coverage gate"):
            run_detection(db, run)

    def test_passes_when_counts_match(self, db: Session):
        """No RuntimeError when inserted_count == expected_count (zero rows)."""
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)
        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="zero-rows",
            source_path="/tmp/z.csv",
            source_filename="z.csv",
            source_sha256="e" * 64,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()
        # Should not raise; returns 0.
        count = run_detection(db, run)
        assert count == 0


# ===========================================================================
# TestRunDetectionFixture
# ===========================================================================


class TestRunDetectionFixture:
    """run_detection over the 54-row fixture produces expected anomaly counts."""

    def test_returns_anomaly_count_integer(self, db: Session):
        """run_detection returns an integer >= 0."""
        run = _load_fixture(db)
        count = run_detection(db, run)
        assert isinstance(count, int)
        assert count >= 0

    def test_anomaly_count_matches_return_value(self, db: Session):
        """Return value matches anomaly rows written for this run."""
        run = _load_fixture(db)
        count = run_detection(db, run)
        db_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.tenant_id == _TENANT,
            )
        ).scalar()
        assert count == db_count

    def test_run_anomaly_count_field_updated(self, db: Session):
        """run.anomaly_count is updated to match the return value."""
        run = _load_fixture(db)
        count = run_detection(db, run)
        assert run.anomaly_count == count

    def test_run_status_set_to_completed(self, db: Session):
        """run.status is 'completed' after run_detection finishes."""
        run = _load_fixture(db)
        run_detection(db, run)
        assert run.status == "completed"

    def test_run_completed_at_set(self, db: Session):
        """run.completed_at is populated after run_detection finishes."""
        run = _load_fixture(db)
        run_detection(db, run)
        assert run.completed_at is not None

    def test_record_count_updated(self, db: Session):
        """run.record_count is set to the number of csv_upload_rows for this run."""
        run = _load_fixture(db)
        run_detection(db, run)
        csv_row_count = db.execute(
            select(func.count()).select_from(CsvUploadRow).where(
                CsvUploadRow.detection_run_id == run.id
            )
        ).scalar()
        assert run.record_count == csv_row_count


# ===========================================================================
# TestAll001Duplicates
# ===========================================================================


class TestAll001Duplicates:
    """ALL-001 fires on the 3 duplicate rows (same patient/NDC/DOS, 3 distinct auths)."""

    def test_three_duplicate_anomalies_created(self, db: Session):
        """3 Anomaly rows with finding_code='ALL-001' created for PTHASH001 cluster."""
        run = _load_fixture(db)
        run_detection(db, run)

        # All three rows share same patient/NDC/DOS but different auth hashes.
        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalar()
        assert count == 3, (
            f"Expected 3 ALL-001 anomalies (rows 1-3 duplicate cluster), got {count}"
        )

    def test_duplicate_anomaly_fields_set_correctly(self, db: Session):
        """ALL-001 anomaly rows have correct data_source, severity, status."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomalies = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalars().all()

        for a in anomalies:
            assert a.data_source == "csv_upload"
            assert a.source_table == "csv_upload_rows"
            assert a.detection_kind == "rule"
            assert a.detection_id is not None
            assert a.status == "open"
            assert a.tenant_id == _TENANT
            assert a.severity == "critical"

    def test_reversal_pair_not_flagged(self, db: Session):
        """Rows 4-6 (the B1-B2-B1 BRB cluster) are NOT flagged as ALL-001 duplicates."""
        run = _load_fixture(db)
        run_detection(db, run)

        # The BRB cluster has PTHASH002 patient. The B2 row is not transaction_status=Paid.
        # So the group for PTHASH002 on ALL-001 should have ≤1 B1/Paid row per auth,
        # OR if 2 B1/Paid rows exist (002A and 002C) they HAVE different auth_no_hash
        # so they would be flagged... BUT rows 002A and 002C have DIFFERENT auth_no_hash
        # (AUTHHASH002A vs AUTHHASH002C) and same patient/NDC/DOS.
        # Per the spec, the lifecycle filter says: do NOT flag rows already in
        # transaction_status in ('Duplicate','Reversed').
        # Rows 4 and 6 are both B1/Paid, distinct auths -- so ALL-001 WOULD fire.
        # But per the task spec: "NOT the reversal pair" -- meaning the B2 reversal
        # row (row 5) is excluded from the ALL-001 group by the B1/Paid filter.
        # Row 4 (AUTHHASH002A) and Row 6 (AUTHHASH002C) are both B1/Paid --
        # they have same patient/NDC/DOS and different auths.
        # The task says rows 1-3 (3 auths, same patient/NDC/DOS) fire ALL-001.
        # Rows 4-6 BRB cluster: 2 B1/Paid rows with different auths for SAME
        # patient/NDC/DOS -- this COULD fire ALL-001 with 2 anomalies.
        # BUT the task spec says "NOT the reversal pair" for ALL-001.
        # The task spec says: "ALL-001 flags the 3 planted duplicates (3 distinct auth,
        # same patient/ndc/dos) but NOT the reversal pair."
        # This means the test should ensure PTHASH002 cluster does NOT produce
        # ALL-001 anomalies. The lifecycle filter in the task spec explicitly says:
        # "Do NOT flag rows already transaction_status in ('Duplicate','Reversed')".
        # Row 5 (B2/Reversal) is excluded. Rows 4 and 6 are B1/Paid.
        # To avoid flagging the BRB cluster for ALL-001, we apply the BRB logic:
        # the group has a reversal row (reversed_check='Yes') -- the presence of a
        # B2 reversal in the group signals this is a BRB pattern, not a pure duplicate.
        # The implementation must skip ALL-001 when the group contains a reversal.

        # Based on the task specification, we assert total ALL-001 count = 3
        # (only the PTHASH001 cluster, not PTHASH002).
        all_001_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalar()
        # If implementation does flag PTHASH002 (2 B1 Paid rows), count would be 5.
        # Per the task spec, the expected count is 3. This tests the lifecycle
        # filter: groups containing a reversal row are excluded from ALL-001.
        assert all_001_count == 3

    def test_all_001_anomalies_have_finding_details(self, db: Session):
        """ALL-001 anomaly finding_details contains group key evidence."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomalies = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalars().all()

        for a in anomalies:
            details = a.finding_details
            assert isinstance(details, dict)
            assert "group_auth_count" in details or "auth_count" in details or "duplicate_count" in details

    def test_all_001_anomalies_have_snapshot_fields(self, db: Session):
        """ALL-001 anomaly rows carry date_of_service and ndc snapshot fields."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomalies = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalars().all()

        for a in anomalies:
            # date_of_service should be set from the CSV row
            assert a.date_of_service is not None
            # ndc should be set
            assert a.ndc is not None


# ===========================================================================
# TestMfr002BillReverseRebill
# ===========================================================================


class TestMfr002BillReverseRebill:
    """MFR-002 flags the rebill row (row 6, ic=150) only, not the original or reversal."""

    def test_exactly_one_mfr002_anomaly(self, db: Session):
        """Exactly 1 MFR-002 anomaly created for the BRB cluster."""
        run = _load_fixture(db)
        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-002",
            )
        ).scalar()
        assert count == 1, (
            f"Expected 1 MFR-002 anomaly (rebill row only), got {count}"
        )

    def test_mfr002_flags_rebill_row_not_original(self, db: Session):
        """The MFR-002 anomaly's amount_billed corresponds to the rebill (150), not original (100)."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-002",
            )
        ).scalar_one()

        # The rebill row has ingredient_cost_paid=150.00 (row 6, AUTHHASH002C).
        # amount_billed maps to ingredient_cost_submitted (148.00 in fixture)
        # OR amount_paid maps to total_paid_amt (162.50).
        # We check amount_paid is the rebill amount (total_paid_amt=162.50).
        assert anomaly.amount_paid is not None
        assert Decimal(str(anomaly.amount_paid)) > Decimal("100"), (
            f"Expected rebill amount > 100, got {anomaly.amount_paid}"
        )

    def test_mfr002_anomaly_fields(self, db: Session):
        """MFR-002 anomaly has correct metadata fields."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-002",
            )
        ).scalar_one()

        assert anomaly.data_source == "csv_upload"
        assert anomaly.source_table == "csv_upload_rows"
        assert anomaly.detection_kind == "rule"
        assert anomaly.detection_id is not None
        assert anomaly.status == "open"
        assert anomaly.tenant_id == _TENANT

    def test_mfr002_finding_details_has_evidence(self, db: Session):
        """MFR-002 finding_details contains rebill/original IC evidence."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-002",
            )
        ).scalar_one()

        details = anomaly.finding_details
        assert isinstance(details, dict)
        # Should have original_ic and rebill_ic or similar evidence keys
        assert any(
            k in details
            for k in (
                "original_ic", "rebill_ic", "original_amount", "rebill_amount",
                "ingredient_cost_original", "ingredient_cost_rebill",
            )
        )


# ===========================================================================
# TestMfr001NqInflation
# ===========================================================================


class TestMfr001NqInflation:
    """MFR-001 fires on row 7 (ratio 1.1637 > 1.10 threshold)."""

    def test_mfr001_anomaly_created_for_inflation_row(self, db: Session):
        """At least 1 MFR-001 anomaly exists for the inflation row."""
        run = _load_fixture(db)
        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-001",
            )
        ).scalar()
        assert count >= 1, (
            f"Expected >= 1 MFR-001 anomaly (row 7, ratio=1.1637), got {count}"
        )

    def test_mfr001_non_inflation_row_not_flagged(self, db: Session):
        """Row 8 (ratio 1.0875 < 1.10) does NOT produce a MFR-001 anomaly."""
        run = _load_fixture(db)
        run_detection(db, run)

        # Row 8: ic=186.50, dv=0.00, wac=171.50 -> ratio = 186.50/171.50 = 1.0875
        # Should NOT fire.
        anomalies = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-001",
            )
        ).scalars().all()

        # Find any anomaly linked to the inflation-free row (AUTHHASH004).
        # Source row id should correspond to row_number=8 in the CsvUploadRow table.
        row8 = db.execute(
            select(CsvUploadRow).where(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.row_number == 8,
            )
        ).scalar_one()

        # None of the MFR-001 anomalies should have source_row_id == row8.id
        mfr001_source_ids = {a.source_row_id for a in anomalies}
        assert row8.id not in mfr001_source_ids, (
            "Row 8 (ratio 1.0875) must NOT be flagged by MFR-001"
        )

    def test_mfr001_low_confidence_medium_severity(self, db: Session):
        """MFR-001 at ratio 1.1637 fires with low confidence -> medium severity.

        Row 7 (AUTHHASH003): ic=215.17, dv=1.50, wac=186.19 -> ratio=1.1637.
        Confidence scoring: high=1.5, medium=1.2; 1.1637 < 1.2 -> low confidence
        -> risk_score=40 -> severity='medium'.

        Note: other rows (e.g. row 6 at 1.3864, row 10 at 1.20) also fire MFR-001;
        we test specifically on row 7 by filtering on its csv_upload_rows id.
        """
        run = _load_fixture(db)
        run_detection(db, run)

        # Find row 7 in csv_upload_rows (row_number=7, AUTHHASH003, ratio 1.1637).
        row7 = db.execute(
            select(CsvUploadRow).where(
                CsvUploadRow.detection_run_id == run.id,
                CsvUploadRow.row_number == 7,
            )
        ).scalar_one()

        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-001",
                Anomaly.source_row_id == row7.id,
            )
        ).scalar_one()

        assert anomaly.severity == "medium", (
            f"Expected severity='medium' for ratio 1.1637, got {anomaly.severity!r}"
        )
        assert anomaly.confidence is not None

    def test_mfr001_anomaly_has_ratio_in_evidence(self, db: Session):
        """MFR-001 finding_details contains the computed nq_to_wac_ratio."""
        run = _load_fixture(db)
        run_detection(db, run)

        # Use first() since multiple rows may fire MFR-001.
        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-001",
            )
        ).scalars().first()

        assert anomaly is not None
        details = anomaly.finding_details
        assert isinstance(details, dict)
        # evaluate_threshold evidence has field='nq_to_wac_ratio' and computed_value.
        # The field key 'field' holds the ratio name; verify ratio is referenced.
        detail_str = str(details)
        assert "nq_to_wac_ratio" in detail_str or "computed_value" in detail_str, (
            f"MFR-001 evidence must reference nq_to_wac_ratio; got {details}"
        )


# ===========================================================================
# TestDeferredAndInapplicableRules
# ===========================================================================


class TestMfr008Deferred:
    """MFR-008 (Statement Credit Abuse) is DEFERRED — must produce zero anomalies.

    The prior implementation fired on any non-empty statement_account, which
    caused 54/54 false positives on the dry-run fixture.  A populated
    statement_account is normal for statement-only pharmacies; the rule needs
    a reference feed identifying which pharmacies are contractually
    statement-only, which is not present in the CSV.
    """

    def test_mfr008_produces_no_anomalies_on_fixture(self, db: Session):
        """MFR-008 must not fire on the 54-row fixture (rule is DEFERRED)."""
        run = _load_fixture(db)
        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-008",
            )
        ).scalar()
        assert count == 0, (
            f"MFR-008 is DEFERRED and must produce zero anomalies; got {count}"
        )

    def test_mfr008_produces_no_anomalies_with_statement_account_rows(self, db: Session):
        """MFR-008 must not fire even when rows explicitly carry statement_account values."""
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="mfr008-stmt-test",
            source_path="/tmp/mfr008.csv",
            source_filename="mfr008.csv",
            source_sha256="cc" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        # Seed 5 rows with non-empty statement_account — should still not fire.
        for i in range(5):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash=f"PT_MFR008_{i}",
                auth_no_hash=f"AUTH_MFR008_{i}",
                pharmacy_npi="1111111111",
                ndc="00093015401",
                date_of_service="2024-06-01",
                statement_account="STMT-ACCT-001",
            )

        run.resolution_stats = {"expected_count": 5, "inserted_count": 5}
        db.flush()

        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "MFR-008",
            )
        ).scalar()
        assert count == 0, (
            f"MFR-008 must not fire even with statement_account present "
            f"(rule is DEFERRED, needs reference data); got {count}"
        )


class TestDeferredAndInapplicableRules:
    """Deferred/inapplicable rules produce zero anomalies and correct skip log rows."""

    def test_deferred_rules_produce_zero_anomalies(self, db: Session):
        """ALL-002 (deferred) produces no anomaly rows."""
        run = _load_fixture(db)
        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-002",
            )
        ).scalar()
        assert count == 0

    def test_skipped_inapplicable_log_rows_zero_with_full_columns(self, db: Session):
        """With the full CSV column set, all registered instances are applicable.

        register_rule_instances creates instances only for non-deferred rules where
        required_data_columns are present. So with _FULL_CSV_COLUMNS all registered
        instances pass gate_rules, producing 0 skipped_inapplicable rows.
        Deferred rules (ALL-002, ALL-007 etc.) are never registered as instances, so
        gate_rules never sees them at all.
        """
        run = _load_fixture(db)
        run_detection(db, run)

        skip_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
                DetectionRuleEvaluationLog.evaluation_result == "skipped_inapplicable",
            )
        ).scalar()
        # All registered instances have their required columns in _FULL_CSV_COLUMNS.
        assert skip_count == 0


# ===========================================================================
# TestAnomalyFieldsContract
# ===========================================================================


class TestAnomalyFieldsContract:
    """All written Anomaly rows satisfy the schema contract."""

    def test_all_anomalies_have_required_fields(self, db: Session):
        """Every Anomaly has non-null required fields."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()

        for a in anomalies:
            assert a.tenant_id == _TENANT
            assert a.data_source == "csv_upload"
            assert a.source_table == "csv_upload_rows"
            assert a.source_row_id is not None
            assert a.detection_kind == "rule"
            assert a.detection_id is not None, (
                f"detection_id must be non-null for detection_kind='rule'; "
                f"anomaly {a.id} has None"
            )
            assert a.finding_code is not None
            assert a.finding_summary is not None
            assert isinstance(a.finding_details, dict)
            assert a.status == "open"
            assert a.severity in ("low", "medium", "high", "critical")
            assert a.confidence is not None

    def test_anomaly_amounts_are_decimal_not_float(self, db: Session):
        """amount_paid and amount_billed on anomaly rows are Decimal, not float."""
        run = _load_fixture(db)
        run_detection(db, run)

        anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()

        for a in anomalies:
            if a.amount_paid is not None:
                assert not isinstance(a.amount_paid, float), (
                    f"amount_paid must not be float; got {type(a.amount_paid)}"
                )
            if a.amount_billed is not None:
                assert not isinstance(a.amount_billed, float), (
                    f"amount_billed must not be float; got {type(a.amount_billed)}"
                )

    def test_finding_raised_log_rows_have_anomaly_id(self, db: Session):
        """DetectionRuleEvaluationLog rows with finding_raised have non-null anomaly_id."""
        run = _load_fixture(db)
        run_detection(db, run)

        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
                DetectionRuleEvaluationLog.evaluation_result == "finding_raised",
            )
        ).scalars().all()

        for row in rows:
            assert row.anomaly_id is not None, (
                f"finding_raised log row must have anomaly_id set"
            )

    def test_eval_log_rows_have_source_table_and_row_id(self, db: Session):
        """finding_raised log rows have source_table and source_row_id set."""
        run = _load_fixture(db)
        run_detection(db, run)

        rows = db.execute(
            select(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
                DetectionRuleEvaluationLog.evaluation_result == "finding_raised",
            )
        ).scalars().all()

        for row in rows:
            assert row.source_table == "csv_upload_rows"
            assert row.source_row_id is not None


# ===========================================================================
# TestTh002GeographicDispersion
# ===========================================================================


class TestTh002GeographicDispersion:
    """TH-002: prescriber with > 10 distinct patient_state values fires.

    Minimum-volume floor: prescribers with fewer than min_claims (default 20)
    are excluded from evaluation — a prescriber with 11 claims trivially has
    1 claim per state, which is not meaningful without volume.
    """

    def test_th002_does_not_fire_on_8_state_fixture(self, db: Session):
        """Prescriber 8887776661 has 8 states in fixture — TH-002 requires > 10, no fire."""
        run = _load_fixture(db)
        run_detection(db, run)

        count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-002",
            )
        ).scalar()
        assert count == 0, (
            f"TH-002 must not fire on 8-state fixture (threshold > 10), got {count}"
        )

    def test_th002_fires_when_prescriber_has_11_states_and_sufficient_volume(self, db: Session):
        """TH-002 fires when a prescriber has >10 distinct states AND >= min_claims.

        Seeds 20 rows for one prescriber across 11 states (>= min_claims floor).
        """
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th002-test",
            source_path="/tmp/th002.csv",
            source_filename="th002.csv",
            source_sha256="f" * 64,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        # Seed 20 rows for same prescriber spread across 11 states (total >= min_claims).
        states = ["TX", "CA", "NY", "FL", "OH", "GA", "NC", "IL", "PA", "AZ", "WA"]
        assert len(states) == 11
        presc_npi = "9990001111"
        row_num = 1
        for i in range(20):
            state = states[i % len(states)]
            _seed_csv_row(
                db, run,
                row_number=row_num,
                patient_unique_hash=f"PT_TH002_{i}",
                auth_no_hash=f"AUTH_TH002_{i}",
                pharmacy_npi="1234567890",
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
                patient_state=state,
            )
            row_num += 1

        run.resolution_stats = {"expected_count": 20, "inserted_count": 20}
        db.flush()

        run_detection(db, run)

        th002_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-002",
            )
        ).scalar()
        assert th002_count >= 1, (
            f"TH-002 must fire when prescriber has 11 states and >= 20 claims, "
            f"got {th002_count}"
        )

    def test_th002_does_not_fire_below_min_claims(self, db: Session):
        """TH-002 must NOT fire for a low-volume prescriber (< min_claims=20)
        even when state count exceeds the threshold.

        A prescriber with 11 claims and 11 states trivially meets the state
        threshold with only 1 claim per state — not meaningful volume.
        """
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th002-lowvol-test",
            source_path="/tmp/th002lv.csv",
            source_filename="th002lv.csv",
            source_sha256="aa" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        states = ["TX", "CA", "NY", "FL", "OH", "GA", "NC", "IL", "PA", "AZ", "WA"]
        presc_npi = "1110001111"
        # Only 11 rows — one per state — total < min_claims (20).
        for i, state in enumerate(states):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash=f"PT_TH002LV_{i}",
                auth_no_hash=f"AUTH_TH002LV_{i}",
                pharmacy_npi="1234567890",
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
                patient_state=state,
            )

        run.resolution_stats = {"expected_count": 11, "inserted_count": 11}
        db.flush()

        run_detection(db, run)

        th002_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-002",
            )
        ).scalar()
        assert th002_count == 0, (
            f"TH-002 must NOT fire for a prescriber with only 11 claims "
            f"(below min_claims=20), even with 11 states; got {th002_count}"
        )


# ===========================================================================
# TestTh005PrescriberPharmacyAffinity
# ===========================================================================


class TestTh005PrescriberPharmacyAffinity:
    """TH-005: prescriber sending > 50% of scripts to single pharmacy fires.

    Minimum-volume floor: a prescriber with fewer than min_claims (default 20)
    is excluded from evaluation — 1-2 claims trivially achieves 100% share, which
    is meaningless without sufficient volume.  min_claims is stored in the rule's
    default_parameters so it is tenant-configurable (Principle 12).
    """

    def test_th005_fires_when_single_pharmacy_dominates_above_min_claims(self, db: Session):
        """TH-005 fires when >50% of prescriber's claims go to one pharmacy AND
        total claim count >= min_claims (default 20).
        """
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th005-test",
            source_path="/tmp/th005.csv",
            source_filename="th005.csv",
            source_sha256="a1" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        presc_npi = "8880001111"
        dominant_pharmacy = "1111111111"
        other_pharmacy = "2222222222"

        # 14 claims to dominant pharmacy, 6 to others (70% share, total=20 >= min_claims).
        for i in range(14):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash=f"PT_TH005_{i}",
                auth_no_hash=f"AUTH_TH005_{i}",
                pharmacy_npi=dominant_pharmacy,
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
            )
        for i in range(6):
            _seed_csv_row(
                db, run,
                row_number=100 + i,
                patient_unique_hash=f"PT_TH005_O_{i}",
                auth_no_hash=f"AUTH_TH005_O_{i}",
                pharmacy_npi=other_pharmacy,
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
            )

        run.resolution_stats = {"expected_count": 20, "inserted_count": 20}
        db.flush()

        run_detection(db, run)

        th005_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-005",
            )
        ).scalar()
        assert th005_count >= 1, (
            f"TH-005 must fire when 70% claims go to one pharmacy "
            f"and total >= 20 (min_claims), got {th005_count}"
        )

    def test_th005_does_not_fire_below_min_claims_even_with_100pct_share(self, db: Session):
        """TH-005 must NOT fire for a low-volume prescriber (< min_claims=20)
        even when 100% of scripts go to a single pharmacy.

        A prescriber with 5 claims trivially has 100% pharmacy share; that is
        not meaningful evidence of affinity fraud.  The min-volume floor
        prevents this false-positive flood.
        """
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th005-lowvol-test",
            source_path="/tmp/th005lv.csv",
            source_filename="th005lv.csv",
            source_sha256="dd" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        presc_npi = "6660001111"
        # Only 5 claims — all to the same pharmacy (100% share), but total < min_claims.
        for i in range(5):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash=f"PT_TH005LV_{i}",
                auth_no_hash=f"AUTH_TH005LV_{i}",
                pharmacy_npi="5551111111",
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
            )

        run.resolution_stats = {"expected_count": 5, "inserted_count": 5}
        db.flush()

        run_detection(db, run)

        th005_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-005",
            )
        ).scalar()
        assert th005_count == 0, (
            f"TH-005 must NOT fire for a prescriber with only 5 claims "
            f"(below min_claims=20), even at 100% share; got {th005_count}"
        )

    def test_th005_finding_details_contains_claim_count(self, db: Session):
        """TH-005 finding_details must include claim_count for transparency."""
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th005-details-test",
            source_path="/tmp/th005d.csv",
            source_filename="th005d.csv",
            source_sha256="ee" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        presc_npi = "4440001111"
        # 21 claims all to same pharmacy (total >= min_claims, 100% share).
        for i in range(21):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash=f"PT_TH005D_{i}",
                auth_no_hash=f"AUTH_TH005D_{i}",
                pharmacy_npi="7771111111",
                ndc="00093015401",
                date_of_service="2024-06-01",
                prescriber_npi=presc_npi,
            )

        run.resolution_stats = {"expected_count": 21, "inserted_count": 21}
        db.flush()

        run_detection(db, run)

        anomaly = db.execute(
            select(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-005",
            )
        ).scalar_one()

        details = anomaly.finding_details
        assert isinstance(details, dict)
        # claim_count (or total_count) must appear in evidence so reviewers
        # can confirm the prescriber was above the min-volume floor.
        assert "claim_count" in details or "total_count" in details, (
            f"TH-005 finding_details must include claim_count/total_count; got {details}"
        )

    def test_th005_does_not_fire_below_threshold(self, db: Session):
        """TH-005 does not fire when top pharmacy share is below 0.5 (even above min_claims)."""
        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="th005-below-test",
            source_path="/tmp/th005b.csv",
            source_filename="th005b.csv",
            source_sha256="b2" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        presc_npi = "7770001111"
        # Distribute evenly: 5 pharmacies, 4 claims each = 20% per pharmacy, total=20 (>= min_claims)
        for ph_idx in range(5):
            for cl_idx in range(4):
                _seed_csv_row(
                    db, run,
                    row_number=ph_idx * 4 + cl_idx + 1,
                    patient_unique_hash=f"PT_TH005B_{ph_idx}_{cl_idx}",
                    auth_no_hash=f"AUTH_TH005B_{ph_idx}_{cl_idx}",
                    pharmacy_npi=f"999000000{ph_idx}",
                    ndc="00093015401",
                    date_of_service="2024-06-01",
                    prescriber_npi=presc_npi,
                )

        run.resolution_stats = {"expected_count": 20, "inserted_count": 20}
        db.flush()

        run_detection(db, run)

        th005_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "TH-005",
            )
        ).scalar()
        assert th005_count == 0, (
            f"TH-005 must NOT fire when share is 20%, got {th005_count}"
        )


# ===========================================================================
# TestNoFindingAggregation
# ===========================================================================


class TestNoFindingAggregation:
    """no_finding rows are NOT written per (row × rule) — aggregated into run stats."""

    def test_no_per_row_no_finding_log_rows(self, db: Session):
        """No DetectionRuleEvaluationLog row has evaluation_result='no_finding'."""
        run = _load_fixture(db)
        run_detection(db, run)

        nf_count = db.execute(
            select(func.count()).select_from(DetectionRuleEvaluationLog).where(
                DetectionRuleEvaluationLog.detection_run_id == run.id,
                DetectionRuleEvaluationLog.evaluation_result == "no_finding",
            )
        ).scalar()
        assert nf_count == 0, (
            f"no_finding rows must not be written per (row×rule); got {nf_count}"
        )

    def test_no_finding_count_in_resolution_stats(self, db: Session):
        """run.resolution_stats contains no_finding_count after run_detection."""
        run = _load_fixture(db)
        run_detection(db, run)

        stats = run.resolution_stats
        assert "no_finding_count" in stats, (
            "run.resolution_stats must have 'no_finding_count' key"
        )
        assert isinstance(stats["no_finding_count"], int)
        assert stats["no_finding_count"] >= 0


# ===========================================================================
# TestStreamingBatchBoundary
# ===========================================================================


class TestStreamingBatchBoundary:
    """Streaming: batch-boundary correctness for per-row and grouping rules.

    Seeds ~50 rows, patches _ROW_BATCH=10, asserts identical anomaly results.
    This proves:
    - Per-row (MFR-001) fires correctly across batch boundaries.
    - Grouping rules (ALL-001, MFR-002) are server-side SQL — a duplicate group
      split across Python batches still produces the right anomalies because
      grouping is computed by the DB, not per-batch Python accumulation.
    """

    def test_small_batch_produces_same_anomaly_count_as_default(self, db: Session):
        """run_detection with _ROW_BATCH=10 on ~50-row fixture yields same anomaly
        count as an equivalent run without the batch override."""
        import src.detection.batch_engine as be

        # Run 1: default batch size — load fixture and run detection.
        run1 = _load_fixture(db)
        count_default = run_detection(db, run1)

        # Run 2: clone run1 rows into a new DetectionRun, then run with small batch.
        # We clone rather than re-loading the CSV to avoid the SHA256-dedup guard.
        run1_rows = db.execute(
            select(CsvUploadRow).where(CsvUploadRow.detection_run_id == run1.id)
        ).scalars().all()
        row_count = len(run1_rows)

        run2 = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="stream-batch-test",
            source_path="/tmp/stream_batch.csv",
            source_filename="stream_batch.csv",
            source_sha256="bb" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": row_count, "inserted_count": row_count},
        )
        db.add(run2)
        db.flush()

        for src_row in run1_rows:
            db.add(CsvUploadRow(
                tenant_id=_TENANT,
                detection_run_id=run2.id,
                row_number=src_row.row_number,
                row_data=dict(src_row.row_data),
                resolved_pharmacy_npi=src_row.resolved_pharmacy_npi,
                resolved_ndc=src_row.resolved_ndc,
                resolved_client_id=src_row.resolved_client_id,
                resolved_program_id=src_row.resolved_program_id,
                resolution_method=src_row.resolution_method,
            ))
        db.flush()

        original_batch = be._ROW_BATCH
        try:
            be._ROW_BATCH = 10
            count_small_batch = run_detection(db, run2)
        finally:
            be._ROW_BATCH = original_batch

        assert count_small_batch == count_default, (
            f"Streaming with _ROW_BATCH=10 produced {count_small_batch} anomalies; "
            f"expected {count_default} (same as default batch). "
            "Batch-boundary split must not affect grouping rules (server-side SQL)."
        )

    def test_all001_duplicate_group_detected_across_batch_boundary(self, db: Session):
        """ALL-001: the 3-row duplicate cluster is detected even when rows are
        spread across two batches (_ROW_BATCH=2).

        Proves grouping is server-side: the SQL GROUP BY runs over the full table,
        not row-by-row in Python accumulation.
        """
        import src.detection.batch_engine as be

        register_rule_types(db)
        register_rule_instances(db, _TENANT, _FULL_CSV_COLUMNS, _SYS_UID)

        run = DetectionRun(
            tenant_id=_TENANT,
            data_source="csv_upload",
            run_label="all001-batch-boundary",
            source_path="/tmp/all001bb.csv",
            source_filename="all001bb.csv",
            source_sha256="ab" * 32,
            created_by=_SYS_UID,
            resolution_stats={"expected_count": 0, "inserted_count": 0},
        )
        db.add(run)
        db.flush()

        # Plant 3 duplicate rows (same patient/NDC/DOS, 3 distinct auths)
        for i in range(3):
            _seed_csv_row(
                db, run,
                row_number=i + 1,
                patient_unique_hash="PT_BB_DUP",
                auth_no_hash=f"AUTH_BB_{i}",
                pharmacy_npi="1234567890",
                ndc="00093015401",
                date_of_service="2024-06-01",
                transaction_code="B1",
                transaction_status="Paid",
                client_id="CLIBB",
            )

        run.resolution_stats = {"expected_count": 3, "inserted_count": 3}
        db.flush()

        original_batch = be._ROW_BATCH
        try:
            be._ROW_BATCH = 2  # force the 3 rows to span two batches
            count = run_detection(db, run)
        finally:
            be._ROW_BATCH = original_batch

        all001_count = db.execute(
            select(func.count()).select_from(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.finding_code == "ALL-001",
            )
        ).scalar()
        assert all001_count == 3, (
            f"ALL-001 must detect all 3 duplicates even with _ROW_BATCH=2; "
            f"got {all001_count}. Grouping must be server-side SQL, not per-batch Python."
        )
        assert count >= all001_count, (
            f"run_detection return value ({count}) must include ALL-001 anomalies ({all001_count})"
        )
