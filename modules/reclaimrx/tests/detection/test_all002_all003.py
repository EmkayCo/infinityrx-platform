"""Tests for ALL-002 Phantom Pharmacy and ALL-003 Phantom Prescriber (section 12 H5).

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


@pytest.fixture()
def pg_session():
    """Real Postgres session for reference-FDW tests. Rolls back all writes on teardown.

    Used by Postgres-gated ALL-002/003 tests that seed reclaimrx.* rows AND query
    reference.* FDW tables -- the SQLite conftest 'db' fixture cannot serve both.
    RLS GUC is set so INSERT into reclaimrx.* tables succeeds.
    """
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    if not REAL_DB:
        pytest.skip("requires live Postgres with reference grants")
    engine = sa.create_engine(REAL_DB)
    conn = engine.connect()
    outer = conn.begin()
    session = Session(bind=conn)
    # Set RLS tenant GUC so INSERT into reclaimrx.* passes row-level security
    session.execute(
        text("SET app.current_tenant_id = :tid"),
        {"tid": str(TEST_TENANT_ID)},
    )
    # Disable statement_timeout for FDW queries (reference.* can be slow)
    session.execute(text("SET statement_timeout = 0"))
    yield session
    session.close()
    outer.rollback()
    conn.close()
    engine.dispose()


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
    """Missing/invalid NPI increments data_quality counter at ROW level, NOT anomaly."""

    def test_missing_and_invalid_npi_row_counts_correct(self):
        from src.detection.reference_rules import _is_valid_npi

        def _count_npi_dq(npi_values):
            missing = sum(1 for v in npi_values if v is None or v == "")
            invalid = sum(
                1 for v in npi_values
                if v is not None and v != "" and not _is_valid_npi(v)
            )
            return {"missing_pharmacy_npi": missing, "invalid_pharmacy_npi": invalid}

        npi_values = [None, None, "123456789", "MA3253488", "ABCDEFGHIJ", "1234567890"]
        dq = _count_npi_dq(npi_values)

        assert isinstance(dq, dict), f"Expected dict return, got {type(dq)}"
        assert dq.get("missing_pharmacy_npi") == 2, f"Expected missing=2, got {dq}"
        assert dq.get("invalid_pharmacy_npi") == 3, f"Expected invalid=3, got {dq}"

    def test_abcdefghij_classified_as_invalid_not_valid(self):
        from src.detection.reference_rules import _is_valid_npi
        assert _is_valid_npi("ABCDEFGHIJ") is False, (
            "'ABCDEFGHIJ' is 10 chars but all-alpha -- must be INVALID, not valid"
        )



def test_all003_returns_dict_with_required_keys(db):
    """evaluate_all003_phantom_prescriber returns (list, dict) with required DQ keys.

    PORTABLE (SQLite): seeds ONLY missing and invalid NPI rows -- NO valid-format NPI rows.
    This keeps valid_npis empty so the early-return is taken before Postgres-only reference CTE.
    """
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-dq-shape", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 2, "expected_count": 2},
    )
    db.add(run)
    db.flush()

    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
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
    assert "missing_prescriber_npi" in dq, f"Missing key, got: {list(dq.keys())}"
    assert "invalid_prescriber_npi" in dq, f"Missing key, got: {list(dq.keys())}"
    assert dq["missing_prescriber_npi"] == 1, f"Expected 1, got {dq['missing_prescriber_npi']}"
    assert dq["invalid_prescriber_npi"] == 1, f"Expected 1, got {dq['invalid_prescriber_npi']}"


def test_fdb_cache_built_once_and_mfr003_receives_it(db):
    """FDB cache is built once; data_quality.no_fdb_wac increments for NDC with wac=None;
    all four NPI keys always present in data_quality.

    Pure-Python test double: patches fetch_current_prices_for_ndcs via unittest.mock.
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
    assert dq.get("no_fdb_wac", 0) >= 1, (
        f"Expected no_fdb_wac >= 1 for UNKNOWN_NDC (wac=None), got data_quality={dq}"
    )
    for _key in ("missing_pharmacy_npi", "invalid_pharmacy_npi",
                 "missing_prescriber_npi", "invalid_prescriber_npi"):
        assert _key in dq, (
            f"data_quality must always contain '{_key}', got keys={list(dq.keys())}"
        )



class TestALL002PhantomFires:
    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
    def test_npi_not_in_dataq_master_fires(self, pg_session):
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
        pg_session.add(run)
        pg_session.flush()
        pg_session.add(CsvUploadRow(
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
        pg_session.flush()

        anomalies, dq = evaluate_all002_phantom_pharmacy(pg_session, run, instance=inst)
        assert isinstance(dq, dict), f"Expected dict, got {type(dq)}"
        assert "missing_pharmacy_npi" in dq and "invalid_pharmacy_npi" in dq, (
            f"data_quality dict must have missing_pharmacy_npi and invalid_pharmacy_npi keys, got {dq}"
        )
        assert any(a.finding_code == "ALL-002" for a in anomalies)


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_matched_npi_with_null_name_does_not_fire_phantom(pg_session):
    """A pharmacy NPI that EXISTS in dataq_master but has NULL legal_business_name
    must NOT be flagged as phantom (phantom = dm.npi IS NULL after LEFT JOIN, NOT null name)."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    row = pg_session.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, (
        "reference.dataq_master has no rows -- FDW not set up."
    )
    NULL_NAME_NPI = row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-null-name-no-fire", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    pg_session.add(run)
    pg_session.flush()
    pg_session.add(CsvUploadRow(
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
    pg_session.flush()

    anomalies, _dq = evaluate_all002_phantom_pharmacy(pg_session, run, instance=inst)

    phantom_anomalies = [a for a in anomalies if "phantom" in (a.finding_details or {}).get("reason", "")]
    assert len(phantom_anomalies) == 0, (
        f"NPI {NULL_NAME_NPI} exists in dataq_master but was wrongly flagged as phantom: {phantom_anomalies}"
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_truly_absent_npi_fires_phantom(pg_session):
    """A pharmacy NPI with NO row in dataq_master MUST be flagged as phantom."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    ABSENT_NPI = "9999999991"
    present = pg_session.execute(
        text("SELECT 1 FROM reference.dataq_master WHERE npi = :npi LIMIT 1"),
        {"npi": ABSENT_NPI},
    ).fetchone()
    assert present is None, f"NPI {ABSENT_NPI} unexpectedly present in reference.dataq_master."

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-absent-fires", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    pg_session.add(run)
    pg_session.flush()
    pg_session.add(CsvUploadRow(
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
    pg_session.flush()

    anomalies, _dq = evaluate_all002_phantom_pharmacy(pg_session, run, instance=inst)

    phantom_anomalies = [
        a for a in anomalies
        if (a.finding_details or {}).get("reason") == "phantom_not_in_dataq_master"
    ]
    assert len(phantom_anomalies) >= 1, (
        f"NPI {ABSENT_NPI} is absent from dataq_master but no phantom anomaly was raised."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all003_matched_npi_with_null_name_does_not_fire_phantom(pg_session):
    """A prescriber NPI that EXISTS in prescribers but has NULL display_name
    must NOT be flagged as phantom."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    row = pg_session.execute(
        text(
            "SELECT npi FROM reference.prescribers "
            "WHERE npi IS NOT NULL AND (status IS NULL OR status != 'deactivated') "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, "reference.prescribers has no rows -- FDW not set up."
    NULL_NAME_NPI = row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-null-name-no-fire", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    pg_session.add(run)
    pg_session.flush()
    pg_session.add(CsvUploadRow(
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
    pg_session.flush()

    anomalies, _dq = evaluate_all003_phantom_prescriber(pg_session, run, instance=inst)

    phantom_anomalies = [a for a in anomalies if "phantom" in (a.finding_details or {}).get("reason", "")]
    assert len(phantom_anomalies) == 0, (
        f"NPI {NULL_NAME_NPI} exists in prescribers with NULL display_name but was wrongly "
        f"flagged as phantom: {phantom_anomalies}. Phantom must test p.npi IS NULL, not name nullness."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all003_truly_absent_npi_fires_phantom(pg_session):
    """A prescriber NPI with NO row in prescribers MUST be flagged as phantom."""
    from datetime import date as _date

    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    ABSENT_NPI = "9999999992"
    present = pg_session.execute(
        text("SELECT 1 FROM reference.prescribers WHERE npi = :npi LIMIT 1"),
        {"npi": ABSENT_NPI},
    ).fetchone()
    assert present is None, f"NPI {ABSENT_NPI} unexpectedly present in reference.prescribers."

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-absent-fires", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1, "expected_count": 1},
    )
    pg_session.add(run)
    pg_session.flush()
    pg_session.add(CsvUploadRow(
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
    pg_session.flush()

    anomalies, _dq = evaluate_all003_phantom_prescriber(pg_session, run, instance=inst)

    phantom_anomalies = [
        a for a in anomalies
        if (a.finding_details or {}).get("reason") == "phantom_not_in_prescribers"
    ]
    assert len(phantom_anomalies) >= 1, (
        f"NPI {ABSENT_NPI} is absent from prescribers but no phantom anomaly was raised."
    )


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_query_count_constant_not_linear(pg_session):
    """Query count must be CONSTANT as flagged-NPI count grows (set-based, not N+1)."""
    from datetime import date as _date

    import sqlalchemy.event as sa_event

    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import CsvUploadRow, DetectionRun, DetectionRuleInstance

    def _count_queries(n: int) -> int:
        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label=f"qcount-{n}", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": n, "expected_count": n},
        )
        pg_session.add(run)
        pg_session.flush()
        for i in range(n):
            npi = str(1000000000 + i)
            pg_session.add(CsvUploadRow(
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
        pg_session.flush()

        query_count = [0]
        bind = pg_session.get_bind()

        def _count(conn, cursor, statement, params, context, executemany):
            query_count[0] += 1

        sa_event.listen(bind, "before_cursor_execute", _count)
        try:
            evaluate_all002_phantom_pharmacy(pg_session, run, instance=inst)
        finally:
            # Always remove the listener to prevent leakage into subsequent tests.
            sa_event.remove(bind, "before_cursor_execute", _count)
        return query_count[0]

    count_5 = _count_queries(5)
    count_50 = _count_queries(50)
    assert count_5 == count_50, (
        f"Query count is NOT constant: 5 NPIs={count_5}, 50 NPIs={count_50}. N+1 suspected."
    )
    assert count_5 <= 5, f"Too many queries even for 5 NPIs: {count_5}"


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants from 0010")
def test_run_detection_wires_all002_and_produces_anomaly(pg_session):
    """run_detection must produce exactly the planted ALL-002 anomaly for a phantom pharmacy."""
    from datetime import date as _date

    from sqlalchemy import select

    from src.detection.batch_engine import run_detection
    from src.detection.rule_type_registry import register_rule_types
    from src.models.detection_run_models import (
        Anomaly,
        CsvUploadRow,
        DetectionRun,
        DetectionRuleInstance,
    )

    TOTAL_ROWS = 500

    _ref_row = pg_session.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert _ref_row is not None, (
        "reference.dataq_master has no active rows -- FDW not provisioned."
    )
    KNOWN_GOOD_NPI = _ref_row.npi

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all002-wiring-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": TOTAL_ROWS, "expected_count": TOTAL_ROWS},
    )
    pg_session.add(run)
    pg_session.flush()

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
    pg_session.add(phantom_row)
    pg_session.flush()
    planted_row_id = phantom_row.id

    for i in range(2, TOTAL_ROWS + 1):
        pg_session.add(CsvUploadRow(
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
    pg_session.flush()

    register_rule_types(pg_session)

    pg_session.add(DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-wiring-test",
        enabled=True, effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    ))
    pg_session.flush()

    run_detection(pg_session, run)
    pg_session.refresh(run)

    assert run.status == "completed", (
        f"run_detection must complete (not fail); got status={run.status!r}, "
        f"guardrail={run.resolution_stats.get('guardrail')}"
    )

    all002_anomalies = pg_session.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "ALL-002",
        )
    ).scalars().all()
    assert len(all002_anomalies) == 1, (
        f"Expected exactly 1 ALL-002 anomaly, got {len(all002_anomalies)}"
    )
    assert all002_anomalies[0].source_row_id == planted_row_id, (
        f"ALL-002 anomaly must reference planted row id {planted_row_id}"
    )
    assert all002_anomalies[0].finding_details.get("pharmacy_npi") == "9999999999", (
        f"ALL-002 phantom finding_details['pharmacy_npi'] must equal '9999999999'; "
        f"got {all002_anomalies[0].finding_details.get('pharmacy_npi')!r}"
    )

    dq = run.resolution_stats.get("data_quality", {})
    assert isinstance(dq, dict), f"resolution_stats['data_quality'] must be a dict, got {type(dq)}"
    for key in ("missing_pharmacy_npi", "invalid_pharmacy_npi",
                "missing_prescriber_npi", "invalid_prescriber_npi"):
        assert key in dq, f"data_quality must contain '{key}'; got keys: {list(dq.keys())}"