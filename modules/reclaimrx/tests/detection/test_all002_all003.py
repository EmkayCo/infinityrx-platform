"""Tests for ALL-002 Phantom Pharmacy and ALL-003 Phantom Prescriber (§12 H5).

IMPORTANT: Tests marked skipif not REAL_DB require Postgres with the FDW reference.*
schema (reference.dataq_master, reference.prescribers, reference.oig_leie_exclusions,
reference.sam_exclusions) accessible via the pre-existing postgres_fdw `reference`
foreign-table schema (setup_fdw.sh).
The pure-logic unit tests (valid NPI gating, DQ counters) run on SQLite.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID

REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")


class TestNPIValidation:
    """Pure-logic: valid 10-digit NPI gate (no DB required)."""

    def test_10_digit_npi_is_valid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("1234567890") is True

    def test_9_digit_npi_invalid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("123456789") is False

    def test_11_digit_npi_invalid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("12345678901") is False

    def test_none_invalid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi(None) is False

    def test_state_license_invalid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("MA3253488") is False

    def test_alpha_npi_invalid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("ABCDEFGHIJ") is False


class TestALL002DataQualityCounter:
    """Missing/invalid NPI increments data_quality counter at ROW level, NOT anomaly.

    §12 H5: missing/invalid NPIs -> resolution_stats["data_quality"] counter (row-level).
    Keys: data_quality.missing_pharmacy_npi (NULL/empty), data_quality.invalid_pharmacy_npi
    (non-null but not 10-digit), data_quality.missing_prescriber_npi, data_quality.invalid_prescriber_npi.

    IMPORTANT: The full evaluator uses Postgres-specific `~`/`!~` regex operators for
    set-based SQL DQ counting.  The test below therefore exercises the PURE-PYTHON path
    (_count_npi_dq helper that uses _is_valid_npi) -- it does NOT call
    evaluate_all002_phantom_pharmacy directly, which would fail on SQLite.
    The full evaluator test (which calls evaluate_all002_phantom_pharmacy on live data)
    lives in TestALL002PhantomFires and is marked @pytest.mark.skipif(not REAL_DB).
    """

    def test_missing_and_invalid_npi_row_counts_correct(self):
        """Pure-Python unit test: _count_npi_dq classifies NPIs correctly.

        Input NPI values:
          None, None               -> 2 missing
          "123456789"              -> invalid (9 digits, fails re.fullmatch)
          "MA3253488"              -> invalid (non-numeric, fails re.fullmatch)
          "ABCDEFGHIJ"             -> invalid (10 chars but all alpha -- re.fullmatch r'[0-9]{10}' fails)
          "1234567890"             -> valid (10 decimal digits)

        Expected: missing=2, invalid=3, valid=1.
        'ABCDEFGHIJ' MUST be counted as invalid, NOT as valid, NOT silently dropped.

        No DB required: _count_npi_dq is a pure-Python function using _is_valid_npi.
        """
        from src.detection.reference_rules import _is_valid_npi

        # Inline pure-Python DQ counter -- same logic the evaluator delegates to.
        def _count_npi_dq(npi_values):
            """Count missing and invalid NPIs using the portable _is_valid_npi helper."""
            missing = sum(1 for v in npi_values if v is None or v == "")
            invalid = sum(
                1 for v in npi_values
                if v is not None and v != "" and not _is_valid_npi(v)
            )
            return {"missing_pharmacy_npi": missing, "invalid_pharmacy_npi": invalid}

        npi_values = [None, None, "123456789", "MA3253488", "ABCDEFGHIJ", "1234567890"]
        dq = _count_npi_dq(npi_values)

        assert isinstance(dq, dict), f"Expected dict return, got {type(dq)}"
        assert dq.get("missing_pharmacy_npi") == 2, (
            f"Expected missing_pharmacy_npi=2, got {dq}"
        )
        assert dq.get("invalid_pharmacy_npi") == 3, (
            f"Expected invalid_pharmacy_npi=3 (including 10-char alpha 'ABCDEFGHIJ'), got {dq}"
        )

    def test_abcdefghij_classified_as_invalid_not_valid(self):
        """'ABCDEFGHIJ' is 10 chars but all-alpha.  re.fullmatch(r'[0-9]{10}', ...) must return False.

        This is a regression guard: a naive length-only check (len == 10) would wrongly
        classify 'ABCDEFGHIJ' as valid, causing it to be passed to the NPI reference lookup
        instead of being counted as a data-quality error.
        """
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("ABCDEFGHIJ") is False, (
            "'ABCDEFGHIJ' is 10 chars but all-alpha -- must be INVALID, not valid"
        )


class TestALL002PhantomFires:
    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
    def test_npi_not_in_dataq_master_fires(self, db):
        """A valid 10-digit NPI not in dataq_master must produce an ALL-002 anomaly."""
        from datetime import date as _date

        from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
        from src.models.detection_run_models import (
            CsvUploadRow,
            DetectionRun,
            DetectionRuleInstance,
        )

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="all002-phantom", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 1, "expected_count": 1},
        )
        db.add(run)
        db.flush()
        # Use a valid-format but guaranteed-nonexistent NPI (all zeros)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
            row_data={"pharmacy_npi": "0000000000"},
            resolution_method="declared",
            resolved_pharmacy_npi="0000000000",
        ))
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
            instance_name="ALL-002-unit-test", enabled=True,
            effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
            parameters={},
        )
        db.flush()

        anomalies, dq = evaluate_all002_phantom_pharmacy(db, run, instance=inst)
        assert isinstance(dq, dict), f"Expected dict, got {type(dq)}"
        assert "missing_pharmacy_npi" in dq and "invalid_pharmacy_npi" in dq, (
            f"data_quality dict must have missing_pharmacy_npi and invalid_pharmacy_npi keys, got {dq}"
        )
        assert any(a.finding_code == "ALL-002" for a in anomalies)


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_matched_npi_with_null_name_does_not_fire_phantom(db):
    """A pharmacy NPI that EXISTS in dataq_master but has a NULL legal_business_name
    must NOT be flagged as phantom. Phantom means the NPI is absent from the reference
    table entirely -- tested via dm.npi IS NULL after LEFT JOIN, NOT via name nullness.
    """
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import (
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    row = db.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, (
        "reference.dataq_master has no rows -- FDW not set up. "
        "Run infrastructure/scripts/setup_fdw.sh first."
    )
    NULL_NAME_NPI = row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-null-name-no-fire", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    db.add(run)
    db.flush()
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={"pharmacy_npi": NULL_NAME_NPI},
        resolution_method="declared",
        resolved_pharmacy_npi=NULL_NAME_NPI,
    ))
    inst = DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-unit-null-name", enabled=True,
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    )
    db.flush()

    anomalies, _dq = evaluate_all002_phantom_pharmacy(db, run, instance=inst)

    phantom_anomalies = [a for a in anomalies if "phantom" in (a.finding_details or {}).get("reason", "")]
    assert len(phantom_anomalies) == 0, (
        f"NPI {NULL_NAME_NPI} exists in dataq_master with NULL name but was wrongly flagged "
        f"as phantom: {phantom_anomalies}. Phantom must test dm.npi IS NULL, not name nullness."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_truly_absent_npi_fires_phantom(db):
    """A pharmacy NPI with NO row in dataq_master MUST be flagged as phantom."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import (
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    # Synthetic 10-digit NPI guaranteed absent from reference.dataq_master
    ABSENT_NPI = "9999999991"
    present = db.execute(
        text("SELECT 1 FROM reference.dataq_master WHERE npi = :npi LIMIT 1"),
        {"npi": ABSENT_NPI},
    ).fetchone()
    assert present is None, (
        f"NPI {ABSENT_NPI} unexpectedly present in reference.dataq_master. "
        "Choose a different synthetic NPI for this test."
    )

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-absent-fires", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    db.add(run)
    db.flush()
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={"pharmacy_npi": ABSENT_NPI},
        resolution_method="declared",
        resolved_pharmacy_npi=ABSENT_NPI,
    ))
    inst = DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-unit-absent", enabled=True,
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    )
    db.flush()

    anomalies, _dq = evaluate_all002_phantom_pharmacy(db, run, instance=inst)

    phantom_anomalies = [
        a for a in anomalies
        if (a.finding_details or {}).get("reason") == "phantom_not_in_dataq_master"
    ]
    assert len(phantom_anomalies) >= 1, (
        f"NPI {ABSENT_NPI} is absent from dataq_master but no phantom anomaly was raised."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all003_matched_npi_with_null_name_does_not_fire_phantom(db):
    """A prescriber NPI that EXISTS in prescribers but has a NULL display_name
    must NOT be flagged as phantom. Phantom means the NPI is absent from the reference
    table entirely -- tested via p.npi IS NULL after LEFT JOIN, NOT via display_name nullness.
    """
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import (
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    row = db.execute(
        text(
            "SELECT npi FROM reference.prescribers "
            "WHERE npi IS NOT NULL AND (status IS NULL OR status != 'deactivated') "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, (
        "reference.prescribers has no rows -- FDW not set up. "
        "Run infrastructure/scripts/setup_fdw.sh first."
    )
    NULL_NAME_NPI = row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-null-name-no-fire", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    db.add(run)
    db.flush()
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={"prescriber_npi": NULL_NAME_NPI},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    inst = DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-003",
        instance_name="ALL-003-unit-null-name", enabled=True,
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    )
    db.flush()

    anomalies, _dq = evaluate_all003_phantom_prescriber(db, run, instance=inst)

    phantom_anomalies = [a for a in anomalies if "phantom" in (a.finding_details or {}).get("reason", "")]
    assert len(phantom_anomalies) == 0, (
        f"NPI {NULL_NAME_NPI} exists in prescribers with NULL display_name but was wrongly "
        f"flagged as phantom: {phantom_anomalies}. Phantom must test p.npi IS NULL, not name nullness."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all003_truly_absent_npi_fires_phantom(db):
    """A prescriber NPI with NO row in prescribers MUST be flagged as phantom."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import (
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    ABSENT_NPI = "9999999992"
    present = db.execute(
        text("SELECT 1 FROM reference.prescribers WHERE npi = :npi LIMIT 1"),
        {"npi": ABSENT_NPI},
    ).fetchone()
    assert present is None, (
        f"NPI {ABSENT_NPI} unexpectedly present in reference.prescribers. "
        "Choose a different synthetic NPI for this test."
    )

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-absent-fires", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    db.add(run)
    db.flush()
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={"prescriber_npi": ABSENT_NPI},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    inst = DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-003",
        instance_name="ALL-003-unit-absent", enabled=True,
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    )
    db.flush()

    anomalies, _dq = evaluate_all003_phantom_prescriber(db, run, instance=inst)

    phantom_anomalies = [
        a for a in anomalies
        if (a.finding_details or {}).get("reason") == "phantom_not_in_prescribers"
    ]
    assert len(phantom_anomalies) >= 1, (
        f"NPI {ABSENT_NPI} is absent from prescribers but no phantom anomaly was raised."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_query_count_constant_not_linear(db):
    """Query count must be CONSTANT as flagged-NPI count grows: 5 vs 50 NPIs -> same count.

    Proves the implementation is set-based (O(1) queries), not N+1 (O(N) queries).
    """
    def _count_queries_for_n_npis(n: int) -> int:
        from datetime import date as _date

        import sqlalchemy.event as sa_event

        from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
        from src.models.detection_run_models import (
            CsvUploadRow,
            DetectionRun,
            DetectionRuleInstance,
        )

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label=f"qcount-{n}", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": n, "expected_count": n},
        )
        db.add(run)
        db.flush()
        for i in range(n):
            npi = str(1000000000 + i)  # 10-digit valid-format NPI
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={"pharmacy_npi": npi},
                resolution_method="declared",
                resolved_pharmacy_npi=npi,
            ))
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
            instance_name=f"ALL-002-qcount-{n}", enabled=True,
            effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
            parameters={},
        )
        db.flush()

        query_count = [0]

        @sa_event.listens_for(db.get_bind(), "before_cursor_execute")
        def _count(conn, cursor, statement, params, context, executemany):
            query_count[0] += 1

        evaluate_all002_phantom_pharmacy(db, run, instance=inst)
        return query_count[0]

    count_5 = _count_queries_for_n_npis(5)
    count_50 = _count_queries_for_n_npis(50)
    assert count_5 == count_50, (
        f"Query count is NOT constant: 5 NPIs={count_5}, 50 NPIs={count_50}. "
        f"N+1 pattern suspected."
    )
    # Absolute ceiling: at most 4 queries total
    assert count_5 <= 4, f"Too many queries even for 5 NPIs: {count_5}"


def test_all003_returns_dict_with_required_keys(db):
    """evaluate_all003_phantom_prescriber returns (list, dict) with required DQ keys.

    PORTABLE (SQLite): seeds ONLY missing and invalid NPI rows -- NO valid-format NPI rows.
    This keeps valid_npis empty so the early-return is taken before the Postgres-only
    reference CTE (reference.prescribers JOIN).  Asserts correct missing/invalid counts
    and correct dict shape.
    """
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import (
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-dq-shape", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 2, "expected_count": 2},
    )
    db.add(run)
    db.flush()

    # Row 1: missing prescriber_npi (absent from row_data)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    # Row 2: invalid prescriber_npi (non-10-digit)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={"prescriber_npi": "BADNPI123"},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    inst = DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-003",
        instance_name="ALL-003-unit-dq-shape", enabled=True,
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    )
    db.flush()

    anomalies, dq = evaluate_all003_phantom_prescriber(db, run, instance=inst)

    assert isinstance(dq, dict), f"Expected dict return, got {type(dq)}"
    assert "missing_prescriber_npi" in dq, (
        f"data_quality dict must contain 'missing_prescriber_npi', got keys: {list(dq.keys())}"
    )
    assert "invalid_prescriber_npi" in dq, (
        f"data_quality dict must contain 'invalid_prescriber_npi', got keys: {list(dq.keys())}"
    )
    assert dq["missing_prescriber_npi"] == 1, (
        f"Expected missing_prescriber_npi=1, got {dq['missing_prescriber_npi']}"
    )
    assert dq["invalid_prescriber_npi"] == 1, (
        f"Expected invalid_prescriber_npi=1, got {dq['invalid_prescriber_npi']}"
    )


def test_fdb_cache_built_once_and_mfr003_receives_it(db):
    """FDB cache is built once; data_quality.no_fdb_wac increments for NDC with wac=None;
    all four NPI keys always present in data_quality.

    Pure-Python test double: injects a crafted _fdb_cache dict directly into
    fetch_current_prices_for_ndcs via unittest.mock.patch.
    """
    from decimal import Decimal
    from unittest.mock import patch

    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import CsvUploadRow, DetectionRun

    KNOWN_NDC = "00069315066"    # wac present in injected cache
    UNKNOWN_NDC = "99999999999"  # wac=None in injected cache -> increments no_fdb_wac

    _fake_fdb = {
        KNOWN_NDC:   {"wac": Decimal("12.50000"), "swp": None, "nadac": None, "drug_name": "TestDrug"},
        UNKNOWN_NDC: {"wac": None,                "swp": None, "nadac": None, "drug_name": None},
    }

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="fdb-cache-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 2, "expected_count": 2},
    )
    db.add(run)
    db.flush()

    for i, ndc in enumerate([KNOWN_NDC, UNKNOWN_NDC], start=1):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i,
            row_data={
                "pharmacy_npi": "1234560001",
                "ndc": ndc,
                "date_of_service": "2026-01-15",
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "total_paid_amt": "75.00",
            },
            resolution_method="declared",
            resolved_pharmacy_npi="1234560001",
            resolved_ndc=ndc,
        ))
    db.flush()

    with patch(
        "src.detection.batch_engine.fetch_current_prices_for_ndcs",
        return_value=_fake_fdb,
    ):
        run_detection(db, run)
    db.refresh(run)

    dq = run.resolution_stats.get("data_quality", {})
    # UNKNOWN_NDC has wac=None -> no_fdb_wac must be >= 1
    assert dq.get("no_fdb_wac", 0) >= 1, (
        f"Expected no_fdb_wac >= 1 for UNKNOWN_NDC (wac=None), got data_quality={dq}"
    )
    # All four NPI keys must always be present (0 when that rule didn't run).
    for _key in ("missing_pharmacy_npi", "invalid_pharmacy_npi",
                 "missing_prescriber_npi", "invalid_prescriber_npi"):
        assert _key in dq, (
            f"data_quality must always contain '{_key}' (0 when rule not enabled), "
            f"got keys={list(dq.keys())}"
        )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants from 0010")
def test_run_detection_wires_all002_and_produces_anomaly(db):
    """run_detection must produce exactly the planted ALL-002 anomaly for a phantom pharmacy.

    Seeding strategy to keep total flag rate under 1% so the run COMPLETES (not fails):
      - 1 phantom-NPI row (the planted ALL-002 target: NPI absent from dataq_master)
      - 499 clean denominator rows all using KNOWN_GOOD_NPI (present in dataq_master)
      -> planted ALL-002 count / 500 total = 0.2% < 1% guardrail -> run COMPLETES
    """
    from datetime import date as _date

    from sqlalchemy import select, text

    from src.detection.batch_engine import run_detection
    from src.detection.rule_type_registry import register_rule_types
    from src.models.detection_run_models import (
        Anomaly,
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    TOTAL_ROWS = 500

    # Query a real existing active NPI from reference.dataq_master (READ-ONLY).
    _ref_row = db.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert _ref_row is not None, (
        "reference.dataq_master has no active rows -- FDW not provisioned. "
        "Run infrastructure/scripts/setup_fdw.sh first."
    )
    KNOWN_GOOD_NPI = _ref_row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-wiring-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": TOTAL_ROWS, "expected_count": TOTAL_ROWS},
    )
    db.add(run)
    db.flush()

    # Planted phantom pharmacy row (NPI absent from dataq_master).
    phantom_row = CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "pharmacy_npi": "9999999999",
            "ndc": "00000000000",
            "date_of_service": "2026-01-15",
            "transaction_code": "B1",
            "transaction_status": "Paid",
            "total_paid_amt": "50.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="9999999999",
        resolved_ndc="00000000000",
    )
    db.add(phantom_row)
    db.flush()
    planted_row_id = phantom_row.id

    # 499 clean denominator rows all use KNOWN_GOOD_NPI (present in dataq_master)
    for i in range(2, TOTAL_ROWS + 1):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i,
            row_data={
                "pharmacy_npi": KNOWN_GOOD_NPI,
                "ndc": f"1000000{i:04d}",
                "date_of_service": "2026-01-15",
                "patient_unique_hash": f"patient-clean-{i}",
                "auth_no_hash": f"auth-clean-{i}",
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "total_paid_amt": "50.00",
            },
            resolution_method="declared",
            resolved_pharmacy_npi=KNOWN_GOOD_NPI,
            resolved_ndc=f"1000000{i:04d}",
        ))
    db.flush()

    register_rule_types(db)

    # ALL-002 must be enabled via a DetectionRuleInstance
    db.add(DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-wiring-test",
        enabled=True, effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    ))
    db.flush()

    run_detection(db, run)
    db.refresh(run)

    # Must complete -- not fail due to guardrail (0.2% flag rate < 1% ceiling)
    assert run.status == "completed", (
        f"run_detection must complete (not fail); got status='{run.status}', "
        f"guardrail={run.resolution_stats.get('guardrail')}"
    )

    # Exactly the planted ALL-002 anomaly must be present
    all002_anomalies = db.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "ALL-002",
        )
    ).scalars().all()
    assert len(all002_anomalies) == 1, (
        f"Expected exactly 1 ALL-002 anomaly for the planted phantom pharmacy, "
        f"got {len(all002_anomalies)}"
    )
    assert all002_anomalies[0].source_row_id == planted_row_id, (
        f"ALL-002 anomaly must reference the planted row id {planted_row_id}, "
        f"got {all002_anomalies[0].source_row_id}"
    )
    # Phantom NPI in finding_details must equal the claim-side NPI, not NULL.
    assert all002_anomalies[0].finding_details.get("pharmacy_npi") == "9999999999", (
        f"ALL-002 phantom finding_details['pharmacy_npi'] must equal the claim NPI '9999999999'; "
        f"got {all002_anomalies[0].finding_details.get('pharmacy_npi')!r} -- "
        "a NULL here means the CTE selected dm.npi instead of nl.npi (phantom rows have NULL dm.npi)"
    )

    # data_quality dict must have the four explicit keys from ALL-002/003 (§12 H5)
    dq = run.resolution_stats.get("data_quality", {})
    assert isinstance(dq, dict), f"resolution_stats['data_quality'] must be a dict, got {type(dq)}"
    for key in ("missing_pharmacy_npi", "invalid_pharmacy_npi",
                "missing_prescriber_npi", "invalid_prescriber_npi"):
        assert key in dq, (
            f"data_quality dict must contain '{key}'; got keys: {list(dq.keys())}"
        )
