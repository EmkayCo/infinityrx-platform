"""Tests for atomic guardrail in run_detection (§12 H1).

Reuses conftest.py fixtures: engine, db, TEST_TENANT_ID, TEST_USER_ID.

DEVIATION from plan (noted): plan used SYNTH-HIGH-FIRE custom rule type, but that
code is not in _SINGLE_ROW_CODES/_STATISTICAL_CODES/_GROUPING_CODES so no evaluator
dispatches it, producing 0 fires.  Fix: use MFR-001 (in _SINGLE_ROW_CODES) with
threshold=0.0 so any row with nq_to_wac_ratio present fires.  The plan's intent
(a rule that fires at a rate exceeding the cap) is preserved identically.
MFR-001 also requires required_data_columns=['extended_wac','ingredient_cost_paid',
'dispensing_fee_paid','quantity_dispensed'] to pass gate_rules; firing rows include
all four columns.
"""
from __future__ import annotations
import uuid
from datetime import date
from decimal import Decimal
import pytest
from sqlalchemy import select

from src.detection.batch_engine import run_detection, _TOTAL_FIRE_RATE_CAP, _RULE_FIRE_RATE_CAP
from src.detection.rule_type_registry import register_rule_types, register_rule_instances
from src.models.detection_run_models import (
    Anomaly, DetectionRun, CsvUploadRow, DetectionRuleInstance, DetectionRuleType,
    DetectionRuleEvaluationLog,
)

from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _firing_row_data(i, ratio="1.5", ic="100.00", wac="90.00", total="105.00"):
    """Row data that fires MFR-001 (nq_to_wac_ratio > threshold).

    Includes all required_data_columns for MFR-001 so gate_rules passes it.
    """
    return {
        "patient_unique_hash": f"p{i}",
        "ndc": "00000000001",
        "nq_to_wac_ratio": ratio,
        "ingredient_cost_paid": ic,
        "dispensing_fee_paid": "5.00",
        "extended_wac": wac,
        "quantity_dispensed": "30",
        "total_paid_amt": total,
    }


def _nonfiring_row_data(i):
    """Row data that does NOT fire MFR-001 (required columns absent -> gate skips)."""
    return {"patient_unique_hash": f"nf{i}", "ndc": "00000000002"}




def _low_ratio_row_data(i):
    """Row data with required MFR-001 columns but computed nq_to_wac_ratio < 1.0.

    (ic=50 + fee=5) / wac=90 = 0.611 -- below any threshold >= 1.0, so no fire
    when instance threshold=1.0.  Gate_rules passes because required columns present.
    """
    return {
        "patient_unique_hash": f"low{i}",
        "ndc": "00000000003",
        "ingredient_cost_paid": "50.00",
        "dispensing_fee_paid": "5.00",
        "extended_wac": "90.00",
        "quantity_dispensed": "30",
        "total_paid_amt": "55.00",
    }
def _make_run(db, record_count=200):
    run = DetectionRun(
        tenant_id=TEST_TENANT_ID,
        data_source="csv_upload",
        run_label="guardrail-test",
        status="in_progress",
        created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": record_count, "expected_count": record_count},
    )
    db.add(run)
    db.flush()
    return run


def _seed_rows(db, run, n, row_data_fn=None):
    for i in range(n):
        rd = row_data_fn(i) if row_data_fn else _nonfiring_row_data(i)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID,
            detection_run_id=run.id,
            row_number=i + 1,
            row_data=rd,
            resolution_method="declared",
        ))
    db.flush()


def _add_mfr001_instance(db, tenant_id, threshold=0.0,
                          rule_fire_rate_cap="0.005",
                          instance_name="MFR-001-guardrail-test"):
    """Register MFR-001 rule type + a tenant instance.

    MFR-001 is in _SINGLE_ROW_CODES so _evaluate_single_row_rules dispatches it.
    threshold=0.0 -> every row with nq_to_wac_ratio present fires.
    """
    register_rule_types(db)
    inst = DetectionRuleInstance(
        tenant_id=tenant_id,
        rule_type_code="MFR-001",
        instance_name=instance_name,
        parameters={
            "field": "nq_to_wac_ratio",
            "operator": "gt",
            "threshold": threshold,
            "rule_fire_rate_cap": rule_fire_rate_cap,
        },
        enabled=True,
        effective_from=date.today(),
        created_by=TEST_USER_ID,
    )
    db.add(inst)
    db.flush()
    return inst


class TestGuardrailTrips:
    def test_synthetic_30pct_rule_trips_cap_status_failed(self, db):
        """Rule firing on 100% of rows trips 0.5% per-rule cap -> status='failed', 0 anomalies."""
        run = _make_run(db, record_count=200)
        _seed_rows(db, run, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)

        result = run_detection(db, run)
        db.refresh(run)
        assert run.status == "failed"
        assert run.resolution_stats.get("guardrail", {}).get("tripped") is True
        assert result == 0
        anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()
        assert len(anomalies) == 0

    def test_low_fire_rule_completes(self, db):
        """No enabled rules -> 0 fires -> status='completed'."""
        run = _make_run(db, record_count=1000)
        _seed_rows(db, run, n=1000)
        result = run_detection(db, run)
        db.refresh(run)
        assert run.status == "completed"

    def test_failed_run_persists_no_anomalies(self, db):
        """On guardrail trip, zero Anomaly rows exist for the run."""
        run = _make_run(db, record_count=200)
        _seed_rows(db, run, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)
        run_detection(db, run)
        db.refresh(run)
        assert run.status == "failed"
        assert db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().first() is None


class TestGuardrailResolutionStats:
    def test_guardrail_stats_contain_rule_and_fire_rate(self, db):
        run = _make_run(db, record_count=200)
        _seed_rows(db, run, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)
        run_detection(db, run)
        db.refresh(run)
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert "rule" in g
        assert "fire_rate" in g
        assert "cap" in g


class TestPerRuleCapOverride:
    def test_rule_with_tighter_per_rule_cap_trips_while_total_under_1pct(self, db):
        """MFR-001 with cap=0.001 trips on 0.3% fire rate (< 1% total cap).

        1000 rows: 3 fire (0.3%) -> above 0.1% rule cap -> guardrail trips on rule.
        """
        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="per-rule-cap-test", status="in_progress",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 1000, "expected_count": 1000},
        )
        db.add(run)
        db.flush()

        # 997 below-threshold rows (include required MFR-001 columns so gate_rules passes)
        for i in range(997):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data=_low_ratio_row_data(i),
                resolution_method="declared",
            ))
        # 3 firing rows with ratio=1.5 > threshold=1.0
        for i in range(3):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=997 + i + 1,
                row_data=_firing_row_data(997 + i, ratio="1.5"),
                resolution_method="declared",
            ))
        db.flush()

        _add_mfr001_instance(db, TEST_TENANT_ID,
                              threshold=1.0,
                              rule_fire_rate_cap="0.001",
                              instance_name="MFR-001-tight-cap")

        result = run_detection(db, run)
        db.refresh(run)

        # 3/1000 = 0.3% > 0.1% rule cap -> must trip
        assert run.status == "failed"
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert g.get("rule") == "MFR-001"
        assert result == 0
        assert db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().first() is None


class TestGuardrailBypassPrevention:
    """Configured caps ABOVE the ceiling must be clamped -- bypass is blocked."""

    def test_inflated_total_cap_clamped_to_ceiling(self, db):
        """total_fire_rate_cap='0.99' must NOT bypass the 1% ceiling."""
        run = _make_run(db, record_count=200)
        run.resolution_stats = {
            "inserted_count": 200,
            "expected_count": 200,
            "total_fire_rate_cap": "0.99",
        }
        db.flush()
        _seed_rows(db, run, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)

        result = run_detection(db, run)
        db.refresh(run)

        assert run.status == "failed", (
            "Inflated total_fire_rate_cap='0.99' must be clamped to ceiling 0.01"
        )
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        effective_cap = Decimal(str(g.get("cap", "0")))
        assert effective_cap <= Decimal("0.01"), (
            f"Effective cap {effective_cap} exceeds ceiling 0.01 -- bypass not clamped"
        )
        assert result == 0

    def test_inflated_per_rule_cap_clamped_to_ceiling(self, db):
        """rule_fire_rate_cap='0.50' must be clamped to 0.005 ceiling.

        1000 rows, 6 fire -> 6/1000 = 0.6%.
        0.6% > ceiling (0.5%) -> TRIPS.  0.6% < configured (50%) -> NOT tripped if not clamped.
        Total fire rate = 0.6% < 1% -> total cap is not the trip cause.
        """
        run = _make_run(db, record_count=1000)
        run.resolution_stats = {"inserted_count": 1000, "expected_count": 1000}
        db.flush()

        # 994 below-threshold rows (include required MFR-001 columns so gate_rules passes)
        for i in range(994):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data=_low_ratio_row_data(i),
                resolution_method="declared",
            ))
        # 6 firing rows -> 6/1000 = 0.6% > 0.5% ceiling
        for i in range(6):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=994 + i + 1,
                row_data=_firing_row_data(994 + i, ratio="2.0", ic="200.00",
                                          wac="90.00", total="205.00"),
                resolution_method="declared",
            ))
        db.flush()

        _add_mfr001_instance(db, TEST_TENANT_ID,
                              threshold=1.0,
                              rule_fire_rate_cap="0.50",
                              instance_name="MFR-001-inflated-cap")

        result = run_detection(db, run)
        db.refresh(run)

        assert run.status == "failed", (
            "Inflated rule_fire_rate_cap='0.50' must be clamped to ceiling 0.005; "
            "6/1000 = 0.6% must trip the 0.5% ceiling"
        )
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert g.get("rule") == "MFR-001"
        effective_cap = Decimal(str(g.get("cap", "0")))
        assert effective_cap <= Decimal("0.005"), (
            f"Effective cap {effective_cap} exceeds per-rule ceiling 0.005 -- bypass not clamped"
        )
        assert result == 0


class TestRedetectIdempotency:
    def test_failed_fresh_run_leaves_zero_anomalies_after_prior_stale_seed(self, db):
        """Guardrail trip on fresh run leaves zero anomalies; prior run's anomalies unaffected."""
        prior_run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="stale-prior-run", status="completed",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 5, "expected_count": 5},
        )
        db.add(prior_run)
        db.flush()
        for _ in range(3):
            db.add(Anomaly(
                tenant_id=TEST_TENANT_ID, data_source="csv_upload",
                data_source_run_id=prior_run.id,
                source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
                detection_kind="rule",
                finding_code="STALE-FINDING",
                finding_summary="stale anomaly from prior run",
                finding_details={}, severity="high",
                confidence=Decimal("0.90"), status="open",
            ))
        db.flush()
        prior_count = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == prior_run.id)
        ).scalars().all()
        assert len(prior_count) == 3

        fresh_run = _make_run(db, record_count=200)
        _seed_rows(db, fresh_run, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)

        result = run_detection(db, fresh_run)
        db.refresh(fresh_run)

        assert fresh_run.status == "failed"
        assert result == 0
        fresh_anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == fresh_run.id)
        ).scalars().all()
        assert len(fresh_anomalies) == 0

        prior_after = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == prior_run.id)
        ).scalars().all()
        assert len(prior_after) == 3, (
            f"Prior run stale anomalies deleted unexpectedly: expected 3, got {len(prior_after)}"
        )

    def test_failed_run_with_same_run_preseeded_anomalies_leaves_zero(self, db):
        """Guardrail trip clears pre-existing anomalies on the SAME run.id."""
        run_a = _make_run(db, record_count=200)
        for _ in range(4):
            db.add(Anomaly(
                tenant_id=TEST_TENANT_ID, data_source="csv_upload",
                data_source_run_id=run_a.id,
                source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
                detection_kind="rule",
                finding_code="PRE-EXISTING",
                finding_summary="pre-existing anomaly seeded on same run_id",
                finding_details={}, severity="medium",
                confidence=Decimal("0.75"), status="open",
            ))
        db.flush()
        preseeded = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run_a.id)
        ).scalars().all()
        assert len(preseeded) == 4

        _seed_rows(db, run_a, n=200, row_data_fn=_firing_row_data)
        _add_mfr001_instance(db, TEST_TENANT_ID)

        result = run_detection(db, run_a)
        db.refresh(run_a)

        assert run_a.status == "failed"
        assert "guardrail" in (run_a.resolution_stats or {})
        assert result == 0

        remaining = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run_a.id)
        ).scalars().all()
        assert len(remaining) == 0, (
            f"REGRESSION: failed run_a has {len(remaining)} anomaly rows -- expected 0"
        )


def test_no_finding_not_written_to_eval_log(db):
    """no_finding rows must NOT appear in detection_rule_evaluation_log."""
    run = _make_run(db, record_count=200)
    _seed_rows(db, run, n=5)
    register_rule_types(db)
    run_detection(db, run)
    db.refresh(run)

    no_finding_rows = db.execute(
        select(DetectionRuleEvaluationLog).where(
            DetectionRuleEvaluationLog.detection_run_id == run.id,
            DetectionRuleEvaluationLog.evaluation_result == "no_finding",
        )
    ).scalars().all()
    assert len(no_finding_rows) == 0
    assert "no_finding_count" in run.resolution_stats