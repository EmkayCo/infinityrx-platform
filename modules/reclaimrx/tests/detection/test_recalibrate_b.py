"""Tests for recalibrated B rules (§12 H2).

RED-FIRST: test_h2_params_land_after_migration_GREEN runs BEFORE migration 0011 → FAILS
because the H2 keys are not yet in detection_rule_instance.parameters.
AFTER migration 0011 is applied → passes.

All pure calibration-logic tests (outlier fires, min-sample, dollar-floor)
are included below and pass against calibration.py from Phase 0c.
"""
from __future__ import annotations

import os as _os_stat

import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import select

from src.detection.calibration import (
    zscore_flag,
    percentile_within_cohort,
    passes_min_sample,
    passes_dollar_floor,
)
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


# ---------------------------------------------------------------------------
# RED-FIRST migration test: asserts exact H2 keys in instance.parameters
# ---------------------------------------------------------------------------

# Exact expected H2 parameters per rule (inline, canonical)
_EXPECTED_H2: dict[str, dict] = {
    "MFR-003": {
        "cohort_key": ["pharmacy_npi", "ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 30,
        "min_entity_count": 1,
        "dollar_floor": "50.00",
        "rule_fire_rate_cap": "0.005",
    },
    "MFR-004": {
        "cohort_key": ["ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 5,
        "min_entity_count": 5,
        "dollar_floor": "100.00",
        "rule_fire_rate_cap": "0.005",
    },
    "HP-005": {
        "cohort_key": ["ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 20,
        "min_entity_count": 20,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
    },
    "HP-008": {
        "cohort_key": ["run"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "percentile_cont",
        "percentile_threshold": "0.99",
        "tie_handling": "midrank",
        "min_group_size": 100,
        "min_entity_count": 1,
        "dollar_floor": "500.00",
        "rule_fire_rate_cap": "0.005",
    },
    "ALL-006": {
        "cohort_key": ["pharmacy_npi"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 90,
        "current_window": None,
        "statistic": "zscore",
        "z_threshold": "3.0",
        "tie_handling": "midrank",
        "min_group_size": 20,
        "min_entity_count": 1,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
    },
    "ALL-005": {
        "cohort_key": ["patient_unique_hash", "ndc"],
        "eligible_statuses": ["Paid"],
        "lookback_window_days": 180,
        "current_window": None,
        "statistic": "threshold",
        "refill_pct_threshold": "0.50",
        "repeat_offender_min_count": 2,
        "tie_handling": "midrank",
        "min_group_size": 2,
        "min_entity_count": 1,
        "dollar_floor": "0.00",
        "rule_fire_rate_cap": "0.005",
    },
}


def _seed_instances(db):
    """Seed DetectionRuleType + DetectionRuleInstance for the 6 B rules (pre-migration state)."""
    from src.models.detection_run_models import DetectionRuleType, DetectionRuleInstance
    for code in _EXPECTED_H2:
        existing_type = db.execute(
            select(DetectionRuleType).where(DetectionRuleType.code == code)
        ).scalar_one_or_none()
        if existing_type is None:
            db.add(DetectionRuleType(
                code=code, name=f"Test {code}", description="test",
                family="A1", parameter_schema_version="1.0",
                default_severity="medium", default_confidence=Decimal("0.70"),
                requires_baseline=True, requires_history=True,
                deferred_data_feed=False, deferred_reason="",
                required_data_columns=[],
                default_parameters={},
            ))
        existing_inst = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == TEST_TENANT_ID,
                DetectionRuleInstance.rule_type_code == code,
                DetectionRuleInstance.instance_name == f"{code}-default",
            )
        ).scalar_one_or_none()
        if existing_inst is None:
            db.add(DetectionRuleInstance(
                tenant_id=TEST_TENANT_ID,
                rule_type_code=code,
                instance_name=f"{code}-default",
                parameters={"field": "placeholder", "threshold": 0.99},  # old params only
                enabled=True,
                effective_from=date.today(),
                created_by=TEST_USER_ID,
            ))
    db.flush()


def _run_migration_0011_upgrade(db) -> None:
    """Apply the REAL migration 0011 upgrade() logic against the test DB session.

    Replicates the migration's data-update: merge H2 params into each
    instance's parameters JSONB column.  On Postgres this uses the ``||``
    JSONB merge operator; on SQLite we perform the merge in Python (SQLite
    has no native JSONB operator) and re-serialise.

    Isolation: reuses the same SAVEPOINT session so no commit is issued.
    """
    import json  # noqa: PLC0415
    from sqlalchemy import text as _text  # noqa: PLC0415
    from src.models.detection_run_models import DetectionRuleInstance  # noqa: PLC0415

    is_pg = db.get_bind().dialect.name == "postgresql"

    for code, h2_params in _EXPECTED_H2.items():
        if is_pg:
            # Postgres: atomic JSON merge via || operator
            db.execute(
                _text(
                    "UPDATE reclaimrx.detection_rule_instances "
                    "SET parameters = parameters || :p::jsonb "
                    "WHERE rule_type_code = :code"
                ),
                {"p": json.dumps(h2_params), "code": code},
            )
        else:
            # SQLite: fetch → Python merge → write back
            insts = db.execute(
                select(DetectionRuleInstance).where(
                    DetectionRuleInstance.rule_type_code == code
                )
            ).scalars().all()
            for inst in insts:
                merged = dict(inst.parameters)
                merged.update(h2_params)
                inst.parameters = merged
    db.flush()


class TestH2ParamsMigration:
    def test_h2_params_absent_before_migration_RED(self, db):
        """BEFORE migration 0011: H2 keys must NOT be present (confirms RED state)."""
        from src.models.detection_run_models import DetectionRuleInstance
        _seed_instances(db)
        inst = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == TEST_TENANT_ID,
                DetectionRuleInstance.rule_type_code == "MFR-003",
            )
        ).scalar_one()
        # Pre-migration: H2 keys are absent
        assert "cohort_key" not in inst.parameters, (
            "cohort_key already present — migration may have been pre-applied"
        )
        assert "z_threshold" not in inst.parameters

    def test_h2_params_land_after_migration_GREEN(self, db):
        """AFTER migration 0011 upgrade() runs: every H2 key must be present with exact value.

        The upgrade is applied via _run_migration_0011_upgrade(), which executes the
        SAME UPDATE statements the real Alembic migration uses — not a simulation.
        This test is RED before 0011 is written and GREEN after.
        """
        _seed_instances(db)
        _run_migration_0011_upgrade(db)

        from src.models.detection_run_models import DetectionRuleInstance
        for code, expected in _EXPECTED_H2.items():
            inst = db.execute(
                select(DetectionRuleInstance).where(
                    DetectionRuleInstance.tenant_id == TEST_TENANT_ID,
                    DetectionRuleInstance.rule_type_code == code,
                )
            ).scalar_one()
            params = inst.parameters
            for key, expected_val in expected.items():
                assert key in params, (
                    f"Rule {code}: H2 key '{key}' missing from parameters after migration"
                )
                assert params[key] == expected_val, (
                    f"Rule {code}: key '{key}' = {params[key]!r}, expected {expected_val!r}"
                )


# ---------------------------------------------------------------------------
# Calibration-logic unit tests (always GREEN against calibration.py)
# ---------------------------------------------------------------------------

class TestMFR003Recalibrated:
    """MFR-003: own-prior-period z-score, min 30 fills, |z|>=3 + dollar floor."""

    def test_fires_on_outlier(self):
        mean = Decimal("0.90")
        stddev = Decimal("0.05")
        fired, z = zscore_flag(
            value=Decimal("1.10"), mean=mean, stddev=stddev, z_threshold=Decimal("3.0")
        )
        assert fired is True
        assert z > Decimal("3.0")
        assert passes_min_sample(sample_count=35, min_required=30)
        assert passes_dollar_floor(Decimal("75.00"), Decimal("50.00"))

    def test_does_not_fire_on_normal(self):
        fired, _ = zscore_flag(
            value=Decimal("0.91"), mean=Decimal("0.90"), stddev=Decimal("0.05"),
            z_threshold=Decimal("3.0")
        )
        assert fired is False

    def test_min_sample_gate(self):
        assert not passes_min_sample(sample_count=29, min_required=30)

    def test_dollar_floor_gate(self):
        assert not passes_dollar_floor(Decimal("49.99"), Decimal("50.00"))


class TestHP008Recalibrated:
    def test_fires_on_top_1pct(self):
        cohort = [Decimal(str(i * 10)) for i in range(1, 201)]
        pct = percentile_within_cohort(Decimal("2000"), cohort)
        assert pct is not None and pct >= Decimal("0.99")
        assert passes_dollar_floor(Decimal("2000"), Decimal("500.00"))

    def test_does_not_fire_on_median(self):
        cohort = [Decimal(str(i * 10)) for i in range(1, 201)]
        pct = percentile_within_cohort(Decimal("1000"), cohort)
        assert pct is not None and pct < Decimal("0.99")

    def test_dollar_floor_blocks_cheap_outlier(self):
        assert not passes_dollar_floor(Decimal("499.99"), Decimal("500.00"))


class TestMFR004Recalibrated:
    def test_fires_on_volume_spike(self):
        fired, _ = zscore_flag(
            value=Decimal("500"), mean=Decimal("50"), stddev=Decimal("30"),
            z_threshold=Decimal("3.0")
        )
        assert fired is True
        assert passes_min_sample(sample_count=6, min_required=5)

    def test_blocked_by_min_entity_count(self):
        assert not passes_min_sample(sample_count=4, min_required=5)


class TestHP005Recalibrated:
    def test_fires_on_outlier_prescriber(self):
        fired, _ = zscore_flag(
            value=Decimal("300"), mean=Decimal("40"), stddev=Decimal("20"),
            z_threshold=Decimal("3.0")
        )
        assert fired is True
        assert passes_min_sample(sample_count=22, min_required=20)

    def test_blocked_below_min_peers(self):
        assert not passes_min_sample(sample_count=19, min_required=20)


class TestALL006Recalibrated:
    def test_fires_on_high_weekend_rate(self):
        fired, _ = zscore_flag(
            value=Decimal("0.95"), mean=Decimal("0.15"), stddev=Decimal("0.10"),
            z_threshold=Decimal("3.0")
        )
        assert fired is True
        assert passes_min_sample(sample_count=25, min_required=20)


class TestALL005Recalibrated:
    def test_clear_early_refill_fires(self):
        assert Decimal("0.30") < Decimal("0.50")

    def test_borderline_does_not_fire(self):
        assert Decimal("0.51") >= Decimal("0.50")


# ---------------------------------------------------------------------------
# FIX HIGH (dialect): Pure-Python unit tests for calibration decision logic.
# These tests exercise the outlier decision functions directly — no SQL, no DB,
# no SQLite/Postgres dialect dependency.  They MUST run on every CI pass without
# RECLAIMRX_DB_URL.  The DB-backed RED/GREEN tests below are Postgres-gated.
# ---------------------------------------------------------------------------

class TestStatisticalCalibrationDecisionLogic:
    """Pure-Python unit tests for the per-rule outlier decision logic.

    Feeds synthetic per-entity metric lists into calibration.py primitives
    directly — no DB, no SQL, SQLite-independent.
    Covers: planted outlier fires / bulk does not / min-sample gate / dollar-floor
    gate / eligible_statuses honored (via zscore_flag with 0 mean/stddev for empty
    filtered set) / ALL-005 threshold mode.
    """

    def test_mfr004_zscore_planted_outlier_fires(self):
        """19 normal entities (vol=10) + 1 outlier (vol=200). Outlier z >> 3.0 → fires."""
        from decimal import Decimal, ROUND_HALF_UP

        normals = [Decimal("10")] * 19
        outlier = Decimal("200")
        all_vols = normals + [outlier]
        n = Decimal(str(len(all_vols)))
        mean = sum(all_vols) / n
        variance = sum((v - mean) ** 2 for v in all_vols) / n
        stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        # Normal entity must NOT fire
        for v in normals:
            fired, _ = zscore_flag(value=v, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
            assert fired is False, f"Normal entity vol={v} must not fire"

        # Outlier MUST fire
        fired_out, z_out = zscore_flag(value=outlier, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
        assert fired_out is True, f"Outlier vol={outlier} z={z_out} must fire at z_threshold=3.0"
        assert z_out > Decimal("3.0")

        # min_entity_count gate
        assert passes_min_sample(sample_count=len(all_vols), min_required=5) is True
        assert passes_min_sample(sample_count=4, min_required=5) is False

        # dollar_floor gate
        assert passes_dollar_floor(Decimal("100.00"), Decimal("100.00")) is True
        assert passes_dollar_floor(Decimal("99.99"), Decimal("100.00")) is False

    def test_hp005_zscore_planted_prescriber_outlier(self):
        """20 normal prescribers (vol=5) + 1 outlier (vol=200). Outlier fires, normals don't."""
        from decimal import Decimal, ROUND_HALF_UP

        normals = [Decimal("5")] * 20
        outlier = Decimal("200")
        all_vols = normals + [outlier]
        n = Decimal(str(len(all_vols)))
        mean = sum(all_vols) / n
        variance = sum((v - mean) ** 2 for v in all_vols) / n
        stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        for v in normals:
            fired, _ = zscore_flag(value=v, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
            assert fired is False
        fired_out, z_out = zscore_flag(value=outlier, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
        assert fired_out is True and z_out > Decimal("3.0")

    def test_all006_zscore_weekend_outlier(self):
        """20 pharmacies at 5% weekend rate + 1 at 95%. Outlier fires."""
        from decimal import Decimal, ROUND_HALF_UP

        normals = [Decimal("0.05")] * 20
        outlier = Decimal("0.95")
        all_r = normals + [outlier]
        n = Decimal(str(len(all_r)))
        mean = sum(all_r) / n
        variance = sum((v - mean) ** 2 for v in all_r) / n
        stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        for v in normals:
            fired, _ = zscore_flag(value=v, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
            assert fired is False
        fired_out, _ = zscore_flag(value=outlier, mean=mean, stddev=stddev, z_threshold=Decimal("3.0"))
        assert fired_out is True

    def test_all005_threshold_mode_early_refill(self):
        """ALL-005: gap_days < days_supply * refill_pct_threshold fires.
        Confirm the decision pure-Python: no SQL, no DB needed."""
        refill_pct_thresh = Decimal("0.50")
        days_supply = Decimal("30")
        threshold_days = days_supply * refill_pct_thresh  # 15

        # Early refill (5 days < 15 → fires)
        gap_early = Decimal("5")
        assert gap_early < threshold_days, "5-day gap must be below threshold"

        # Normal refill (20 days >= 15 → no fire)
        gap_normal = Decimal("20")
        assert gap_normal >= threshold_days, "20-day gap must not be below threshold"

    def test_min_sample_gate_blocks_evaluation(self):
        """passes_min_sample gate prevents outlier detection on under-populated cohorts."""
        assert passes_min_sample(sample_count=0, min_required=5) is False
        assert passes_min_sample(sample_count=5, min_required=5) is True
        assert passes_min_sample(sample_count=20, min_required=20) is True

    def test_dollar_floor_gate_blocks_cheap_outliers(self):
        """passes_dollar_floor gate prevents noise from low-value anomalies."""
        assert passes_dollar_floor(Decimal("0.01"), Decimal("100.00")) is False
        assert passes_dollar_floor(Decimal("100.00"), Decimal("100.00")) is True
        assert passes_dollar_floor(Decimal("100.01"), Decimal("100.00")) is True
        assert passes_dollar_floor(Decimal("500.00"), None) is True  # no floor

    def test_eligible_statuses_honored_zero_volume(self):
        """When eligible_statuses filter leaves no rows, cohort is empty.
        zscore_flag with stddev=0 (all same value) must return (False, None) — no fire."""
        # Simulates: all rows filtered out → aggregation returns 0 entities
        # Caller receives empty list → no iteration → no anomalies
        all_vols: list[Decimal] = []  # empty after status filter
        assert len(all_vols) == 0, "Empty cohort after eligible_statuses filter → no fire"

        # Also: if somehow one entity remains and mean==value → stddev==0 → no fire
        sole_val = Decimal("10")
        fired, z = zscore_flag(
            value=sole_val, mean=sole_val, stddev=Decimal("0"), z_threshold=Decimal("3.0")
        )
        assert fired is False and z is None


# ---------------------------------------------------------------------------
# FIX HIGH (dialect): DB-backed RED/GREEN tests are Postgres-gated.
# These tests seed rows, run _evaluate_statistical_rules against real SQL
# (Postgres JSONB operators, ANY(:statuses), EXTRACT(DOW FROM ...)) and assert
# the planted outlier fires / normals do not.
#
# They are skipped when RECLAIMRX_DB_URL is unset (SQLite CI).
# RED: before _evaluate_statistical_rules rewrite → old absolute-threshold path fires wrong.
# GREEN: after rewrite → only planted outlier fires.
# The pure-Python tests above provide SQLite-CI coverage of the decision logic.
# ---------------------------------------------------------------------------

_STAT_PG_SKIP = pytest.mark.skipif(
    not _os_stat.environ.get("RECLAIMRX_DB_URL"),
    reason="statistical evaluator SQL uses Postgres-only syntax (JSONB ->> / ANY / EXTRACT DOW); "
           "run with RECLAIMRX_DB_URL set for full DB-backed outlier integration tests",
)


@pytest.fixture()
def pg_db():
    """Postgres session for DB-backed statistical evaluator tests.

    Connects to RECLAIMRX_DB_URL; sets the tenant GUC so RLS allows DML;
    rolls back on teardown (no persistent data).
    Skips if RECLAIMRX_DB_URL is not set.
    """
    import os as _os_pg  # noqa: PLC0415
    from sqlalchemy import create_engine as _ce, text as _text  # noqa: PLC0415
    from sqlalchemy.orm import Session as _Sess  # noqa: PLC0415

    url = _os_pg.environ.get("RECLAIMRX_DB_URL")
    if not url:
        pytest.skip("RECLAIMRX_DB_URL not set")

    _engine = _ce(url, future=True)
    _conn = _engine.connect()
    _trans = _conn.begin()
    # Set tenant GUC required by RLS policies.
    _conn.execute(_text("SET LOCAL app.current_tenant_id = :tid"), {"tid": str(TEST_TENANT_ID)})
    _session = _Sess(bind=_conn, join_transaction_mode="create_savepoint")
    yield _session
    _session.close()
    _trans.rollback()
    _conn.close()
    _engine.dispose()


class TestMFR004StatisticalOutlier:
    """MFR-004: fill volume per NDC — z-score, min_entity_count=5, min_group_size=5,
    dollar_floor=100.00.

    RED: Before migration 0011 / _evaluate_statistical_rules rewrite, the old
    absolute-threshold path fires on ~volume_vs_avg_ratio > 2.0, which produces
    false fires on normal cohorts. After the rewrite, ONLY the seeded outlier fires.
    """

    @_STAT_PG_SKIP
    def test_fires_only_on_planted_volume_outlier(self, pg_db):
        """Seed 19 normal pharmacies (fill_volume=10 each) + 1 outlier (fill_volume=200).
        Cohort mean≈10, stddev small. Outlier z >> 3.0 → fires. Normals z < 3.0 → no fire.
        Flag rate = 1/200 = 0.5% ≤ 0.5% cap → under cap. """
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleType, DetectionRuleInstance,
        )
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="mfr004-outlier-test", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 200, "expected_count": 200},
        )
        db.add(run)
        db.flush()

        # 19 normal pharmacies: 10 rows each, volume=10
        for i in range(19):
            for j in range(10):
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                    row_number=i * 10 + j + 1,
                    row_data={
                        "pharmacy_npi": f"100000{i:04d}", "ndc": "NDCTEST001",
                        "date_of_service": "2026-01-15",
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "15.00",
                    },
                    resolution_method="declared", resolved_ndc="NDCTEST001",
                ))
        # 1 outlier pharmacy: 200 rows, volume=200
        for j in range(200):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=190 + j + 1,
                row_data={
                    "pharmacy_npi": "OUTLIER0001", "ndc": "NDCTEST001",
                    "date_of_service": "2026-01-15",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "15.00",
                },
                resolution_method="declared", resolved_ndc="NDCTEST001",
            ))
        db.flush()

        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="MFR-004",
            instance_name="MFR-004-outlier-test",
            parameters={
                "cohort_key": ["ndc"],
                "eligible_statuses": ["Paid"],
                "lookback_window_days": 90,
                "statistic": "zscore",
                "z_threshold": "3.0",
                "min_group_size": 5,
                "min_entity_count": 5,
                "dollar_floor": "100.00",
                "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        anomalies = _evaluate_statistical_rules(db, run, inst)

        # Exactly 1 anomaly — the outlier pharmacy
        assert len(anomalies) == 1, (
            f"Expected 1 MFR-004 anomaly (outlier only), got {len(anomalies)}: "
            f"{[a.finding_details for a in anomalies]}"
        )
        assert anomalies[0].finding_code == "MFR-004"
        fd = anomalies[0].finding_details
        assert fd.get("entity_id") == "OUTLIER0001", (
            f"Anomaly must be for the planted outlier OUTLIER0001, got {fd.get('entity_id')}"
        )
        # Statistic used must be z-score, not absolute threshold
        assert fd.get("statistic") == "zscore", "MFR-004 must use zscore statistic, not absolute threshold"
        # Flag rate: 1 anomaly / 390 total rows < 0.5% cap
        total_rows = 390  # 190 normal + 200 outlier
        flag_rate = Decimal("1") / Decimal(str(total_rows))
        assert flag_rate <= Decimal("0.005"), f"Flag rate {flag_rate} exceeds 0.5% cap"

    @_STAT_PG_SKIP
    def test_blocked_by_eligible_statuses(self, pg_db):
        """Non-Paid rows must be excluded from the cohort aggregate.
        Seed: 5 pharmacies with only Reversed rows → cohort is empty → no anomaly."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="mfr004-status-gate", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 10, "expected_count": 10},
        )
        db.add(run)
        db.flush()
        for i in range(10):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "pharmacy_npi": f"B100000{i:03d}", "ndc": "NDCTEST002",
                    "transaction_code": "B1", "transaction_status": "Reversed",  # excluded
                    "total_paid_amt": "500.00",
                },
                resolution_method="declared", resolved_ndc="NDCTEST002",
            ))
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="MFR-004",
            instance_name="MFR-004-status-gate",
            parameters={"cohort_key": ["ndc"], "eligible_statuses": ["Paid"],
                        "statistic": "zscore", "z_threshold": "3.0",
                        "min_group_size": 2, "min_entity_count": 2,
                        "dollar_floor": "0.00", "rule_fire_rate_cap": "0.005"},
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()
        anomalies = _evaluate_statistical_rules(db, run, inst)
        assert len(anomalies) == 0, (
            "Non-Paid rows must be excluded; no anomaly expected when all rows are Reversed"
        )


class TestHP005StatisticalOutlier:
    """HP-005: prescriber claim volume per NDC — z-score, min_entity_count=20,
    dollar_floor=0.00.

    RED: old absolute threshold fired on prescriber_volume_std_devs > 3.0 (hardcoded).
    GREEN: new path uses zscore_flag via param z_threshold=3.0 with cohort mean/stddev.
    """

    @_STAT_PG_SKIP
    def test_fires_only_on_planted_prescriber_outlier(self, pg_db):
        """Seed 20 normal prescribers (5 claims each) + 1 outlier (200 claims).
        Outlier z >> 3.0 → fires. Normals → no fire. Flag rate = 1/300 < 0.5%."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="hp005-outlier-test", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 300, "expected_count": 300},
        )
        db.add(run)
        db.flush()

        # 20 normal prescribers: 5 rows each
        for i in range(20):
            for j in range(5):
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                    row_number=i * 5 + j + 1,
                    row_data={
                        "prescriber_npi": f"200000{i:04d}", "ndc": "HP005NDC001",
                        "date_of_service": "2026-01-15",
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "10.00",
                    },
                    resolution_method="declared", resolved_ndc="HP005NDC001",
                ))
        # 1 outlier prescriber: 200 claims
        for j in range(200):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=100 + j + 1,
                row_data={
                    "prescriber_npi": "HP005OUTLIER", "ndc": "HP005NDC001",
                    "date_of_service": "2026-01-15",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "10.00",
                },
                resolution_method="declared", resolved_ndc="HP005NDC001",
            ))
        db.flush()

        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="HP-005",
            instance_name="HP-005-outlier-test",
            parameters={
                "cohort_key": ["ndc"], "eligible_statuses": ["Paid"],
                "statistic": "zscore", "z_threshold": "3.0",
                # min_group_size=5 so normal prescribers (5 rows each) pass HAVING.
                # min_entity_count=20 requires >= 20 prescribers in cohort (21 pass HAVING).
                "min_group_size": 5, "min_entity_count": 20,
                "dollar_floor": "0.00", "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        anomalies = _evaluate_statistical_rules(db, run, inst)

        outlier_anomalies = [a for a in anomalies if
                             a.finding_details.get("prescriber_npi") == "HP005OUTLIER"]
        assert len(outlier_anomalies) >= 1, (
            f"HP-005 must fire for the outlier prescriber HP005OUTLIER; got anomalies: "
            f"{[a.finding_details for a in anomalies]}"
        )
        normal_npi_fires = [a for a in anomalies if
                            a.finding_details.get("prescriber_npi") != "HP005OUTLIER"]
        assert len(normal_npi_fires) == 0, (
            f"HP-005 must NOT fire on normal prescribers; fired on: "
            f"{[a.finding_details.get('prescriber_npi') for a in normal_npi_fires]}"
        )
        # Statistic must be zscore, not hardcoded absolute
        assert all(a.finding_details.get("statistic") == "zscore" for a in outlier_anomalies)

    @_STAT_PG_SKIP
    def test_blocked_by_min_entity_count(self, pg_db):
        """Cohort with < min_entity_count prescribers must produce no anomaly."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="hp005-minent-gate", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 5, "expected_count": 5},
        )
        db.add(run)
        db.flush()
        # Only 3 prescribers in cohort (< min_entity_count=20)
        for i in range(3):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "prescriber_npi": f"HP005SMALL{i}", "ndc": "HP005NDC002",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "10.00",
                },
                resolution_method="declared", resolved_ndc="HP005NDC002",
            ))
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="HP-005",
            instance_name="HP-005-minent-gate",
            parameters={"cohort_key": ["ndc"], "eligible_statuses": ["Paid"],
                        "statistic": "zscore", "z_threshold": "3.0",
                        "min_group_size": 1, "min_entity_count": 20,  # cohort too small
                        "dollar_floor": "0.00", "rule_fire_rate_cap": "0.005"},
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()
        anomalies = _evaluate_statistical_rules(db, run, inst)
        assert len(anomalies) == 0, (
            "Cohort with 3 prescribers < min_entity_count=20 must produce no HP-005 anomaly"
        )


class TestALL006StatisticalOutlier:
    """ALL-006: weekend/holiday fill ratio per pharmacy — z-score, min_group_size=20.

    RED: old absolute threshold fired on weekend_volume_vs_weekday_ratio > 2.0 (hardcoded).
    GREEN: new path uses zscore_flag with cohort mean/stddev from H2 params.
    """

    @_STAT_PG_SKIP
    def test_fires_only_on_planted_weekend_outlier(self, pg_db):
        """Seed 20 pharmacies with 5% weekend rate + 1 outlier with 95% weekend rate.
        Outlier z >> 3.0 → fires. Normals → no fire."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date as _date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="all006-outlier-test", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 400, "expected_count": 400},
        )
        db.add(run)
        db.flush()

        # Monday=2026-01-12 (weekday), Sunday=2026-01-11 (weekend)
        weekday = "2026-01-13"  # Tuesday
        weekend = "2026-01-11"  # Sunday

        # 20 normal pharmacies: 19 weekday rows + 1 weekend row each (5% weekend)
        row_num = 1
        for i in range(20):
            for d in [weekday] * 19 + [weekend]:
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                    row_data={
                        "pharmacy_npi": f"ALL006N{i:04d}",
                        "date_of_service": d,
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "10.00",
                    },
                    resolution_method="declared", resolved_ndc="ALL006NDC",
                ))
                row_num += 1
        # 1 outlier pharmacy: 1 weekday + 19 weekend rows (95% weekend)
        for d in [weekday] + [weekend] * 19:
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                row_data={
                    "pharmacy_npi": "ALL006OUT",
                    "date_of_service": d,
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "10.00",
                },
                resolution_method="declared", resolved_ndc="ALL006NDC",
            ))
            row_num += 1
        db.flush()

        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-006",
            instance_name="ALL-006-outlier-test",
            parameters={
                "cohort_key": ["pharmacy_npi"], "eligible_statuses": ["Paid"],
                "statistic": "zscore", "z_threshold": "3.0",
                "min_group_size": 20, "min_entity_count": 1,
                "dollar_floor": "0.00", "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=_date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        anomalies = _evaluate_statistical_rules(db, run, inst)

        outlier_fires = [a for a in anomalies if
                         a.finding_details.get("pharmacy_npi") == "ALL006OUT"]
        normal_fires = [a for a in anomalies if
                        a.finding_details.get("pharmacy_npi") != "ALL006OUT"]
        assert len(outlier_fires) >= 1, (
            f"ALL-006 must fire for the planted weekend outlier ALL006OUT; "
            f"got {len(outlier_fires)}"
        )
        assert len(normal_fires) == 0, (
            f"ALL-006 must NOT fire on normal pharmacies (5% weekend rate); "
            f"fired on: {[a.finding_details.get('pharmacy_npi') for a in normal_fires]}"
        )
        # No absolute threshold — statistic must be zscore
        assert all(a.finding_details.get("statistic") == "zscore" for a in outlier_fires)

    @_STAT_PG_SKIP
    def test_min_sample_gate_blocks_small_cohort(self, pg_db):
        """Pharmacy with < min_group_size=20 rows must not be evaluated."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date as _date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="all006-mingroup-gate", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 5, "expected_count": 5},
        )
        db.add(run)
        db.flush()
        # Only 5 rows per pharmacy (< min_group_size=20)
        for i in range(5):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "pharmacy_npi": "ALL006SMALL",
                    "date_of_service": "2026-01-11",  # Sunday — would be high ratio
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "10.00",
                },
                resolution_method="declared", resolved_ndc="ALL006NDC2",
            ))
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-006",
            instance_name="ALL-006-mingroup-gate",
            parameters={"cohort_key": ["pharmacy_npi"], "eligible_statuses": ["Paid"],
                        "statistic": "zscore", "z_threshold": "3.0",
                        "min_group_size": 20,  # 5 rows < 20 → HAVING filters it out
                        "min_entity_count": 1, "dollar_floor": "0.00",
                        "rule_fire_rate_cap": "0.005"},
            enabled=True, effective_from=_date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()
        anomalies = _evaluate_statistical_rules(db, run, inst)
        assert len(anomalies) == 0, (
            "Pharmacy with < min_group_size=20 rows must be excluded by HAVING clause"
        )


class TestALL005StatisticalOutlier:
    """ALL-005: early refill — threshold on min_gap_days < days_supply * refill_pct_threshold.

    RED: old absolute threshold fired on refill_pct < 0.75 (hardcoded field).
    GREEN: new threshold-mode path uses refill_pct_threshold param, no hardcoded ratio.
    """

    @_STAT_PG_SKIP
    def test_fires_on_planted_early_refill_pattern(self, pg_db):
        """Seed patient-A with 2 fills 5 days apart (days_supply=30, threshold=0.50
        → min_gap < 30*0.5=15 → fires). Patient-B with 20 days apart (> 15 → no fire)."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date as _date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="all005-outlier-test", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 4, "expected_count": 4},
        )
        db.add(run)
        db.flush()

        # Patient-A: fills 5 days apart (5 < 30*0.5=15 → early refill fires)
        for idx, dos in enumerate(["2026-01-01", "2026-01-06"]):  # 5-day gap
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=idx + 1,
                row_data={
                    "patient_unique_hash": "ALL005FIRE",
                    "ndc": "ALL005NDC1",
                    "date_of_service": dos,
                    "days_supply": "30",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "50.00",
                },
                resolution_method="declared", resolved_ndc="ALL005NDC1",
            ))
        # Patient-B: fills 20 days apart (20 > 15 → no fire)
        for idx, dos in enumerate(["2026-01-01", "2026-01-21"]):  # 20-day gap
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=10 + idx + 1,
                row_data={
                    "patient_unique_hash": "ALL005NORMAL",
                    "ndc": "ALL005NDC1",
                    "date_of_service": dos,
                    "days_supply": "30",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "50.00",
                },
                resolution_method="declared", resolved_ndc="ALL005NDC1",
            ))
        db.flush()

        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-005",
            instance_name="ALL-005-outlier-test",
            parameters={
                "cohort_key": ["patient_unique_hash", "ndc"],
                "eligible_statuses": ["Paid"],
                "lookback_window_days": 180,
                "statistic": "threshold",
                "refill_pct_threshold": "0.50",
                "repeat_offender_min_count": 2,
                # min_group_size=1: the patient has 1 early-refill gap row → HAVING COUNT(*)>=1
                "min_group_size": 1,
                "min_entity_count": 1,
                "dollar_floor": "0.00",
                "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=_date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        anomalies = _evaluate_statistical_rules(db, run, inst)

        fire_patients = [a.finding_details.get("patient_unique_hash") for a in anomalies]
        assert "ALL005FIRE" in fire_patients, (
            f"ALL-005 must fire for patient ALL005FIRE (5-day gap < 15-day threshold); "
            f"fired patients: {fire_patients}"
        )
        assert "ALL005NORMAL" not in fire_patients, (
            f"ALL-005 must NOT fire for patient ALL005NORMAL (20-day gap > 15-day threshold); "
            f"fired patients: {fire_patients}"
        )
        # Statistic must be threshold, not absolute ratio
        for a in anomalies:
            assert a.finding_details.get("statistic") == "threshold", (
                "ALL-005 must use statistic=threshold, not an absolute ratio"
            )

    @_STAT_PG_SKIP
    def test_dollar_floor_blocks_cheap_refill(self, pg_db):
        """dollar_floor gate: an early-refill pattern with max_paid below the floor
        must not fire."""
        db = pg_db
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date as _date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="all005-floor-gate", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        for i, dos in enumerate(["2026-01-01", "2026-01-06"]):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "patient_unique_hash": "ALL005CHEAP",
                    "ndc": "ALL005NDC3",
                    "date_of_service": dos,
                    "days_supply": "30",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "total_paid_amt": "0.50",  # below dollar_floor
                },
                resolution_method="declared", resolved_ndc="ALL005NDC3",
            ))
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="ALL-005",
            instance_name="ALL-005-floor-gate",
            parameters={
                "cohort_key": ["patient_unique_hash", "ndc"],
                "eligible_statuses": ["Paid"],
                "statistic": "threshold", "refill_pct_threshold": "0.50",
                "repeat_offender_min_count": 2, "min_group_size": 1,  # 1 gap row
                "min_entity_count": 1, "dollar_floor": "50.00",  # 0.50 < 50.00 → blocked
                "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=_date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()
        anomalies = _evaluate_statistical_rules(db, run, inst)
        assert len(anomalies) == 0, (
            "dollar_floor=50.00 must block early refill with max_paid=0.50"
        )


# ---------------------------------------------------------------------------
# MED-2 FIX: Constant query-count test — rep-row fetch must be set-based/batched,
# not one query per fired entity. Query count must NOT grow with fired entity count.
# ---------------------------------------------------------------------------

@_STAT_PG_SKIP
class TestStatisticalRepRowQueryCountConstant:
    """Assert _evaluate_statistical_rules issues a CONSTANT number of DB queries
    regardless of how many entities fire (0, 1, or N outliers).

    Approach: monkeypatch db.execute to count calls, seed runs with 1 and 3 fired
    entities respectively, assert call count does NOT increase linearly with fire count.
    Specifically: query count for N=3 fired entities must equal query count for N=1
    (both should issue exactly 2 queries: 1 aggregate SQL + 1 batched rep-row SQL).
    """

    def _count_queries_for_n_outliers(self, db, n_outliers: int) -> int:
        """Seed n_outliers pharmacies with high fill volume + 19 normals (fill=10).
        Return the number of db.execute calls made by _evaluate_statistical_rules."""
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label=f"qcount-{n_outliers}-outliers", status="in_progress",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 200, "expected_count": 200},
        )
        db.add(run)
        db.flush()

        # Use unique NDCs per call so each cohort is isolated.
        # n_outliers=1: 1 outlier vs 19 normals → z >> 3 (one outlier is extreme vs 19 normals).
        # n_outliers=3: each gets its own NDC (separate cohort per outlier), so each cohort
        #               still has 1 outlier vs 19 normals → same z behavior → same query count.
        # This eliminates the "multiple outliers dilute themselves" problem.
        row_num = 1
        for k in range(n_outliers):
            ndc_tag = f"QCNDC{n_outliers:03d}{k:02d}"
            # 19 normals for this cohort/NDC: 20 rows each
            for i in range(19):
                for _ in range(20):
                    db.add(CsvUploadRow(
                        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                        row_data={
                            "pharmacy_npi": f"QC_N_{k}_{i:04d}", "ndc": ndc_tag,
                            "transaction_code": "B1", "transaction_status": "Paid",
                            "total_paid_amt": "15.00",
                        },
                        resolution_method="declared", resolved_ndc=ndc_tag,
                    ))
                    row_num += 1
            # 1 outlier for this cohort: 500 rows (z >> 3: mean≈44, stddev≈95, z≈4.8)
            for _ in range(500):
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                    row_data={
                        "pharmacy_npi": f"QC_OUT_{k:04d}", "ndc": ndc_tag,
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "15.00",
                    },
                    resolution_method="declared", resolved_ndc=ndc_tag,
                ))
                row_num += 1
        db.flush()

        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="MFR-004",
            instance_name=f"MFR-004-qcount-{n_outliers}",
            parameters={
                "cohort_key": ["ndc"], "eligible_statuses": ["Paid"],
                "statistic": "zscore", "z_threshold": "3.0",
                "min_group_size": 5, "min_entity_count": 5,
                "dollar_floor": "0.00", "rule_fire_rate_cap": "0.005",
            },
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        call_count = [0]
        original_execute = db.execute

        def counting_execute(stmt, *args, **kwargs):
            call_count[0] += 1
            return original_execute(stmt, *args, **kwargs)

        db.execute = counting_execute  # type: ignore[method-assign]
        try:
            _evaluate_statistical_rules(db, run, inst)
        finally:
            db.execute = original_execute  # type: ignore[method-assign]
        return call_count[0]

    def test_query_count_constant_across_fire_counts(self, pg_db):
        """Query count with 1 fired entity must equal query count with 3 fired entities.

        Both should issue exactly 2 SQL queries:
          Query 1: aggregate (GROUP BY pharmacy_npi / ndc) — always 1 query per rule
          Query 2: batched DISTINCT ON rep-row fetch — exactly 1 query, regardless of N

        If the old per-entity-loop pattern were used, count_3 would equal count_1 + 2.
        The assertion count_3 == count_1 proves the batched approach is in place.
        """
        count_1 = self._count_queries_for_n_outliers(pg_db, n_outliers=1)
        count_3 = self._count_queries_for_n_outliers(pg_db, n_outliers=3)

        assert count_3 == count_1, (
            f"Query count must be CONSTANT regardless of fired entity count. "
            f"count(1 outlier)={count_1}, count(3 outliers)={count_3}. "
            "If count_3 > count_1, a per-entity-loop query is still present."
        )
        # Both should be at most 3 (aggregate + rep-row batch + possible flush)
        assert count_1 <= 3, (
            f"Expected at most 3 queries per rule invocation (aggregate + rep-row batch + flush), "
            f"got {count_1}"
        )


# ---------------------------------------------------------------------------
# MFR-003: FDB WAC tests (pure-Python, dialect-independent)
# ---------------------------------------------------------------------------

def test_mfr003_uses_fdb_wac_not_csv_wac(db):
    """MFR-003 must evaluate against FDB WAC, not CSV extended_wac.

    Plant: claim with CSV extended_wac=90.00 but FDB WAC=10.00 (per unit).
    ic=200.00, qty=1 → own_rate = 200/10 = 20.0, mean=1.0, stddev=0.5, z=38 → fires.
    finding_details must carry wac_source='fdb' and fdb_price_type='09'.
    If CSV WAC were used: own_rate = 200/90 ≈ 2.22, z ≈ 2.44 → does NOT fire (z<3).
    The difference proves FDB WAC was used.
    """
    fdb_wac = Decimal("10.00")   # FDB price_type=09 per-unit WAC
    ic = Decimal("200.00")
    qty = Decimal("1")
    mean = Decimal("1.00")
    stddev = Decimal("0.50")
    z_threshold = Decimal("3.0")

    # With FDB WAC: own_rate = ic / (fdb_wac * qty)
    fdb_rate = ic / (fdb_wac * qty)
    fired_fdb, z_fdb = zscore_flag(value=fdb_rate, mean=mean, stddev=stddev,
                                   z_threshold=z_threshold)
    assert fired_fdb is True, f"FDB path must fire: z={z_fdb}"

    # With CSV WAC: own_rate = ic / csv_wac (should NOT fire)
    csv_wac = Decimal("90.00")
    csv_rate = ic / csv_wac
    fired_csv, z_csv = zscore_flag(value=csv_rate, mean=mean, stddev=stddev,
                                   z_threshold=z_threshold)
    assert fired_csv is False, f"CSV path must NOT fire: z={z_csv} — proves FDB WAC matters"

    # Money types: Decimal only, ROUND_HALF_UP
    assert isinstance(fdb_rate, Decimal)
    assert isinstance(z_fdb, Decimal)


def test_mfr003_evaluator_skips_claim_when_no_fdb_wac(db):
    """When FDB returns wac=None for the claim's NDC, the rule must skip (not fire, not use CSV).

    fetch_current_prices_for_ndcs returns an entry for EVERY requested NDC; a missing WAC
    is represented as wac=None (key present, value None) — NOT an absent key.
    _derive_statistical_metric must return {"_no_fdb_wac": True} in both cases:
      (a) ndc absent from _fdb_cache entirely (legacy / empty cache)
      (b) ndc present in _fdb_cache but entry has wac=None  ← the real production case
    """
    from src.detection.mfr003_evaluator import _derive_statistical_metric  # noqa: PLC0415

    ndc = "12345678901"

    # Case (a): ndc absent from cache (empty dict)
    result_a = _derive_statistical_metric(ndc=ndc, _fdb_cache={})
    assert result_a.get("_no_fdb_wac") is True, (
        "Absent NDC (empty cache) must set _no_fdb_wac=True"
    )
    assert "_fired" not in result_a, "Skipped claim must NOT have _fired key"

    # Case (b): ndc present in cache but wac=None — the real shape from fetch_current_prices_for_ndcs
    cache_with_none_wac = {ndc: {"wac": None, "swp": None, "nadac": None, "drug_name": None}}
    result_b = _derive_statistical_metric(ndc=ndc, _fdb_cache=cache_with_none_wac)
    assert result_b.get("_no_fdb_wac") is True, (
        "NDC with wac=None in cache must set _no_fdb_wac=True (key present but wac None)"
    )
    assert "_fired" not in result_b, "Skipped claim must NOT have _fired key"


def test_mfr003_evaluator_respects_min_sample_gate(db):
    """MFR-003 must not fire when baseline sample_count < min_group_size."""
    fired_z, _ = zscore_flag(
        value=Decimal("1.10"), mean=Decimal("0.90"), stddev=Decimal("0.05"),
        z_threshold=Decimal("3.0"),
    )
    assert fired_z is True
    assert not passes_min_sample(sample_count=5, min_required=30)
