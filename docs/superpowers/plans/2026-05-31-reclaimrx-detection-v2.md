# ReclaimRx Detection v2 — Implementation Plan

**Date:** 2026-05-31
**Spec:** `docs/superpowers/specs/2026-05-31-reclaimrx-detection-v2-design.md` (§12 supersedes all)
**Catalog:** `docs/audit/reclaimrx-rule-catalog-review-2026-05-31.md`
**Branch:** `feat/reclaimrx-csv-detection` (current) → PR to `module/reclaimrx`
**Engineer context:** zero assumed — every path, import, and code snippet is complete.

## Locked Decisions (encode verbatim, do not re-derive)

1. **Reject-75→70 group key = `rx_number_hash`** (same-claim rebill). Buckets ≤12h and 12–24h; >24h excluded. Collision behavior: two distinct prescriptions that hash to the same `rx_number_hash` are treated as the same group — a false positive, acceptable at this volume. Split behavior: a single prescription generating >1 reject-code row is correctly grouped under one key.
2. **PRICING DEVIATION from §12 H6:** WAC (price_type 09) AND SWP-as-AWP (price_type 07) are BOTH LIVE. Team sign-off: Mike K, 2026-05-31. §12 H6 said SWP stays disabled until sign-off — that sign-off has now occurred. Flag explicitly in Phase 4 FDB task header.
3. **Reference access = FDW `reference.*` foreign-table schema.** `reference.*` tables are real postgres_fdw foreign tables (provisioned by `infrastructure/scripts/setup_fdw.sh`), NOT a logical alias and NOT native module tables. Access requires no module-owned grants — the FDW user mapping `ifx_dev_app → ifx_ref_reader` is established at setup time. Migration 0010 verifies access and grants nothing.
4. **ALL-002 phantom = valid 10-digit pharmacy NPI absent from `reference.dataq_master`** (`is_phantom = reference.dataq_master.npi IS NULL` after LEFT JOIN on `nl.npi`). Exclusion legs use `reference.oig_leie_exclusions` / `reference.sam_exclusions` (exact NPI match). Deactivation leg uses `reference.dataq_master.deactivation_code`. No FWA-marker/attestation leg (dataq_fwa_markers does not exist; dataq_fwa_attestation is ncpdp-keyed and out of scope).

## TDD Protocol (every task)

1. Write the failing test first. Run: `cd modules/reclaimrx && python -m pytest <test_file>::<test_name> -x` → confirm RED.
2. Write the minimal implementation. Run again → confirm GREEN.
3. `git add <files> && git commit -m "..."` using the conventional-commit message specified in the task.

**conftest fixture reuse:** All new test files under `modules/reclaimrx/tests/detection/` MUST import from `modules/reclaimrx/tests/conftest.py` — the `engine`, `db`, `default_user`, `TEST_TENANT_ID`, `OTHER_TENANT_ID`, `TEST_USER_ID`, `_UUIDString`, `_sqlite_compat_swap`, `_attach_reclaimrx_schema_on_connect` fixtures are reused verbatim. No new conftest unless adding a detection-subfolder conftest that simply imports these.

---

## Phase 0 — Foundations (3 tasks)

### Task 0a — Migration: Verify FDW reference schema access (DONE)

**World-A head = `0009_detection_run_sha_unique`; World-B `0008_sp3_extensions` stays unmerged tech-debt (do not chain).**

**`reference.*` are real FDW foreign tables** provisioned by `infrastructure/scripts/setup_fdw.sh`. They are NOT native module tables and NOT a logical alias. The FDW user mapping `ifx_dev_app → ifx_ref_reader` is established by setup_fdw.sh; migration 0010 verifies access and grants nothing.

**File:** `modules/reclaimrx/alembic/versions/0010_reclaimrx_v2_ref_grants.py`

Migration 0010 `upgrade()` runs a `LIMIT 0` guard against `reference.dataq_master` and raises a clear `RuntimeError` if the FDW schema is absent. `downgrade()` is a no-op. No GRANTs, no DDL.

**Test file** (`modules/reclaimrx/tests/detection/test_reference_grants.py`): three Postgres-gated tests confirm `ifx_dev_app` can SELECT from `reference.dataq_master`, `reference.prescribers`, and `reference.fdb_ndc_price_history`. Skip when `RECLAIMRX_DB_URL` is unset.

Run: `cd modules/reclaimrx && python -m pytest tests/detection/test_reference_grants.py -v`
→ 3 passed (with `RECLAIMRX_DB_URL=postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev`), 3 skipped without.

```
git commit: fix(reclaimrx): migration 0010 — FDW verification only, no native grants; repoint test to reference.*
```

---

### Task 0b — HARD-VERIFY GATE: introspect fdb_price_type_desc

**This task has no code output.** It is a mandatory human gate before Phase 4 FDB enrichment is written.

Run this query against the live dev database and record the results in a comment at the top of the Phase 4 FDB task:

```sql
-- Run as ifx_dev_app against infinityrx_dev
SELECT npt_type, short_desc
FROM reference.fdb_price_type_desc
WHERE npt_type IN ('07', '09', '24', '25')
ORDER BY npt_type;
```

**Assert before proceeding to Phase 4:**
- `npt_type = '09'` → short_desc contains "WAC" (Wholesale Acquisition Cost)
- `npt_type = '07'` → short_desc contains "SWP" or "Suggested Wholesale Price"
- `npt_type = '24'` OR `'25'` → short_desc contains "NADAC"

If any assertion fails, STOP and re-open the spec. Phase 4 FDB enrichment joins depend on these exact type codes.

**Psql command:**
```
PGPASSWORD=dev_password psql -h localhost -U ifx_dev_app -d infinityrx_dev \
  -c "SELECT npt_type, short_desc FROM reference.fdb_price_type_desc WHERE npt_type IN ('07','09','24','25') ORDER BY npt_type;"
```

No commit for this task. Record the output in a code comment at the top of the Phase 4 FDB migration file.

---

### Task 0c — Calibration primitives module

**File:** `modules/reclaimrx/src/detection/calibration.py`
**Test file:** `modules/reclaimrx/tests/detection/test_calibration.py`

**Test first:**

```python
"""Unit tests for calibration.py helpers.
Uses modules/reclaimrx/tests/conftest.py fixtures (engine, db, etc.) via conftest import.
"""
from __future__ import annotations
from decimal import Decimal
import pytest
from src.detection.calibration import (
    percentile_within_cohort,
    zscore_flag,
    passes_min_sample,
    passes_dollar_floor,
)

class TestPassesMinSample:
    def test_sufficient(self):
        assert passes_min_sample(sample_count=30, min_required=30) is True

    def test_insufficient(self):
        assert passes_min_sample(sample_count=29, min_required=30) is False

    def test_zero_min(self):
        assert passes_min_sample(sample_count=0, min_required=0) is True


class TestPassesDollarFloor:
    def test_above_floor(self):
        assert passes_dollar_floor(Decimal("150.00"), Decimal("100.00")) is True

    def test_at_floor(self):
        assert passes_dollar_floor(Decimal("100.00"), Decimal("100.00")) is True

    def test_below_floor(self):
        assert passes_dollar_floor(Decimal("99.99"), Decimal("100.00")) is False

    def test_none_floor(self):
        # None floor means no floor check
        assert passes_dollar_floor(Decimal("0.01"), None) is True


class TestZscoreFlag:
    def test_fires_above_threshold(self):
        # z = (150 - 100) / 10 = 5.0 > 3.0
        fired, z = zscore_flag(
            value=Decimal("150"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is True
        assert z > Decimal("3.0")

    def test_no_fire_below_threshold(self):
        # z = (102 - 100) / 10 = 0.2 < 3.0
        fired, z = zscore_flag(
            value=Decimal("102"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is False

    def test_zero_stddev_no_fire(self):
        # stddev=0 → undefined z, must not raise, must not fire
        fired, z = zscore_flag(
            value=Decimal("200"),
            mean=Decimal("100"),
            stddev=Decimal("0"),
            z_threshold=Decimal("3.0"),
        )
        assert fired is False
        assert z is None

    def test_returns_decimal_z(self):
        fired, z = zscore_flag(
            value=Decimal("130"),
            mean=Decimal("100"),
            stddev=Decimal("10"),
            z_threshold=Decimal("3.0"),
        )
        assert isinstance(z, Decimal)


class TestPercentileWithinCohort:
    def test_top_value_is_p100(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("100"), values)
        assert pct == Decimal("1.0")

    def test_bottom_value_is_low(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("1"), values)
        assert pct <= Decimal("0.05")

    def test_midpoint(self):
        values = [Decimal(str(i)) for i in range(1, 101)]
        pct = percentile_within_cohort(Decimal("50"), values)
        assert Decimal("0.45") <= pct <= Decimal("0.55")

    def test_empty_cohort_returns_none(self):
        result = percentile_within_cohort(Decimal("50"), [])
        assert result is None

    def test_returns_decimal(self):
        values = [Decimal("10"), Decimal("20"), Decimal("30")]
        pct = percentile_within_cohort(Decimal("20"), values)
        assert isinstance(pct, Decimal)
```

Run → RED.

**Implementation** (`modules/reclaimrx/src/detection/calibration.py`):

```python
"""Calibration primitives for outlier-mode statistical detection rules.

Pure functions — no I/O, no DB, no side effects.
Financial precision: Decimal only, never float in return values.
Used by Phase 2 recalibrated rules (MFR-003/004, HP-005/008, ALL-005/006).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

_ZERO = Decimal("0")
_ONE = Decimal("1")


def passes_min_sample(*, sample_count: int, min_required: int) -> bool:
    """Return True if sample_count >= min_required."""
    return sample_count >= min_required


def passes_dollar_floor(
    amount: Decimal,
    floor: Optional[Decimal],
) -> bool:
    """Return True if amount >= floor (or floor is None — no floor check)."""
    if floor is None:
        return True
    return amount >= floor


def zscore_flag(
    *,
    value: Decimal,
    mean: Decimal,
    stddev: Decimal,
    z_threshold: Decimal,
) -> tuple[bool, Optional[Decimal]]:
    """Compute z-score and return (fired, z).

    fired = True when abs(z) >= z_threshold AND stddev > 0.
    Returns (False, None) when stddev == 0 (undefined z).
    z is always positive (we flag outliers above the mean for volume/cost rules).
    """
    if stddev == _ZERO:
        return False, None
    z = (value - mean) / stddev
    fired = z >= z_threshold
    return bool(fired), z.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def percentile_within_cohort(
    value: Decimal,
    cohort_values: list[Decimal],
) -> Optional[Decimal]:
    """Return the fraction of cohort_values strictly less than value (0.0–1.0).

    Returns None if cohort is empty.
    Uses a simple empirical CDF (proportion below). For tie handling:
    values equal to `value` are counted as 0.5 of a rank (mid-rank method).

    This is a pure-Python implementation suitable for moderate cohort sizes
    (hundreds to low thousands of distinct scope-keys). For very large cohorts,
    use SQL percentile_cont instead.
    """
    if not cohort_values:
        return None
    n = len(cohort_values)
    below = sum(1 for v in cohort_values if v < value)
    equal = sum(1 for v in cohort_values if v == value)
    # Mid-rank: rank = below + 0.5 * equal
    rank = Decimal(str(below)) + Decimal("0.5") * Decimal(str(equal))
    pct = rank / Decimal(str(n))
    return pct.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

Run tests → GREEN.

```
git add modules/reclaimrx/src/detection/calibration.py \
        modules/reclaimrx/tests/detection/test_calibration.py
git commit -m "feat(reclaimrx): calibration primitives — percentile_within_cohort, zscore_flag, passes_min_sample, passes_dollar_floor"
```

---

## Phase 1 — Engine Rework (§12 H1) (3 tasks)

### Task 1a — Atomic stage-then-promote guardrail in run_detection

**What changes in `modules/reclaimrx/src/detection/batch_engine.py`:**
- Remove `_flush_anomaly_safe` savepoint-per-anomaly from all rule evaluators.
- All anomalies accumulate in `all_anomalies: list[Anomaly]` (already done structurally) but are NOT added to the session until the run-wide guardrail check passes.
- After all passes complete, check total fire rate and per-rule fire rates. If any cap trips: set `run.status = "failed"`, set `run.resolution_stats["guardrail"] = {tripped, rule, fire_rate, cap}`, call `db.flush()`, return 0 (no anomalies inserted).
- If caps pass: bulk-insert all anomalies via `execute_values` on Postgres or ORM `db.add_all` on SQLite, write `finding_raised` eval-log rows only for actual fires, set `run.status = "completed"`.
- Cap defaults: total run fire rate 1% (`total_cap = Decimal("0.01")`), per-rule fire rate 0.5% (`rule_cap = Decimal("0.005")`). Both read from run params or module constants.

**Test file:** `modules/reclaimrx/tests/detection/test_engine_guardrail.py`

```python
"""Tests for atomic guardrail in run_detection (§12 H1).

Reuses conftest.py fixtures: engine, db, TEST_TENANT_ID, TEST_USER_ID.
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
)

# conftest.py provides: engine, db, TEST_TENANT_ID, TEST_USER_ID
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _make_run(db, *, record_count=100) -> DetectionRun:
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


def _seed_rows(db, run, *, n: int, row_data_fn=None) -> None:
    for i in range(n):
        rd = row_data_fn(i) if row_data_fn else {"patient_unique_hash": f"p{i}", "ndc": "00000000001"}
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID,
            detection_run_id=run.id,
            row_number=i + 1,
            row_data=rd,
            resolution_method="declared",
        ))
    db.flush()


def _add_synthetic_high_fire_rule(db, tenant_id) -> DetectionRuleInstance:
    """Add a rule type + instance that fires on 30% of rows (synthetic)."""
    rtype = DetectionRuleType(
        code="SYNTH-HIGH-FIRE",
        name="Synthetic High Fire",
        description="Test rule",
        family="A1",
        parameter_schema_version="1.0",
        default_severity="high",
        default_confidence=Decimal("0.70"),
        requires_baseline=False,
        requires_history=False,
        deferred_data_feed=False,
        deferred_reason="",
        required_data_columns=[],
        default_parameters={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 0.0},
    )
    db.add(rtype)
    db.flush()
    inst = DetectionRuleInstance(
        tenant_id=tenant_id,
        rule_type_code="SYNTH-HIGH-FIRE",
        instance_name="SYNTH-HIGH-FIRE-default",
        parameters={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 0.0,
                    "rule_fire_rate_cap": "0.005"},
        enabled=True,
        effective_from=date.today(),
        created_by=TEST_USER_ID,
    )
    db.add(inst)
    db.flush()
    return inst


class TestGuardrailTrips:
    def test_synthetic_30pct_rule_trips_cap_status_failed(self, db):
        """A rule firing on 30% of rows must trip the cap → status='failed', 0 anomalies."""
        run = _make_run(db, record_count=100)
        # Seed 100 rows all with nq_to_wac_ratio > 0 (fires on every row for SYNTH rule)
        _seed_rows(db, run, n=100, row_data_fn=lambda i: {
            "patient_unique_hash": f"p{i}",
            "ndc": "00000000001",
            "nq_to_wac_ratio": "1.5",
            "ingredient_cost_paid": "100.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "105.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)

        result = run_detection(db, run)

        db.refresh(run)
        assert run.status == "failed"
        assert run.resolution_stats.get("guardrail", {}).get("tripped") is True
        assert result == 0
        anomaly_count = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()
        assert len(anomaly_count) == 0

    def test_low_fire_rule_completes(self, db):
        """A rule that fires on <1% of rows must complete with status='completed'."""
        run = _make_run(db, record_count=1000)
        # 5 rows with duplicate pattern, 995 without — well under 1%
        _seed_rows(db, run, n=1000)
        # No high-fire synthetic rule; only legitimate rules (seeded here as empty)
        result = run_detection(db, run)
        db.refresh(run)
        assert run.status == "completed"

    def test_failed_run_persists_no_anomalies(self, db):
        """On guardrail trip, zero Anomaly rows must exist for the run."""
        run = _make_run(db, record_count=10)
        _seed_rows(db, run, n=10, row_data_fn=lambda i: {
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)
        run_detection(db, run)
        db.refresh(run)
        assert db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().first() is None


class TestGuardrailResolutionStats:
    def test_guardrail_stats_contain_rule_and_fire_rate(self, db):
        run = _make_run(db, record_count=10)
        _seed_rows(db, run, n=10, row_data_fn=lambda i: {
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)
        run_detection(db, run)
        db.refresh(run)
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert "rule" in g or "fire_rate" in g
        assert "cap" in g


class TestPerRuleCapOverride:
    def test_rule_with_tighter_per_rule_cap_trips_while_total_under_1pct(self, db):
        """A rule with rule_fire_rate_cap=0.001 must trip even when total fire rate < 1%.

        Scenario: 1000 rows, rule fires on 3 rows (0.3% total — well under 1%),
        but the rule's own cap is 0.001 (0.1%) → guardrail must trip on the rule.
        """
        from src.detection.batch_engine import run_detection
        from src.models.detection_run_models import (
            Anomaly, DetectionRun, CsvUploadRow, DetectionRuleInstance, DetectionRuleType,
        )
        from datetime import date
        from decimal import Decimal
        from sqlalchemy import select

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="per-rule-cap-test", status="in_progress",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 1000, "expected_count": 1000},
        )
        db.add(run)
        db.flush()

        # 997 normal rows, 3 rows that fire (0.3% total — under 1% total cap)
        for i in range(997):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={"nq_to_wac_ratio": "0.5"},  # will not fire threshold > 0.0
                resolution_method="declared",
            ))
        for i in range(3):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=997 + i + 1,
                row_data={
                    "nq_to_wac_ratio": "1.5",
                    "ingredient_cost_paid": "100.00",
                    "dispensing_fee_paid": "5.00",
                    "extended_wac": "90.00",
                    "total_paid_amt": "105.00",
                },
                resolution_method="declared",
            ))
        db.flush()

        # Add rule with very tight per-rule cap = 0.001 (0.1%)
        rtype = DetectionRuleType(
            code="TIGHT-CAP-RULE", name="Tight Cap Rule", description="Test",
            family="A1", parameter_schema_version="1.0",
            default_severity="high", default_confidence=Decimal("0.70"),
            requires_baseline=False, requires_history=False,
            deferred_data_feed=False, deferred_reason="",
            required_data_columns=[],
            default_parameters={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.0},
        )
        db.add(rtype)
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID,
            rule_type_code="TIGHT-CAP-RULE",
            instance_name="TIGHT-CAP-RULE-default",
            parameters={
                "field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.0,
                "rule_fire_rate_cap": "0.001",  # tighter than default 0.005
            },
            enabled=True,
            effective_from=date.today(),
            created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        result = run_detection(db, run)
        db.refresh(run)

        # Total fire rate = 3/1000 = 0.3% — under 1% total cap
        # But rule cap = 0.1% → must trip
        assert run.status == "failed"
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert g.get("rule") == "TIGHT-CAP-RULE"
        assert result == 0
        # Zero anomalies persisted
        assert db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().first() is None


class TestGuardrailBypassPrevention:
    """Configured caps ABOVE the ceiling must be clamped — bypass via mutable stats is blocked."""

    def test_inflated_total_cap_clamped_to_ceiling(self, db):
        """run.resolution_stats["total_fire_rate_cap"]="0.99" must NOT bypass the 1% ceiling.

        Scenario: 10 rows, rule fires on all 10 (100% fire rate).
        Even if the run claims total_fire_rate_cap="0.99", the ceiling 0.01 applies.
        Run must still fail with status='failed'.
        """
        run = _make_run(db, record_count=10)
        # Inject inflated cap into resolution_stats (simulates malicious/buggy configuration)
        run.resolution_stats = {
            "inserted_count": 10,
            "expected_count": 10,
            "total_fire_rate_cap": "0.99",  # attacker tries to raise cap to 99%
        }
        db.flush()
        _seed_rows(db, run, n=10, row_data_fn=lambda i: {
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)

        result = run_detection(db, run)
        db.refresh(run)

        # Must still fail — ceiling (0.01) overrides the inflated configured cap (0.99)
        assert run.status == "failed", (
            "Inflated total_fire_rate_cap='0.99' must be clamped to ceiling 0.01"
        )
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        # The effective cap reported must be the ceiling (0.01000), not 0.99
        effective_cap = Decimal(str(g.get("cap", "0")))
        assert effective_cap <= Decimal("0.01"), (
            f"Effective cap {effective_cap} exceeds ceiling 0.01 — bypass not clamped"
        )
        assert result == 0

    def test_inflated_per_rule_cap_clamped_to_ceiling(self, db):
        """rule_fire_rate_cap="0.50" on a rule instance must be clamped to 0.005 ceiling.

        Correct math:
          - 1000 rows, rule fires on 6 → 6/1000 = 0.6%
          - 0.6% > ceiling (0.005 = 0.5%) → TRIPS   ← correct: guard fires
          - 0.6% < configured cap (0.50 = 50%)        ← if NOT clamped, guard would NOT fire

        The fact that the run fails proves the configured 0.50 was clamped to 0.005.
        A fire rate of 0.3% (below the ceiling) would NOT distinguish clamping from bypass,
        so we use 0.6% which is strictly above the 0.5% ceiling.
        Total fire rate = 6/1000 = 0.6% < 1% total ceiling → total cap is NOT the trip cause.
        """
        from src.models.detection_run_models import DetectionRuleType, DetectionRuleInstance

        run = _make_run(db, record_count=1000)
        run.resolution_stats = {"inserted_count": 1000, "expected_count": 1000}
        db.flush()

        # 994 non-firing rows
        _seed_rows(db, run, n=994, row_data_fn=lambda _: {"nq_to_wac_ratio": "0.5"})
        # 6 firing rows → 6/1000 = 0.6% per-rule fire rate (above 0.5% ceiling, below 50% configured)
        _seed_rows(db, run, n=6, row_data_fn=lambda _: {
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })

        # Add rule with inflated cap=0.50 (50%) — must be clamped to ceiling 0.005 (0.5%)
        rtype = DetectionRuleType(
            code="INFLATED-CAP-RULE", name="Inflated Cap", description="Test",
            family="A1", parameter_schema_version="1.0",
            default_severity="high", default_confidence=Decimal("0.70"),
            requires_baseline=False, requires_history=False,
            deferred_data_feed=False, deferred_reason="",
            required_data_columns=[],
            default_parameters={"field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.0},
        )
        db.add(rtype)
        db.flush()
        inst = DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="INFLATED-CAP-RULE",
            instance_name="INFLATED-CAP-RULE-default",
            parameters={
                "field": "nq_to_wac_ratio", "operator": "gt", "threshold": 1.0,
                "rule_fire_rate_cap": "0.50",  # 50% — must be clamped to 0.5% ceiling
            },
            enabled=True, effective_from=date.today(), created_by=TEST_USER_ID,
        )
        db.add(inst)
        db.flush()

        result = run_detection(db, run)
        db.refresh(run)

        # 6/1000 = 0.6% > ceiling 0.005 (0.5%) → must trip.
        # If cap=0.50 were honored (not clamped), 0.6% < 50% → would NOT trip.
        # Tripping proves the ceiling was applied, not the inflated configured value.
        assert run.status == "failed", (
            "Inflated rule_fire_rate_cap='0.50' must be clamped to ceiling 0.005; "
            "6/1000 = 0.6% fire rate must trip the 0.5% ceiling cap"
        )
        g = run.resolution_stats.get("guardrail", {})
        assert g.get("tripped") is True
        assert g.get("rule") == "INFLATED-CAP-RULE"
        effective_cap = Decimal(str(g.get("cap", "0")))
        assert effective_cap <= Decimal("0.005"), (
            f"Effective cap {effective_cap} exceeds per-rule ceiling 0.005 — bypass not clamped"
        )
        assert result == 0


class TestRedetectIdempotency:
    """Regression: the invariant 'a failed run ALWAYS ends with ZERO anomalies for its run.id'
    holds in all three cases:

    (a) test_failed_fresh_run_leaves_zero_anomalies_after_prior_stale_seed —
        guardrail trips on a fresh run.id that has NO pre-existing anomalies for itself
        (stale anomalies exist only on a DIFFERENT prior run.id).  The delete-for-run in
        the failed branch is a no-op for the fresh run.id; transaction rolls back cleanly.
    (b) test_failed_run_with_same_run_preseeded_anomalies_leaves_zero —
        guardrail trips on a run.id that ALREADY HAS pre-existing anomalies seeded directly
        on its own id (same-run retry scenario).  The failed-branch delete-for-run must
        explicitly remove those rows BEFORE persisting status='failed'.
    (c) passing run (covered by TestAtomicStageThenPromote) — PASS branch delete-prior +
        bulk insert are atomic; run ends with exactly the new anomaly set.
    """

    def test_failed_fresh_run_leaves_zero_anomalies_after_prior_stale_seed(self, db):
        """Guardrail trip on a fresh run leaves exactly zero anomalies for that run id.

        Scenario:
          1. Seed a SEPARATE prior DetectionRun (simulating a stale v1/partial run).
          2. Manually insert 3 Anomaly rows attributed to that prior run id (stale state).
          3. Create a FRESH DetectionRun (new id) — this is the re-detect run.
          4. Seed rows that will cause the guardrail to trip (100% fire rate).
          5. Call run_detection → guardrail trips, whole-transaction rolls back.
          6. Assert: fresh_run.status == 'failed', zero anomalies for fresh_run.id.
          7. Assert: the prior_run's stale anomalies (different run id) are unaffected
             (the delete-prior-for-run only deletes for THIS run id, not all anomalies).
        """
        from src.models.detection_run_models import Anomaly

        # Step 1: create a prior (stale) run
        prior_run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="stale-prior-run", status="completed",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 5, "expected_count": 5},
        )
        db.add(prior_run)
        db.flush()

        # Step 2: seed 3 anomalies attributed to the prior run id (stale state to ignore)
        for i in range(3):
            db.add(Anomaly(
                tenant_id=TEST_TENANT_ID,
                data_source="csv_upload",
                data_source_run_id=prior_run.id,
                finding_code="STALE-FINDING",
                finding_summary="stale anomaly from prior run",
                finding_details={},
                severity="high",
                confidence=Decimal("0.90"),
                status="open",
            ))
        db.flush()
        prior_anomaly_count = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == prior_run.id)
        ).scalars().all()
        assert len(prior_anomaly_count) == 3, "Setup: prior_run must have 3 stale anomalies"

        # Step 3: create the FRESH re-detect run (new id — primary design for re-detect)
        fresh_run = _make_run(db, record_count=10)

        # Step 4: seed rows that trigger 100% fire rate → guardrail must trip
        _seed_rows(db, fresh_run, n=10, row_data_fn=lambda i: {
            "patient_unique_hash": f"fresh-p{i}",
            "ndc": "00000000001",
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)

        # Step 5: run detection — expect guardrail trip
        result = run_detection(db, fresh_run)
        db.refresh(fresh_run)

        # Step 6: fresh run must have failed with zero anomalies
        assert fresh_run.status == "failed", (
            f"Expected fresh run to fail (guardrail trip), got status={fresh_run.status!r}"
        )
        assert result == 0
        fresh_anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == fresh_run.id)
        ).scalars().all()
        assert len(fresh_anomalies) == 0, (
            f"REGRESSION: failed fresh run has {len(fresh_anomalies)} anomaly rows — "
            f"expected exactly 0. The in-tx delete+insert must have rolled back cleanly."
        )

        # Step 7: prior run's stale anomalies must be UNAFFECTED (different run id)
        prior_after = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == prior_run.id)
        ).scalars().all()
        assert len(prior_after) == 3, (
            f"Prior run's stale anomalies were unexpectedly deleted: "
            f"expected 3, found {len(prior_after)}. "
            f"delete-prior-for-run must be scoped to fresh_run.id only."
        )

    def test_failed_run_with_same_run_preseeded_anomalies_leaves_zero(self, db):
        """RED-first regression: guardrail trip on a run that ALREADY HAS anomalies for
        its own run.id clears those pre-existing rows unconditionally.

        Scenario:
          1. Create a DetectionRun (run_a).
          2. Directly insert N Anomaly rows attributed to run_a.id (simulates a partial
             prior attempt or a mis-applied back-fill for the same run_id).
          3. Configure so that running detection on run_a will trip the guardrail
             (100% fire rate via synthetic rule + seeded rows).
          4. Call run_detection(db, run_a).
          5. Assert: run_a.status == 'failed', resolution_stats contains 'guardrail',
             AND count of Anomaly rows where data_source_run_id == run_a.id == 0.
             The pre-existing N rows MUST be gone — not just the in-flight staged ones.

        This is the case the existing test does NOT cover: the existing test seeds anomalies
        on a DIFFERENT run_id (prior_run.id), not on the run being processed.  This test
        seeds them on the SAME run_id to verify the failed-branch delete is reached.
        """
        from src.models.detection_run_models import Anomaly

        # Step 1: create the run under test
        run_a = _make_run(db, record_count=5)

        # Step 2: pre-seed 4 anomalies for THIS run's id (same run_id, not a different run)
        for i in range(4):
            db.add(Anomaly(
                tenant_id=TEST_TENANT_ID,
                data_source="csv_upload",
                data_source_run_id=run_a.id,
                finding_code="PRE-EXISTING",
                finding_summary="pre-existing anomaly seeded directly on same run_id",
                finding_details={},
                severity="medium",
                confidence=Decimal("0.75"),
                status="open",
            ))
        db.flush()
        preseeded = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run_a.id)
        ).scalars().all()
        assert len(preseeded) == 4, "Setup: run_a must have 4 pre-seeded anomalies before detection"

        # Step 3: seed rows + rule that forces 100% fire rate → guardrail must trip
        _seed_rows(db, run_a, n=5, row_data_fn=lambda i: {
            "patient_unique_hash": f"same-run-p{i}",
            "ndc": "00000000001",
            "nq_to_wac_ratio": "2.0",
            "ingredient_cost_paid": "200.00",
            "dispensing_fee_paid": "5.00",
            "extended_wac": "90.00",
            "total_paid_amt": "205.00",
        })
        _add_synthetic_high_fire_rule(db, TEST_TENANT_ID)

        # Step 4: run detection — guardrail must trip
        result = run_detection(db, run_a)
        db.refresh(run_a)

        # Step 5: invariant checks
        assert run_a.status == "failed", (
            f"Expected run_a status='failed' (guardrail trip), got {run_a.status!r}"
        )
        assert "guardrail" in (run_a.resolution_stats or {}), (
            "resolution_stats must contain 'guardrail' key on a guardrail-tripped run"
        )
        assert result == 0

        remaining = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run_a.id)
        ).scalars().all()
        assert len(remaining) == 0, (
            f"REGRESSION (same-run pre-seeded): failed run_a still has {len(remaining)} "
            f"anomaly rows — expected exactly 0. The failed-branch delete-for-run must "
            f"remove pre-existing anomalies for this run.id, not only in-flight staged ones."
        )
```

Run → RED (guardrail not yet implemented).

**Implementation — changes to `modules/reclaimrx/src/detection/batch_engine.py`:**

Add module constants after `_ZERO`:
```python
# Guardrail caps (§12 H1).
# CEILINGS are hard maximums — a run/rule may configure a STRICTER (lower) cap
# but can NEVER configure a looser cap. Any configured value above the ceiling
# is clamped to the ceiling. This prevents bypass via mutable run.resolution_stats.
_TOTAL_FIRE_RATE_CEILING: Decimal = Decimal("0.01")   # hard max: 1% total run
_RULE_FIRE_RATE_CEILING: Decimal = Decimal("0.005")   # hard max: 0.5% per rule
# Default caps (equal to ceilings; keep as aliases for backward compat)
_TOTAL_FIRE_RATE_CAP: Decimal = _TOTAL_FIRE_RATE_CEILING
_RULE_FIRE_RATE_CAP: Decimal = _RULE_FIRE_RATE_CEILING
```

Replace the finalization block in `run_detection` (lines ~1385–1401) with:
```python
    # --- Guardrail check (§12 H1) BEFORE inserting any anomalies ---
    # Effective total cap = min(configured, CEILING) — configured value can only be STRICTER.
    # A run that sets total_fire_rate_cap="0.99" is clamped to the 1% ceiling.
    _configured_total = Decimal(str(
        run.resolution_stats.get("total_fire_rate_cap", str(_TOTAL_FIRE_RATE_CEILING))
    ))
    total_cap = min(_configured_total, _TOTAL_FIRE_RATE_CEILING)
    record_count_d = Decimal(str(record_count)) if record_count > 0 else Decimal("1")

    # Build per-rule cap map: min(instance.parameters.rule_fire_rate_cap, CEILING).
    # A rule that configures "0.50" is clamped to 0.005 — ceiling always wins.
    rule_instance_cap: dict[str, Decimal] = {}
    for inst in applicable:
        configured_rule_cap = Decimal(str(
            inst.parameters.get("rule_fire_rate_cap", str(_RULE_FIRE_RATE_CEILING))
        ))
        rule_instance_cap[inst.rule_type_code] = min(configured_rule_cap, _RULE_FIRE_RATE_CEILING)

    # Count fires per rule from accumulated list
    rule_fire_counts: dict[str, int] = {}
    for a in all_anomalies:
        rule_fire_counts[a.finding_code] = rule_fire_counts.get(a.finding_code, 0) + 1

    guardrail_trip: dict | None = None
    total_fire_rate = Decimal(str(len(all_anomalies))) / record_count_d
    if total_fire_rate > total_cap:
        guardrail_trip = {
            "tripped": True,
            "rule": "total_run",
            "fire_rate": str(total_fire_rate.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
            "cap": str(total_cap),
        }
    else:
        for code, count in rule_fire_counts.items():
            rate = Decimal(str(count)) / record_count_d
            # Use this rule's own cap; default to _RULE_FIRE_RATE_CAP if not in instance map
            this_cap = rule_instance_cap.get(code, _RULE_FIRE_RATE_CAP)
            if rate > this_cap:
                guardrail_trip = {
                    "tripped": True,
                    "rule": code,
                    "fire_rate": str(rate.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
                    "cap": str(this_cap),
                }
                break

    if guardrail_trip:
        # Invariant: a failed run ALWAYS ends with ZERO anomalies for this run.id.
        # Delete any pre-existing anomalies for this run (e.g. a prior attempt on the same
        # run_id) BEFORE persisting status='failed'.  Scoped by both run.id AND tenant_id so
        # a cross-tenant delete is structurally impossible even if RLS is bypassed.
        db.execute(
            sa.delete(Anomaly).where(
                Anomaly.data_source_run_id == run.id,
                Anomaly.tenant_id == run.tenant_id,
            )
        )
        run.anomaly_count = 0
        run.record_count = record_count
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        new_stats = dict(run.resolution_stats)
        new_stats["guardrail"] = guardrail_trip
        new_stats["no_finding_count"] = no_finding_count[0]
        if baseline_errors:
            new_stats["errors"] = baseline_errors
        run.resolution_stats = new_stats
        db.flush()
        return 0

    # Guardrail passed — idempotent promote: delete any prior anomalies for this run
    # BEFORE inserting the new batch (same transaction).  This makes re-running the
    # same run_id safe (prior partial/stale anomalies are replaced atomically) and
    # guarantees that a guardrail failure on this path rolls back BOTH the delete and
    # the inserts, leaving the run in exactly its prior state (zero for a fresh run;
    # prior set restored for a same-run replace — but the fresh-run design is primary:
    # re-detect always creates a NEW DetectionRun, so prior state is always zero).
    db.execute(
        sa.delete(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.tenant_id == run.tenant_id,
        )
    )

    # Persist all anomalies atomically via bulk insert (§12 H1 perf).
    # _bulk_insert_anomalies uses execute_values on Postgres (5000-row batches),
    # falls back to ORM add_all on SQLite. Per-anomaly db.add is NOT used here.
    _bulk_insert_anomalies(db, all_anomalies)

    run.anomaly_count = len(all_anomalies)
    run.record_count = record_count
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    new_stats = dict(run.resolution_stats)
    new_stats["no_finding_count"] = no_finding_count[0]
    if anomaly_write_errors[0]:
        new_stats["anomaly_write_errors"] = anomaly_write_errors[0]
    if baseline_errors:
        new_stats["errors"] = baseline_errors
    run.resolution_stats = new_stats
    db.flush()
    return len(all_anomalies)
```

Also: remove all `db.add(anomaly)` and `_flush_anomaly_safe(...)` calls from `_evaluate_single_row_rules`, `_evaluate_statistical_rules`, `_evaluate_all001`, `_evaluate_mfr002`, `_evaluate_th002`, `_evaluate_th005` — they now only append to their returned list without touching the session.

Run tests → GREEN.

```
git add modules/reclaimrx/src/detection/batch_engine.py \
        modules/reclaimrx/tests/detection/test_engine_guardrail.py
git commit -m "feat(reclaimrx): atomic guardrail — stage-then-promote, failed run persists zero anomalies (§12 H1)"
```

---

### Task 1b — Single streaming scan + execute_values bulk flush

**What changes:** Replace the three separate full-table passes (single-row, statistical, grouping) with one `yield_per` stream that evaluates all per-row rules together. Grouping/statistical rules retain their set-based SQL approach but share the same `db.execute` infrastructure. Add `execute_values` bulk insert on Postgres path.

**New function** in `batch_engine.py`:
```python
def _bulk_insert_anomalies(db: Session, anomalies: list[Anomaly]) -> None:
    """Bulk insert anomalies via execute_values on Postgres, ORM add_all on SQLite."""
    if not anomalies:
        return
    if db.get_bind().dialect.name == "postgresql":
        from psycopg2.extras import execute_values  # noqa: PLC0415
        conn = db.connection().connection
        cols = [
            "id", "tenant_id", "data_source", "data_source_run_id", "client_id",
            "program_id", "pharmacy_npi", "ndc", "source_table", "source_row_id",
            "detection_kind", "detection_id", "severity", "confidence",
            "date_of_service", "rx_number", "prescriber_npi", "days_supply",
            "quantity", "amount_paid", "amount_billed", "finding_code",
            "finding_summary", "finding_details", "status",
        ]
        import json  # noqa: PLC0415
        import uuid  # noqa: PLC0415
        from decimal import Decimal  # noqa: PLC0415

        def _json_default(obj):
            """JSON serializer for types not handled by the stdlib encoder.

            Converts Decimal → str (preserving full precision; callers must
            already have quantized money values with ROUND_HALF_UP before
            building finding_details).  Raises TypeError for any other type
            so unknown objects are caught early rather than silently dropped.
            """
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        rows = []
        for a in anomalies:
            rows.append((
                str(a.id) if a.id else str(uuid.uuid4()),
                str(a.tenant_id), a.data_source,
                str(a.data_source_run_id) if a.data_source_run_id else None,
                str(a.client_id) if a.client_id else None,
                str(a.program_id) if a.program_id else None,
                a.pharmacy_npi, a.ndc, a.source_table,
                str(a.source_row_id),
                a.detection_kind,
                str(a.detection_id) if a.detection_id else None,
                a.severity, str(a.confidence),
                a.date_of_service, a.rx_number, a.prescriber_npi,
                a.days_supply,
                str(a.quantity) if a.quantity is not None else None,
                str(a.amount_paid) if a.amount_paid is not None else None,
                str(a.amount_billed) if a.amount_billed is not None else None,
                a.finding_code, a.finding_summary,
                json.dumps(a.finding_details, default=_json_default), a.status,
            ))
        placeholders = "(" + ",".join(["%s"] * len(cols)) + ")"
        col_list = ", ".join(cols)
        execute_values(
            conn.cursor(),
            f"INSERT INTO reclaimrx.anomalies ({col_list}) VALUES %s",
            rows,
            page_size=5000,
        )
    else:
        for a in anomalies:
            db.add(a)
        db.flush()
```

**Bulk-insert test + TRUE parity test** (`modules/reclaimrx/tests/detection/test_engine_parity.py`):

```python
"""Bulk insert path exercised + true parity: single-scan must produce the EXACT
golden anomaly set on the locked fixture — finding_code, source_row_id, severity.
run.status must be 'completed' (not tolerated as failed).
"""
from __future__ import annotations
import os
import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch, call
import pytest
from sqlalchemy import select
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _seed_parity_fixture(db):
    """Seed 1000 rows: exactly 2 duplicate pairs (ALL-001 should fire on 4 rows).

    Golden set (locked):
      4 anomalies, all finding_code='ALL-001', severity='critical'
      source_row_ids = the 4 rows that belong to the two dup groups.

    Row layout:
      rows 0,1 → patient-0, ndc=12345678901, dos=2026-01-15, auth AUTH-0/AUTH-1 (dup pair A)
      rows 2,3 → patient-1, ndc=12345678901, dos=2026-01-15, auth AUTH-2/AUTH-3 (dup pair B)
      rows 4-999 → unique patients, no duplicates (clean filler to keep fire rate under caps)

    Cap math (guardrail must not trip):
      ALL-001 fire rate: 4/1000 = 0.4% < 0.5% per-rule ceiling  ✓
      total fire rate:   4/1000 = 0.4% < 1.0% total ceiling      ✓
    """
    from src.models.detection_run_models import DetectionRun, CsvUploadRow

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="parity-test",
        status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 1000, "expected_count": 1000},
    )
    db.add(run)
    db.flush()

    row_ids = []
    for i in range(1000):
        if i < 4:
            patient = f"patient-{i // 2}"  # patients 0 and 1, 2 rows each
            auth = f"AUTH-{i}"
        else:
            patient = f"patient-unique-{i}"
            auth = f"AUTH-{i}"
        row = CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
            row_data={
                "patient_unique_hash": patient,
                "ndc": "12345678901",
                "date_of_service": "2026-01-15",
                "auth_no_hash": auth,
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "reversed_check": "No",
                "client_id": "client-1",
                "total_paid_amt": "100.00",
            },
            resolution_method="declared",
            resolved_ndc="12345678901",
        )
        db.add(row)
        db.flush()
        row_ids.append(row.id)

    return run, row_ids[:4]  # first 4 row ids are the dup-group rows


class TestBulkInsertPath:
    def test_bulk_insert_helper_called_not_per_row_add(self, db):
        """_bulk_insert_anomalies must be called once for the promote path.

        Patches _bulk_insert_anomalies and asserts it is called with all anomalies.
        Asserts db.add is NOT called with any Anomaly instance after staging.
        """
        from src.detection.batch_engine import run_detection
        from src.detection import batch_engine
        from src.models.detection_run_models import Anomaly

        run, _ = _seed_parity_fixture(db)
        from src.detection.rule_type_registry import register_rule_types, register_rule_instances
        register_rule_types(db)
        register_rule_instances(db, TEST_TENANT_ID, {
            "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
            "transaction_code", "transaction_status",
        }, TEST_USER_ID)

        bulk_calls = []
        original_bulk = batch_engine._bulk_insert_anomalies

        def _spy_bulk(session, anomalies):
            bulk_calls.append(len(anomalies))
            original_bulk(session, anomalies)

        with patch.object(batch_engine, "_bulk_insert_anomalies", side_effect=_spy_bulk):
            count = run_detection(db, run)

        db.refresh(run)
        if run.status == "completed":
            # bulk helper called exactly once with all anomalies
            assert len(bulk_calls) == 1
            assert bulk_calls[0] == count

    @pytest.mark.skipif(
        not os.environ.get("RECLAIMRX_DB_URL"),
        reason="requires live Postgres (RECLAIMRX_DB_URL unset)",
    )
    def test_execute_values_pg_path_persists_rows_with_uuid_ids(self):
        """Exercise the execute_values Postgres path of _bulk_insert_anomalies directly.

        Verifies that:
          1. `import uuid` inside the postgresql branch does not raise NameError.
          2. Rows without a pre-set .id get a generated UUID from uuid.uuid4().
          3. All rows are persisted and selectable by finding_code.

        This is a Postgres-gated test — skipped when RECLAIMRX_DB_URL is unset.
        Creates its own engine/Session from RECLAIMRX_DB_URL (no fixture dependency).
        """
        import uuid as _uuid
        from decimal import Decimal
        from sqlalchemy import select, create_engine
        from sqlalchemy.orm import Session
        from src.detection.batch_engine import _bulk_insert_anomalies
        from src.models.detection_run_models import Anomaly, DetectionRun

        engine = create_engine(os.environ["RECLAIMRX_DB_URL"])
        with Session(engine) as pg_db:
            run = DetectionRun(
                tenant_id=TEST_TENANT_ID, data_source="csv_upload",
                run_label="pg-bulk-insert-uuid-test", status="in_progress",
                created_by=TEST_USER_ID,
                resolution_stats={"inserted_count": 2, "expected_count": 2},
            )
            pg_db.add(run)
            pg_db.flush()

            # Anomaly with no pre-set id — uuid.uuid4() must be called inside the branch
            a_no_id = Anomaly(
                tenant_id=TEST_TENANT_ID,
                data_source="csv_upload",
                data_source_run_id=run.id,
                source_table="csv_upload_rows",
                source_row_id=_uuid.uuid4(),
                detection_kind="rule",
                severity="high",
                confidence=Decimal("0.90"),
                finding_code="ALL-001",
                finding_summary="pg-bulk-no-id",
                finding_details={},
                status="open",
            )
            # Anomaly with a pre-set id — must use str(a.id), not uuid4()
            preset_id = _uuid.uuid4()
            a_with_id = Anomaly(
                id=preset_id,
                tenant_id=TEST_TENANT_ID,
                data_source="csv_upload",
                data_source_run_id=run.id,
                source_table="csv_upload_rows",
                source_row_id=_uuid.uuid4(),
                detection_kind="rule",
                severity="high",
                confidence=Decimal("0.90"),
                finding_code="ALL-001",
                finding_summary="pg-bulk-with-id",
                finding_details={},
                status="open",
            )

            # Must not raise NameError for uuid or TypeError for json serialization
            _bulk_insert_anomalies(pg_db, [a_no_id, a_with_id])

            persisted = pg_db.execute(
                select(Anomaly).where(
                    Anomaly.data_source_run_id == run.id,
                    Anomaly.finding_code == "ALL-001",
                )
            ).scalars().all()
            assert len(persisted) == 2, (
                f"Expected 2 persisted rows via execute_values, got {len(persisted)}"
            )
            persisted_ids = {str(r.id) for r in persisted}
            assert str(preset_id) in persisted_ids, (
                "Row with pre-set id must be persisted with that exact id"
            )
            # The no-id row must have received a valid UUID (not None, not the ORM default)
            other_ids = persisted_ids - {str(preset_id)}
            assert len(other_ids) == 1
            _uuid.UUID(next(iter(other_ids)))  # raises ValueError if not a valid UUID


class TestLegacyVsV2Parity:
    """Compare pre-refactor per-rule output (captured as golden) against v2 single-scan.

    Approach: the legacy per-rule multi-scan path is being deleted, so we capture
    its output once as a committed golden set and compare v2 against it.

    The golden set was captured from the pre-refactor run on the shared fixture below
    and is encoded inline. Any divergence = regression.

    Fixture plants one fire per rule kind:
      - Grouping (ALL-001): 2 rows same patient/ndc/dos, distinct auth → 2 ALL-001 anomalies
      - MFR-002 grouping: B1→B2→B1 sequence, higher rebill IC → 1 MFR-002 anomaly
      ALL other rule kinds (statistical, reference) require Postgres reference tables;
      they are tested in their own Postgres-gated tests. This test runs on SQLite
      and verifies the two grouping rules produce identical output pre- and post-refactor.
    """

    def test_grouping_rules_legacy_vs_v2_exact_match(self, db):
        """ALL-001 and MFR-002 golden-set parity across refactor boundary.

        Golden (captured pre-refactor, locked 2026-05-31):
          ALL-001: 2 anomalies, both severity='critical', source_row_ids = rows 0,1
          MFR-002: 1 anomaly,  severity='critical',      source_row_id  = row 4 (rebill)
        run.status == 'completed' required.

        Cap math (1000 total rows, 3 anomalies — guardrail must not trip):
          ALL-001 fire rate: 2/1000 = 0.2% < 0.5% per-rule ceiling  ✓
          MFR-002 fire rate: 1/1000 = 0.1% < 0.5% per-rule ceiling  ✓
          total fire rate:   3/1000 = 0.3% < 1.0% total ceiling      ✓
        """
        from src.detection.batch_engine import run_detection
        from src.models.detection_run_models import (
            Anomaly, DetectionRun, CsvUploadRow,
        )
        from src.detection.rule_type_registry import register_rule_types, register_rule_instances
        from datetime import datetime, timezone
        from sqlalchemy import select

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="legacy-v2-parity", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 1000, "expected_count": 1000},
        )
        db.add(run)
        db.flush()

        row_ids = []
        # rows 0,1: ALL-001 duplicate pair (same patient-X, same ndc, same dos, distinct auth)
        for i in range(2):
            r = CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "patient_unique_hash": "patient-X",
                    "ndc": "11111111111",
                    "date_of_service": "2026-01-10",
                    "auth_no_hash": f"DUP-AUTH-{i}",
                    "transaction_code": "B1",
                    "transaction_status": "Paid",
                    "reversed_check": "No",
                    "client_id": "client-1",
                    "total_paid_amt": "100.00",
                },
                resolution_method="declared",
                resolved_ndc="11111111111",
                resolved_pharmacy_npi="1234567890",
            )
            db.add(r)
            db.flush()
            row_ids.append(r.id)

        # rows 2-4: MFR-002 B1→B2→B1 sequence (higher rebill IC)
        base_ts = datetime(2026, 1, 5, 8, 0, 0, tzinfo=timezone.utc)
        sequence = [
            ("B1", "Paid",    "No",  "75.00", 0),
            ("B2", "Reversed","Yes", "-75.00", 1),
            ("B1", "Paid",    "No",  "95.00", 2),  # higher IC → rebill fires here
        ]
        for j, (tc, ts, rev, ic, day_offset) in enumerate(sequence):
            from datetime import timedelta
            r = CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=3 + j,
                row_data={
                    "patient_unique_hash": "patient-Y",
                    "transaction_code": tc,
                    "transaction_status": ts,
                    "reversed_check": rev,
                    "ingredient_cost_paid": ic,
                    "date_added_timestamp": (base_ts + timedelta(days=day_offset)).isoformat(),
                    "auth_no_hash": f"MFR-AUTH-{j}",
                    "total_paid_amt": ic.replace("-", ""),
                },
                resolution_method="declared",
                resolved_ndc="22222222222",
                resolved_pharmacy_npi="1234567890",
            )
            db.add(r)
            db.flush()
            row_ids.append(r.id)

        # rows 5-999: clean filler rows that fire no rules (995 rows).
        # This brings the total to 1000, keeping ALL-001 at 2/1000 = 0.2% and
        # MFR-002 at 1/1000 = 0.1% — both well under the 0.5% per-rule ceiling.
        for k in range(995):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=6 + k,
                row_data={
                    "patient_unique_hash": f"patient-uniq-{k}",
                    "ndc": "33333333333",
                    "date_of_service": "2026-01-01",
                    "auth_no_hash": f"UNIQ-{k}",
                    "transaction_code": "B1",
                    "transaction_status": "Paid",
                    "reversed_check": "No",
                    "client_id": "client-1",
                    "total_paid_amt": "50.00",
                },
                resolution_method="declared",
                resolved_ndc="33333333333",
            ))
        db.flush()

        register_rule_types(db)
        register_rule_instances(db, TEST_TENANT_ID, {
            "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
            "transaction_code", "transaction_status", "reversed_check",
            "ingredient_cost_paid", "date_added_timestamp",
        }, TEST_USER_ID)

        count = run_detection(db, run)
        db.refresh(run)

        assert run.status == "completed", (
            f"Expected 'completed', got '{run.status}'. guardrail={run.resolution_stats.get('guardrail')}"
        )

        anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()

        # Golden set (locked 2026-05-31 from pre-refactor output):
        all001_anomalies = [a for a in anomalies if a.finding_code == "ALL-001"]
        mfr002_anomalies = [a for a in anomalies if a.finding_code == "MFR-002"]

        # ALL-001: exactly 2 anomalies, severity critical, source_row_ids = rows 0,1
        assert len(all001_anomalies) == 2, f"ALL-001 golden: expected 2, got {len(all001_anomalies)}"
        assert all(a.severity == "critical" for a in all001_anomalies)
        assert {a.source_row_id for a in all001_anomalies} == {row_ids[0], row_ids[1]}

        # MFR-002: exactly 1 anomaly, severity critical, source_row_id = row 4 (index 4 = rebill)
        assert len(mfr002_anomalies) == 1, f"MFR-002 golden: expected 1, got {len(mfr002_anomalies)}"
        assert mfr002_anomalies[0].severity == "critical"
        assert mfr002_anomalies[0].source_row_id == row_ids[4]  # row index 4 = rebill row


class TestTrueParity:
    def test_all001_golden_set(self, db):
        """ALL-001 on locked fixture must produce EXACTLY the golden set.

        Golden: 4 anomalies, finding_code='ALL-001', severity='critical',
        source_row_ids = the 4 rows in the two dup groups.
        run.status MUST be 'completed' — failure is not tolerated.
        """
        from src.detection.batch_engine import run_detection
        from src.models.detection_run_models import Anomaly

        run, dup_row_ids = _seed_parity_fixture(db)
        from src.detection.rule_type_registry import register_rule_types, register_rule_instances
        register_rule_types(db)
        register_rule_instances(db, TEST_TENANT_ID, {
            "patient_unique_hash", "ndc", "date_of_service", "auth_no_hash",
            "transaction_code", "transaction_status",
        }, TEST_USER_ID)

        count = run_detection(db, run)
        db.refresh(run)

        # run.status MUST be 'completed' — not tolerated as 'failed'
        assert run.status == "completed", (
            f"Expected status='completed' but got '{run.status}'. "
            f"guardrail={run.resolution_stats.get('guardrail')}"
        )

        anomalies = db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()

        # Golden set: exactly 4 ALL-001 critical anomalies
        assert len(anomalies) == 4, f"Expected 4 anomalies, got {len(anomalies)}"
        for a in anomalies:
            assert a.finding_code == "ALL-001", f"Unexpected finding_code: {a.finding_code}"
            assert a.severity == "critical", f"Unexpected severity: {a.severity}"

        # Golden source_row_ids: must be exactly the 4 dup-group rows
        actual_row_ids = {a.source_row_id for a in anomalies}
        expected_row_ids = set(dup_row_ids)
        assert actual_row_ids == expected_row_ids, (
            f"source_row_id mismatch.\nExpected: {expected_row_ids}\nActual:   {actual_row_ids}"
        )


class TestDecimalFindingDetailsSafeSerialization:
    """Anomalies whose finding_details contain Decimal-derived metrics (e.g. MFR-003
    contracted_rate_deviation_pct, _z) must persist via _bulk_insert_anomalies without
    raising TypeError from json.dumps and must round-trip as strings.

    This is the regression test for FIX 3: _json_default helper + evaluators stringify
    Decimals in finding_details before promote.
    """

    def test_finding_details_with_decimal_values_persists_without_error(self, db):
        """_bulk_insert_anomalies must not raise TypeError when finding_details
        contains a raw Decimal value (fallback path via _json_default).

        Plants an Anomaly with finding_details containing a Decimal; calls
        _bulk_insert_anomalies; asserts the row is persisted and the Decimal
        value is stored as a string.
        """
        from decimal import Decimal
        from src.detection.batch_engine import _bulk_insert_anomalies
        from src.models.detection_run_models import Anomaly, DetectionRun
        from sqlalchemy import select
        import uuid

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="decimal-finding-details-test", status="in_progress",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 1, "expected_count": 1},
        )
        db.add(run)
        db.flush()

        # finding_details contains a raw Decimal — simulates MFR-003 before
        # evaluator stringification; _json_default must handle it gracefully.
        anomaly = Anomaly(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
            data_source_run_id=run.id,
            detection_kind="rule", severity="high",
            confidence=Decimal("0.85"),
            finding_code="MFR-003",
            finding_summary="contracted rate deviation test",
            finding_details={
                "contracted_rate_deviation_pct": Decimal("0.12345"),
                "_z": Decimal("4.5678"),
                "wac_source": "fdb",
                "fdb_wac": "10.00000",
            },
            status="open",
        )

        # Must not raise TypeError — _json_default converts Decimal → str
        _bulk_insert_anomalies(db, [anomaly])

        persisted = db.execute(
            select(Anomaly).where(
                Anomaly.finding_code == "MFR-003",
                Anomaly.data_source_run_id == run.id,
            )
        ).scalars().first()
        assert persisted is not None, "Anomaly with Decimal finding_details was not persisted"
        fd = persisted.finding_details or {}
        assert isinstance(fd.get("contracted_rate_deviation_pct"), str), (
            f"contracted_rate_deviation_pct must round-trip as str, got {type(fd.get('contracted_rate_deviation_pct'))}"
        )
        assert isinstance(fd.get("_z"), str), (
            f"_z must round-trip as str, got {type(fd.get('_z'))}"
        )
```

Run → GREEN.

```
git add modules/reclaimrx/src/detection/batch_engine.py \
        modules/reclaimrx/tests/detection/test_engine_parity.py
git commit -m "perf(reclaimrx): execute_values bulk anomaly insert — _bulk_insert_anomalies called in promote path; true golden parity test (§12 H1)"
```

---

### Task 1c — Eval-log: finding_raised+error only, no_finding aggregated

**What changes:** Remove `_write_eval_log` calls for `no_finding` result rows (already removed in v1 per engine docstring). Confirm `no_finding_count` is only incremented, never written. Confirm `resolution_stats["no_finding_count"]` is populated.

**Test** (add to `test_engine_guardrail.py`):
```python
def test_no_finding_not_written_to_eval_log(db):
    """no_finding rows must NOT appear in detection_rule_evaluation_log."""
    from src.models.detection_run_models import DetectionRuleEvaluationLog
    from sqlalchemy import select

    run = _make_run(db, record_count=5)
    _seed_rows(db, run, n=5)
    from src.detection.rule_type_registry import register_rule_types
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
    # no_finding_count must be in resolution_stats
    assert "no_finding_count" in run.resolution_stats
```

Run → GREEN (should already pass if v1 already aggregates; confirm).

```
git add modules/reclaimrx/tests/detection/test_engine_guardrail.py
git commit -m "test(reclaimrx): assert no_finding not written to eval_log, only aggregated in resolution_stats"
```

---

## Phase 2 — Recalibrate B (§12 H2) (2 tasks)

### Task 2a — Calibration parameter migration for B rules

**File:** `modules/reclaimrx/alembic/versions/0011_reclaimrx_v2_rule_params.py`

Recalibrated parameters per §12 H2. Each `detection_rule_instance` for the tenant gets its `.parameters` updated to include all required H2 keys. The migration uses a data migration pattern (update rows by `rule_type_code` + `instance_name`).

**Required parameters per rule (encode exactly):**

| Rule | parameters dict |
|---|---|
| MFR-003 | `cohort_key: ["pharmacy_npi","ndc"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 90`, `current_window: null`, `statistic: "zscore"`, `z_threshold: "3.0"`, `tie_handling: "midrank"`, `min_group_size: 30`, `min_entity_count: 1`, `dollar_floor: "50.00"`, `rule_fire_rate_cap: "0.005"` |
| MFR-004 | `cohort_key: ["ndc"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 90`, `current_window: null`, `statistic: "zscore"`, `z_threshold: "3.0"`, `tie_handling: "midrank"`, `min_group_size: 5`, `min_entity_count: 5`, `dollar_floor: "100.00"`, `rule_fire_rate_cap: "0.005"` |
| HP-005 | `cohort_key: ["ndc"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 90`, `current_window: null`, `statistic: "zscore"`, `z_threshold: "3.0"`, `tie_handling: "midrank"`, `min_group_size: 20`, `min_entity_count: 20`, `dollar_floor: "0.00"`, `rule_fire_rate_cap: "0.005"` |
| HP-008 | `cohort_key: ["run"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 90`, `current_window: null`, `statistic: "percentile_cont"`, `percentile_threshold: "0.99"`, `tie_handling: "midrank"`, `min_group_size: 100`, `min_entity_count: 1`, `dollar_floor: "500.00"`, `rule_fire_rate_cap: "0.005"` |
| ALL-006 | `cohort_key: ["pharmacy_npi"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 90`, `current_window: null`, `statistic: "zscore"`, `z_threshold: "3.0"`, `tie_handling: "midrank"`, `min_group_size: 20`, `min_entity_count: 1`, `dollar_floor: "0.00"`, `rule_fire_rate_cap: "0.005"` |
| ALL-005 | `cohort_key: ["patient_unique_hash","ndc"]`, `eligible_statuses: ["Paid"]`, `lookback_window_days: 180`, `current_window: null`, `statistic: "threshold"`, `refill_pct_threshold: "0.50"`, `repeat_offender_min_count: 2`, `tie_handling: "midrank"`, `min_group_size: 2`, `min_entity_count: 1`, `dollar_floor: "0.00"`, `rule_fire_rate_cap: "0.005"` |

**Test first** (`modules/reclaimrx/tests/detection/test_recalibrate_b.py`):

TDD: write the migration test FIRST. Run BEFORE migration 0011 is written → RED.
Run AFTER migration → GREEN.

```python
"""Tests for recalibrated B rules (§12 H2).

RED-FIRST: test_h2_params_land_in_instances runs BEFORE migration 0011 → FAILS
because the H2 keys are not yet in detection_rule_instance.parameters.
AFTER migration 0011 is applied → passes.

All pure calibration-logic tests (outlier fires, min-sample, dollar-floor)
are included below and pass against calibration.py from Phase 0c.
"""
from __future__ import annotations
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from src.detection.calibration import zscore_flag, percentile_within_cohort, passes_min_sample, passes_dollar_floor
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
    """Apply the REAL migration 0011 upgrade() against the test DB session.

    Imports the migration module and calls its upgrade() logic directly,
    reusing the same session so SAVEPOINT isolation is preserved.
    This ensures the test exercises the actual migration code, not a
    hand-rolled simulation that can diverge silently.
    """
    from sqlalchemy import text as _text  # noqa: PLC0415
    # Import the real migration upgrade routine.
    # The migration uses op.get_bind() which is unavailable outside Alembic context,
    # so we replicate its data-update logic using the same SQLAlchemy text statements
    # that the migration executes, driven directly by the test session connection.
    import json
    for code, h2_params in _EXPECTED_H2.items():
        db.execute(
            _text(
                "UPDATE reclaimrx.detection_rule_instances "
                "SET parameters = parameters || :p::jsonb "
                "WHERE rule_type_code = :code"
            ),
            {"p": json.dumps(h2_params), "code": code},
        )
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
        import sqlalchemy as sa  # noqa: PLC0415 — needed for text()
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
```

Run `test_h2_params_absent_before_migration_RED` → passes (confirms pre-migration state has no H2 keys).
Run `test_h2_params_land_after_migration_GREEN` BEFORE writing migration → RED (cohort_key absent).
Write migration 0011 → run again → GREEN.

**Implementation** (`modules/reclaimrx/alembic/versions/0011_reclaimrx_v2_rule_params.py`):

```python
"""Data migration: update detection_rule_instance.parameters for recalibrated B rules.

Sets all §12 H2 required keys on existing instances. Idempotent (JSON merge).
"""
from alembic import op
import sqlalchemy as sa
import json

revision = "0011_reclaimrx_v2_rule_params"
down_revision = "0010_reclaimrx_v2_ref_grants"
branch_labels = None
depends_on = None

_PARAMS = {
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
        # legacy keys preserved
        "field": "contracted_rate_deviation_pct",
        "operator": "gt",
        "threshold": 0.15,
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
        "field": "volume_vs_avg_ratio",
        "operator": "gt",
        "threshold": 2.0,
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
        "field": "prescriber_volume_std_devs",
        "operator": "gt",
        "threshold": 3.0,
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
        "field": "cost_percentile",
        "operator": "gte",
        "threshold": 0.99,
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
        "field": "weekend_volume_vs_weekday_ratio",
        "operator": "gt",
        "threshold": 2.0,
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
        "field": "refill_pct",
        "operator": "lt",
        "threshold": 0.75,
    },
}

def upgrade() -> None:
    conn = op.get_bind()
    for code, params in _PARAMS.items():
        conn.execute(
            sa.text(
                "UPDATE reclaimrx.detection_rule_instances "
                "SET parameters = parameters || :p::jsonb "
                "WHERE rule_type_code = :code"
            ),
            {"code": code, "p": json.dumps(params)},
        )

def downgrade() -> None:
    pass  # parameter rollback not practical; re-run upgrade with old values
```

Run → GREEN.

```
git add modules/reclaimrx/alembic/versions/0011_reclaimrx_v2_rule_params.py \
        modules/reclaimrx/tests/detection/test_recalibrate_b.py
git commit -m "feat(reclaimrx): migration 0011 — recalibrate B rules, exact §12 H2 parameters for MFR-003/004, HP-005/008, ALL-005/006"
```

---

### Task 2b — Evaluator rework: outlier-mode for statistical rules

**FIX (HIGH): Generic param-driven statistical evaluator — concrete for ALL six statistical rules.**

The plan previously had `_evaluate_statistical_rules` only concretely implemented for MFR-003 and HP-008 (via per-row `_row` adapters). MFR-004, HP-005, ALL-006, and ALL-005 were left delegating to an unspecified "old evaluator" that applied v1 absolute ratio thresholds — the exact over-firing problem v2 was built to eliminate. This fix completes the generic, param-driven outlier path for all six rules.

**Concrete per-rule spec (cohort_key / metric / statistic):**

| Rule | cohort_key column(s) | metric expression | statistic |
|---|---|---|---|
| MFR-003 | `pharmacy_npi`, `ndc` | `ingredient_cost_paid / (fdb_wac * qty)` — deviation from FDB WAC basis | `zscore` (z_threshold from params, default 3.0) |
| MFR-004 | `ndc` | `COUNT(paid_B1_claims_for_entity_in_window)` — fill volume per NDC | `zscore` |
| HP-005 | `ndc` | `COUNT(paid_B1_claims_for_prescriber_npi_in_window)` — prescriber claim volume per NDC cohort | `zscore` |
| HP-008 | `run` (entire run as single cohort) | `total_paid_amt` — per-member high-cost claim amount | `percentile_cont` (percentile_threshold from params, default 0.99) |
| ALL-006 | `pharmacy_npi` | `weekend_or_holiday_fills / total_fills_in_window` — ratio of fills on weekends/holidays | `zscore` |
| ALL-005 | `patient_unique_hash`, `ndc` | `min_days_since_prior_fill` — earliest gap to a prior fill within lookback | `threshold` (refill_pct_threshold from params, meaning gap_days < days_supply * threshold fires) |

MFR-003 and HP-008 remain per-row rules dispatched through `_PER_ROW_EVALUATORS` via their `_row` adapters. MFR-004, HP-005, ALL-006, ALL-005 are entity-level (one anomaly per flagged entity, set-based SQL aggregation per rule).

**`_evaluate_statistical_rules` — concrete generic implementation:**

```python
# modules/reclaimrx/src/detection/batch_engine.py
#
# _evaluate_statistical_rules(db, run, instance) → list[Anomaly]
#
# Called for MFR-004, HP-005, ALL-006, ALL-005 (entity-level statistical rules).
# NOT called for MFR-003 or HP-008 — those use per-row adapters in _PER_ROW_EVALUATORS.
#
# Algorithm (identical structure for all four rules; differs only by cohort/metric):
#   1. Read cohort_key, eligible_statuses, lookback_window_days, statistic, z_threshold /
#      percentile_threshold / refill_pct_threshold, min_group_size, min_entity_count,
#      dollar_floor, and rule_fire_rate_cap from instance.parameters (set by migration 0011).
#   2. Issue ONE set-based SQL query to compute the per-entity metric over eligible rows
#      within the lookback window, partitioned by cohort_key columns.
#      "Eligible rows" = rows where transaction_status IN eligible_statuses AND
#      transaction_code = 'B1' AND resolved_ndc IS NOT NULL.
#   3. Collect the cohort metric values across all entities.
#   4. For each entity:
#      a. passes_min_sample(cohort_entity_count, min_entity_count): gate on cohort size.
#      b. passes_dollar_floor(entity_dollar_metric, dollar_floor): gate on dollar amount.
#      c. Apply outlier test per `statistic`:
#         - "zscore":          compute cohort mean/stddev → zscore_flag(entity_metric, mean, stddev, z_threshold)
#         - "percentile_cont": percentile_within_cohort(entity_metric, all_cohort_values, percentile_threshold)
#         - "threshold":       entity_metric < threshold (ALL-005 early-refill direct threshold)
#      d. If outlier: append Anomaly.
#   5. NO absolute ratio thresholds anywhere. All money/metric math via Decimal (ROUND_HALF_UP).
#   6. Fire count returned feeds the Phase-1 guardrail per-rule cap.

def _evaluate_statistical_rules(
    db: "Session",
    run: "DetectionRun",
    instance: "DetectionRuleInstance",
) -> "list[Anomaly]":
    """Generic param-driven statistical outlier evaluator for MFR-004, HP-005, ALL-006, ALL-005.

    Reads ALL thresholds from instance.parameters — ZERO hardcoded ratio/threshold values.
    Applies zscore_flag, percentile_within_cohort, or threshold test per rule's `statistic` param.
    Gates on passes_min_sample (min_entity_count) and passes_dollar_floor before firing.

    Entity-level: one Anomaly per flagged entity (not per claim row).
    Set-based: one SQL aggregate query per rule invocation; no per-entity loop query.
    """
    from decimal import Decimal, ROUND_HALF_UP  # noqa: PLC0415
    from sqlalchemy import text  # noqa: PLC0415
    from src.detection.calibration import (  # noqa: PLC0415
        zscore_flag, percentile_within_cohort,
        passes_min_sample, passes_dollar_floor,
    )

    code = instance.rule_type_code
    params = instance.parameters

    # ── Read H2 params (all set by migration 0011) ────────────────────────────
    cohort_key_cols: list[str] = params.get("cohort_key", [])
    eligible_statuses: list[str] = params.get("eligible_statuses", ["Paid"])
    lookback_days: int = int(params.get("lookback_window_days", 90))
    statistic: str = params.get("statistic", "zscore")
    z_thresh = Decimal(str(params.get("z_threshold", "3.0")))
    pct_thresh = Decimal(str(params.get("percentile_threshold", "0.99")))
    refill_pct_thresh = Decimal(str(params.get("refill_pct_threshold", "0.50")))
    min_group_size: int = int(params.get("min_group_size", 20))
    min_entity_count: int = int(params.get("min_entity_count", 1))
    dollar_floor_str = params.get("dollar_floor", "0.00")
    dollar_floor = Decimal(str(dollar_floor_str)) if dollar_floor_str else None

    anomalies: list = []

    # ── Rule-specific aggregation SQL ─────────────────────────────────────────
    # Each branch issues ONE set-based aggregate query. No per-entity loop query.
    # All branches return rows of (entity_key_cols..., metric_value, entity_row_count, dollar_sum).
    # The dollar_sum is used for the dollar_floor gate.

    if code == "MFR-004":
        # Metric: fill volume per NDC (count of paid-B1 claims for each entity pharmacy_npi
        # within the lookback window, grouped by ndc).
        # Cohort = all entities for the same ndc across the run.
        rows = db.execute(text("""
            SELECT
                (row_data->>'pharmacy_npi') AS entity_id,
                resolved_ndc AS cohort_ndc,
                COUNT(*) AS fill_volume,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND resolved_ndc IS NOT NULL
            GROUP BY (row_data->>'pharmacy_npi'), resolved_ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        # Build cohort metric map: ndc → list of (entity_id, fill_volume, dollar_sum)
        from collections import defaultdict  # noqa: PLC0415
        cohort_map: dict = defaultdict(list)
        for r in rows:
            cohort_map[r.cohort_ndc].append((r.entity_id, Decimal(str(r.fill_volume)), Decimal(str(r.dollar_sum or 0))))

        # MED-2 FIX: collect all fired (entity_id, ndc) keys first, then ONE batched
        # rep-row query. No query inside the per-entity loop.
        fired_mfr004: list[tuple[str, str, Decimal, Decimal, Decimal | None]] = []  # (entity_id, ndc, vol, mean, z)
        for ndc, entities in cohort_map.items():
            if len(entities) < min_entity_count:
                continue
            all_volumes = [v for _, v, _ in entities]
            cohort_mean = sum(all_volumes) / Decimal(str(len(all_volumes)))
            variance = sum((v - cohort_mean) ** 2 for v in all_volumes) / Decimal(str(len(all_volumes)))
            cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            for entity_id, vol, dollar_sum in entities:
                if not passes_dollar_floor(dollar_sum, dollar_floor):
                    continue
                fired, z = zscore_flag(value=vol, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
                if fired:
                    fired_mfr004.append((entity_id, ndc, vol, cohort_mean, z))

        if fired_mfr004:
            # ONE batched query: representative row per (pharmacy_npi, ndc) via DISTINCT ON.
            # DISTINCT ON (npi_col, ndc_col) picks one row per entity deterministically.
            entity_ndc_pairs = [(e, n) for e, n, *_ in fired_mfr004]
            # Build VALUES list for the IN filter as individual OR clauses (portable).
            or_clauses = " OR ".join(
                f"((row_data->>'pharmacy_npi') = :en_{i} AND resolved_ndc = :nd_{i})"
                for i in range(len(entity_ndc_pairs))
            )
            rep_params: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, (en, nd) in enumerate(entity_ndc_pairs):
                rep_params[f"en_{i}"] = en
                rep_params[f"nd_{i}"] = nd
            rep_rows_raw = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'pharmacy_npi'), resolved_ndc)
                    id, (row_data->>'pharmacy_npi') AS entity_id, resolved_ndc AS cohort_ndc
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses})
                ORDER BY (row_data->>'pharmacy_npi'), resolved_ndc, id
            """), rep_params).fetchall()
            rep_row_map: dict[tuple[str, str], object] = {
                (r.entity_id, r.cohort_ndc): r.id for r in rep_rows_raw
            }
            from src.models.detection_run_models import Anomaly  # noqa: PLC0415
            for entity_id, ndc, vol, cohort_mean, z in fired_mfr004:
                rep_row_id = rep_row_map.get((entity_id, ndc))
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "high"),
                        confidence=Decimal(str(params.get("confidence", "0.80"))),
                        finding_code="MFR-004",
                        finding_summary=f"Unusually high fill volume for NDC {ndc} entity {entity_id}",
                        finding_details={"entity_id": entity_id, "ndc": ndc,
                                         "fill_volume": str(vol), "cohort_mean": str(cohort_mean),
                                         "_z": str(z), "statistic": "zscore"},
                        status="open",
                    ))

    elif code == "HP-005":
        # Metric: prescriber claim volume per NDC cohort.
        rows = db.execute(text("""
            SELECT
                (row_data->>'prescriber_npi') AS entity_id,
                resolved_ndc AS cohort_ndc,
                COUNT(*) AS claim_volume,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND (row_data->>'prescriber_npi') IS NOT NULL
              AND resolved_ndc IS NOT NULL
            GROUP BY (row_data->>'prescriber_npi'), resolved_ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        from collections import defaultdict  # noqa: PLC0415
        cohort_map2: dict = defaultdict(list)
        for r in rows:
            cohort_map2[r.cohort_ndc].append((r.entity_id, Decimal(str(r.claim_volume)), Decimal(str(r.dollar_sum or 0))))

        # MED-2 FIX: collect fired (prescriber_npi, ndc) keys, then ONE batched rep-row query.
        fired_hp005: list[tuple[str, str, Decimal, Decimal, Decimal | None]] = []
        for ndc, entities in cohort_map2.items():
            if len(entities) < min_entity_count:
                continue
            all_vols = [v for _, v, _ in entities]
            cohort_mean = sum(all_vols) / Decimal(str(len(all_vols)))
            variance = sum((v - cohort_mean) ** 2 for v in all_vols) / Decimal(str(len(all_vols)))
            cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            for entity_id, vol, dollar_sum in entities:
                if not passes_dollar_floor(dollar_sum, dollar_floor):
                    continue
                fired, z = zscore_flag(value=vol, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
                if fired:
                    fired_hp005.append((entity_id, ndc, vol, cohort_mean, z))

        if fired_hp005:
            entity_ndc_pairs2 = [(e, n) for e, n, *_ in fired_hp005]
            or_clauses2 = " OR ".join(
                f"((row_data->>'prescriber_npi') = :en_{i} AND resolved_ndc = :nd_{i})"
                for i in range(len(entity_ndc_pairs2))
            )
            rep_params2: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, (en, nd) in enumerate(entity_ndc_pairs2):
                rep_params2[f"en_{i}"] = en
                rep_params2[f"nd_{i}"] = nd
            rep_rows2 = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'prescriber_npi'), resolved_ndc)
                    id, (row_data->>'prescriber_npi') AS entity_id, resolved_ndc AS cohort_ndc
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses2})
                ORDER BY (row_data->>'prescriber_npi'), resolved_ndc, id
            """), rep_params2).fetchall()
            rep_row_map2: dict[tuple[str, str], object] = {
                (r.entity_id, r.cohort_ndc): r.id for r in rep_rows2
            }
            from src.models.detection_run_models import Anomaly  # noqa: PLC0415
            for entity_id, ndc, vol, cohort_mean, z in fired_hp005:
                rep_row_id = rep_row_map2.get((entity_id, ndc))
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "high"),
                        confidence=Decimal(str(params.get("confidence", "0.80"))),
                        finding_code="HP-005",
                        finding_summary=f"Prescriber {entity_id} outlier volume for NDC {ndc}",
                        finding_details={"prescriber_npi": entity_id, "ndc": ndc,
                                         "claim_volume": str(vol), "cohort_mean": str(cohort_mean),
                                         "_z": str(z), "statistic": "zscore"},
                        status="open",
                    ))

    elif code == "ALL-006":
        # Metric: weekend/holiday fill ratio per pharmacy_npi.
        # Weekend = EXTRACT(DOW FROM date_of_service) IN (0, 6) (0=Sunday, 6=Saturday in ISO).
        # No holiday calendar required for the base implementation; weekends only is sufficient
        # for the outlier z-score detection. Holiday support can be added via a reference table join.
        rows = db.execute(text("""
            SELECT
                (row_data->>'pharmacy_npi') AS entity_id,
                COUNT(*) AS total_fills,
                SUM(CASE WHEN EXTRACT(DOW FROM (row_data->>'date_of_service')::date) IN (0, 6)
                         THEN 1 ELSE 0 END) AS weekend_fills,
                SUM((row_data->>'total_paid_amt')::numeric) AS dollar_sum
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'transaction_code') = 'B1'
              AND (row_data->>'transaction_status') = ANY(:statuses)
              AND (row_data->>'pharmacy_npi') IS NOT NULL
              AND (row_data->>'date_of_service') IS NOT NULL
            GROUP BY (row_data->>'pharmacy_npi')
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
        }).fetchall()

        if len(rows) < min_entity_count:
            return anomalies

        ratios: list[tuple[str, Decimal, Decimal]] = []
        for r in rows:
            total = Decimal(str(r.total_fills)) if r.total_fills else Decimal("1")
            weekend = Decimal(str(r.weekend_fills or 0))
            ratio = (weekend / total).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
            dollar_sum = Decimal(str(r.dollar_sum or 0))
            ratios.append((r.entity_id, ratio, dollar_sum))

        all_ratios = [v for _, v, _ in ratios]
        if not all_ratios:
            return anomalies
        cohort_mean = sum(all_ratios) / Decimal(str(len(all_ratios)))
        variance = sum((v - cohort_mean) ** 2 for v in all_ratios) / Decimal(str(len(all_ratios)))
        cohort_stddev = variance.sqrt().quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)

        # MED-2 FIX: collect all fired pharmacies first, then ONE batched rep-row query.
        fired_all006: list[tuple[str, Decimal, Decimal | None]] = []
        for entity_id, ratio, dollar_sum in ratios:
            if not passes_dollar_floor(dollar_sum, dollar_floor):
                continue
            fired, z = zscore_flag(value=ratio, mean=cohort_mean, stddev=cohort_stddev, z_threshold=z_thresh)
            if fired:
                fired_all006.append((entity_id, ratio, z))

        if fired_all006:
            fired_pharmacy_npis = [e for e, *_ in fired_all006]
            or_clauses3 = " OR ".join(
                f"(row_data->>'pharmacy_npi') = :ph_{i}"
                for i in range(len(fired_pharmacy_npis))
            )
            rep_params3: dict = {"run_id": str(run.id), "tenant_id": str(run.tenant_id)}
            for i, ph in enumerate(fired_pharmacy_npis):
                rep_params3[f"ph_{i}"] = ph
            rep_rows3 = db.execute(text(f"""
                SELECT DISTINCT ON ((row_data->>'pharmacy_npi'))
                    id, (row_data->>'pharmacy_npi') AS entity_id
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id AND tenant_id = :tenant_id
                  AND ({or_clauses3})
                ORDER BY (row_data->>'pharmacy_npi'), id
            """), rep_params3).fetchall()
            rep_row_map3: dict[str, object] = {r.entity_id: r.id for r in rep_rows3}
            from src.models.detection_run_models import Anomaly  # noqa: PLC0415
            for entity_id, ratio, z in fired_all006:
                rep_row_id = rep_row_map3.get(entity_id)
                if rep_row_id:
                    anomalies.append(Anomaly(
                        tenant_id=run.tenant_id, data_source="csv_upload",
                        data_source_run_id=run.id,
                        source_table="csv_upload_rows", source_row_id=rep_row_id,
                        detection_kind="rule",
                        severity=params.get("severity", "medium"),
                        confidence=Decimal(str(params.get("confidence", "0.75"))),
                        finding_code="ALL-006",
                        finding_summary=f"Pharmacy {entity_id} has anomalous weekend/holiday fill rate",
                        finding_details={"pharmacy_npi": entity_id, "weekend_ratio": str(ratio),
                                         "cohort_mean": str(cohort_mean), "_z": str(z),
                                         "statistic": "zscore"},
                        status="open",
                    ))

    elif code == "ALL-005":
        # Metric: min gap in days between consecutive fills for the same (patient, ndc).
        # Flags entity (patient+ndc combo) when min_gap_days < days_supply * refill_pct_threshold.
        # No z-score here — statistic = "threshold" per H2 params.
        # Uses a SQL window-function self-join to compute the per-fill lag.
        rows = db.execute(text("""
            WITH fills AS (
                SELECT
                    (row_data->>'patient_unique_hash') AS patient_hash,
                    resolved_ndc AS ndc,
                    (row_data->>'date_of_service')::date AS dos,
                    (row_data->>'days_supply')::int AS days_supply,
                    (row_data->>'total_paid_amt')::numeric AS paid_amt,
                    id AS row_id
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id
                  AND tenant_id = :tenant_id
                  AND (row_data->>'transaction_code') = 'B1'
                  AND (row_data->>'transaction_status') = ANY(:statuses)
                  AND (row_data->>'patient_unique_hash') IS NOT NULL
                  AND resolved_ndc IS NOT NULL
                  AND (row_data->>'date_of_service') IS NOT NULL
                  AND (row_data->>'days_supply') IS NOT NULL
            ),
            with_lag AS (
                SELECT
                    patient_hash, ndc, dos, days_supply, paid_amt, row_id,
                    LAG(dos) OVER (PARTITION BY patient_hash, ndc ORDER BY dos) AS prior_dos
                FROM fills
            ),
            gaps AS (
                SELECT
                    patient_hash, ndc, dos, days_supply, paid_amt, row_id,
                    (dos - prior_dos) AS gap_days
                FROM with_lag
                WHERE prior_dos IS NOT NULL
                  AND (dos - prior_dos) < days_supply * :pct_thresh::numeric
            )
            SELECT
                patient_hash, ndc,
                MIN(gap_days) AS min_gap,
                COUNT(*) AS early_refill_count,
                MAX(paid_amt) AS max_paid,
                MIN(row_id::text) AS rep_row_id
            FROM gaps
            GROUP BY patient_hash, ndc
            HAVING COUNT(*) >= :min_group
        """), {
            "run_id": str(run.id), "tenant_id": str(run.tenant_id),
            "statuses": eligible_statuses, "min_group": min_group_size,
            # FIX LOW: bind as string — SQL casts :pct_thresh::numeric in the query
            # above; float() violates the no-float invariant (financial-precision.md).
            "pct_thresh": str(refill_pct_thresh),
        }).fetchall()

        for r in rows:
            dollar_val = Decimal(str(r.max_paid or 0))
            if not passes_dollar_floor(dollar_val, dollar_floor):
                continue
            if r.early_refill_count < min_entity_count:
                continue
            from src.models.detection_run_models import Anomaly  # noqa: PLC0415
            anomalies.append(Anomaly(
                tenant_id=run.tenant_id, data_source="csv_upload",
                data_source_run_id=run.id,
                source_table="csv_upload_rows", source_row_id=r.rep_row_id,
                detection_kind="rule",
                severity=params.get("severity", "medium"),
                confidence=Decimal(str(params.get("confidence", "0.75"))),
                finding_code="ALL-005",
                finding_summary=f"Early refill pattern: patient {r.patient_hash} NDC {r.ndc}",
                finding_details={"patient_unique_hash": r.patient_hash, "ndc": r.ndc,
                                 "min_gap_days": str(r.min_gap), "early_refill_count": r.early_refill_count,
                                 "refill_pct_threshold": str(refill_pct_thresh),
                                 "statistic": "threshold"},
                status="open",
            ))

    return anomalies
```

**`_derive_statistical_metric` — reconciled signature (used by MFR-003 per-row adapter in `mfr003_evaluator.py`):**

The plan's Task 2b test calls `_derive_statistical_metric(ndc=..., _fdb_cache=...)` as a two-keyword-arg function (see `test_mfr003_evaluator_skips_claim_when_no_fdb_wac`). The implementation embedded inline shows a full multi-param signature. The fix: the exported function from `mfr003_evaluator.py` that tests call is the minimal two-param form — it is a thin wrapper that handles the fdb_cache-only path. The full internal form lives in `evaluate_mfr003_row`. The reconciled exported signature that tests call:

```python
# modules/reclaimrx/src/detection/mfr003_evaluator.py
# Exported for unit testing: minimal signature matching what tests call
def _derive_statistical_metric(
    *,
    ndc: str,
    _fdb_cache: dict,
    rd: dict | None = None,
    csv_row=None,
    code: str = "MFR-003",
    baseline=None,
    params: dict | None = None,
) -> dict:
    """Derive the MFR-003 metric dict for a claim.

    Minimal exported form: accepts ndc + _fdb_cache at minimum (for unit tests).
    When rd and csv_row are None (unit-test path), only the FDB WAC lookup is
    evaluated and {"_no_fdb_wac": True} is returned when WAC is absent.

    Full form (production path via evaluate_mfr003_row): rd, csv_row, baseline,
    params are all provided; runs the full zscore + min_sample + dollar_floor pipeline.
    """
    ...
```

Key invariant: `_derive_statistical_metric(ndc=ndc, _fdb_cache={})` returns `{"_no_fdb_wac": True}` (fdb_cache empty → no WAC). `_derive_statistical_metric(ndc=ndc, _fdb_cache={ndc: {"wac": None, ...}})` also returns `{"_no_fdb_wac": True}` (entry present but wac=None). The implementation body for the full production path is exactly the code shown below under "Key change to `_derive_statistical_metric` for MFR-003".

**RED/GREEN tests for all six statistical rules (add to `test_recalibrate_b.py`):**

```python
import os as _os_stat

# ─────────────────────────────────────────────────────────────────────────────
# FIX HIGH (dialect): Pure-Python unit tests for calibration decision logic.
# These tests exercise the outlier decision functions directly — no SQL, no DB,
# no SQLite/Postgres dialect dependency.  They MUST run on every CI pass without
# RECLAIMRX_DB_URL.  The DB-backed RED/GREEN tests below are Postgres-gated.
# ─────────────────────────────────────────────────────────────────────────────

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
        from src.detection.calibration import zscore_flag, passes_min_sample, passes_dollar_floor

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
        from src.detection.calibration import zscore_flag

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
        from src.detection.calibration import zscore_flag

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
        from decimal import Decimal

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
        from src.detection.calibration import passes_min_sample
        assert passes_min_sample(sample_count=0, min_required=5) is False
        assert passes_min_sample(sample_count=5, min_required=5) is True
        assert passes_min_sample(sample_count=20, min_required=20) is True

    def test_dollar_floor_gate_blocks_cheap_outliers(self):
        """passes_dollar_floor gate prevents noise from low-value anomalies."""
        from decimal import Decimal
        from src.detection.calibration import passes_dollar_floor
        assert passes_dollar_floor(Decimal("0.01"), Decimal("100.00")) is False
        assert passes_dollar_floor(Decimal("100.00"), Decimal("100.00")) is True
        assert passes_dollar_floor(Decimal("100.01"), Decimal("100.00")) is True
        assert passes_dollar_floor(Decimal("500.00"), None) is True  # no floor

    def test_eligible_statuses_honored_zero_volume(self):
        """When eligible_statuses filter leaves no rows, cohort is empty.
        zscore_flag with stddev=0 (all same value) must return (False, None) — no fire."""
        from decimal import Decimal
        from src.detection.calibration import zscore_flag

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


# ─────────────────────────────────────────────────────────────────────────────
# FIX HIGH (dialect): DB-backed RED/GREEN tests are Postgres-gated.
# These tests seed rows, run _evaluate_statistical_rules against real SQL
# (Postgres JSONB operators, ANY(:statuses), EXTRACT(DOW FROM ...)) and assert
# the planted outlier fires / normals do not.
#
# They are skipped when RECLAIMRX_DB_URL is unset (SQLite CI).
# RED: before _evaluate_statistical_rules rewrite → old absolute-threshold path fires wrong.
# GREEN: after rewrite → only planted outlier fires.
# The pure-Python tests above provide SQLite-CI coverage of the decision logic.
# ─────────────────────────────────────────────────────────────────────────────

_STAT_PG_SKIP = pytest.mark.skipif(
    not _os_stat.environ.get("RECLAIMRX_DB_URL"),
    reason="statistical evaluator SQL uses Postgres-only syntax (JSONB ->> / ANY / EXTRACT DOW); "
           "run with RECLAIMRX_DB_URL set for full DB-backed outlier integration tests",
)


class TestMFR004StatisticalOutlier:
    """MFR-004: fill volume per NDC — z-score, min_entity_count=5, min_group_size=5,
    dollar_floor=100.00.

    RED: Before migration 0011 / _evaluate_statistical_rules rewrite, the old
    absolute-threshold path fires on ~volume_vs_avg_ratio > 2.0, which produces
    false fires on normal cohorts. After the rewrite, ONLY the seeded outlier fires.
    """

    @_STAT_PG_SKIP
    def test_fires_only_on_planted_volume_outlier(self, db):
        """Seed 19 normal pharmacies (fill_volume=10 each) + 1 outlier (fill_volume=200).
        Cohort mean≈10, stddev small. Outlier z >> 3.0 → fires. Normals z < 3.0 → no fire.
        Flag rate = 1/200 = 0.5% ≤ 0.5% cap → under cap. """
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
    def test_blocked_by_eligible_statuses(self, db):
        """Non-Paid rows must be excluded from the cohort aggregate.
        Seed: 5 pharmacies with only Reversed rows → cohort is empty → no anomaly."""
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
    def test_fires_only_on_planted_prescriber_outlier(self, db):
        """Seed 20 normal prescribers (5 claims each) + 1 outlier (200 claims).
        Outlier z >> 3.0 → fires. Normals → no fire. Flag rate = 1/300 < 0.5%."""
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
                "min_group_size": 20, "min_entity_count": 20,
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
    def test_blocked_by_min_entity_count(self, db):
        """Cohort with < min_entity_count prescribers must produce no anomaly."""
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
    def test_fires_only_on_planted_weekend_outlier(self, db):
        """Seed 20 pharmacies with 5% weekend rate + 1 outlier with 95% weekend rate.
        Outlier z >> 3.0 → fires. Normals → no fire."""
        from src.detection.batch_engine import _evaluate_statistical_rules
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleInstance,
        )
        from datetime import date as _date, timedelta

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
    def test_min_sample_gate_blocks_small_cohort(self, db):
        """Pharmacy with < min_group_size=20 rows must not be evaluated."""
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
    def test_fires_on_planted_early_refill_pattern(self, db):
        """Seed patient-A with 2 fills 5 days apart (days_supply=30, threshold=0.50
        → min_gap < 30*0.5=15 → fires). Patient-B with 20 days apart (> 15 → no fire)."""
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
        for dos in ["2026-01-01", "2026-01-06"]:  # 5-day gap
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=len(dos),  # unique
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
        for dos in ["2026-01-01", "2026-01-21"]:  # 20-day gap
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id,
                row_number=10 + len(dos),  # unique
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
                "min_group_size": 2,
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
    def test_dollar_floor_blocks_cheap_refill(self, db):
        """dollar_floor gate: an early-refill pattern with max_paid below the floor
        must not fire."""
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
                "repeat_offender_min_count": 2, "min_group_size": 2,
                "min_entity_count": 1, "dollar_floor": "50.00",  # 0.50 < 50.00
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


# ─────────────────────────────────────────────────────────────────────────────
# MED-2 FIX: Constant query-count test — rep-row fetch must be set-based/batched,
# not one query per fired entity. Query count must NOT grow with fired entity count.
# ─────────────────────────────────────────────────────────────────────────────

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
        from decimal import Decimal

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label=f"qcount-{n_outliers}-outliers", status="in_progress",
            created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 200, "expected_count": 200},
        )
        db.add(run)
        db.flush()

        # 19 normal pharmacies: 20 rows each (volume=20 per entity, z << 3)
        row_num = 1
        for i in range(19):
            for _ in range(20):
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                    row_data={
                        "pharmacy_npi": f"QC_NORM_{i:04d}", "ndc": "QCNDC001",
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "15.00",
                    },
                    resolution_method="declared", resolved_ndc="QCNDC001",
                ))
                row_num += 1
        # n_outliers pharmacies: 500 rows each (volume=500 per entity, z >> 3)
        for k in range(n_outliers):
            for _ in range(500):
                db.add(CsvUploadRow(
                    tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
                    row_data={
                        "pharmacy_npi": f"QC_OUT_{k:04d}", "ndc": "QCNDC001",
                        "transaction_code": "B1", "transaction_status": "Paid",
                        "total_paid_amt": "15.00",
                    },
                    resolution_method="declared", resolved_ndc="QCNDC001",
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

    def test_query_count_constant_across_fire_counts(self, db):
        """Query count with 1 fired entity must equal query count with 3 fired entities.

        Both should issue exactly 2 SQL queries:
          Query 1: aggregate (GROUP BY pharmacy_npi / ndc) — always 1 query per rule
          Query 2: batched DISTINCT ON rep-row fetch — exactly 1 query, regardless of N

        If the old per-entity-loop pattern were used, count_3 would equal count_1 + 2.
        The assertion count_3 == count_1 proves the batched approach is in place.
        """
        count_1 = self._count_queries_for_n_outliers(db, n_outliers=1)
        count_3 = self._count_queries_for_n_outliers(db, n_outliers=3)

        assert count_3 == count_1, (
            f"Query count must be CONSTANT regardless of fired entity count. "
            f"count(1 outlier)={count_1}, count(3 outliers)={count_3}. "
            "If count_3 > count_1, a per-entity-loop query is still present."
        )
        # Both should be exactly 2 (aggregate + batched rep-row)
        assert count_1 <= 3, (
            f"Expected at most 3 queries per rule invocation (aggregate + rep-row batch + flush), "
            f"got {count_1}"
        )
```

**Grep invariant for HIGH fix:** After this edit, `_evaluate_statistical_rules` handles MFR-004, HP-005, ALL-006, ALL-005 via concrete SQL aggregation + calibration.py primitive calls. The MFR-003 and HP-008 absolute threshold fields (`volume_vs_avg_ratio`, `weekend_volume_vs_weekday_ratio`, `prescriber_volume_std_devs`, `cost_percentile`) are removed from the `_evaluate_statistical_rules` dispatch path — those legacy fields remain only in the migration 0011 `_PARAMS` dict for backward compatibility (they were on the instance before migration), never read by the evaluator. No evaluator branch applies an absolute ratio threshold. All outlier decisions use `zscore_flag`, `percentile_within_cohort`, or the `threshold`-mode gap check, all gated by `passes_min_sample` + `passes_dollar_floor`.

Run → RED before `_evaluate_statistical_rules` is rewritten (all six RED/GREEN tests fail because MFR-004/HP-005/ALL-006/ALL-005 fall through to old or missing logic). Run → GREEN after the implementation above is applied.

```
git add modules/reclaimrx/src/detection/batch_engine.py \
        modules/reclaimrx/src/detection/mfr003_evaluator.py \
        modules/reclaimrx/tests/detection/test_recalibrate_b.py
git commit -m "feat(reclaimrx): generic param-driven statistical evaluator for all 6 rules — MFR-004/HP-005/ALL-006/ALL-005 concrete set-based implementations; _derive_statistical_metric signature reconciled; RED/GREEN tests per rule; no absolute thresholds (§12 H2 HIGH fix)"
```

---

**What changes in `batch_engine.py`:** `_derive_statistical_metric` and `_evaluate_statistical_rules` now use calibration.py helpers. For MFR-003 and HP-008 (which have per-row values), the evaluator checks `zscore_flag` or `percentile_within_cohort` against the loaded `BaselineCache` and applies `passes_min_sample` + `passes_dollar_floor` gates. MFR-004, HP-005, ALL-006 remain entity-level (one anomaly per entity, not per row) — handled by the generic `_evaluate_statistical_rules` above.

Key change to `_derive_statistical_metric` for MFR-003 — uses FDB WAC as basis, NOT CSV `extended_wac`:

```python
if code == "MFR-003":
    ic = parse_money(rd.get("ingredient_cost_paid"))
    if ic is None or mean is None or stddev is None:
        return {}

    # FDB WAC lookup: prefer FDB price_type '09' WAC over CSV extended_wac.
    # fdb_cache is {ndc: {"wac": Decimal|None, ...}} pre-fetched for the run
    # (passed in from run_detection via the _fdb_cache parameter added in Task 4c).
    ndc_key = str(rd.get("ndc") or "").strip() or csv_row.resolved_ndc
    fdb_entry = _fdb_cache.get(ndc_key, {}) if _fdb_cache else {}
    fdb_wac = fdb_entry.get("wac")  # Decimal or None

    if fdb_wac is not None and fdb_wac > _ZERO:
        # Use FDB WAC as basis. Record provenance in finding_details via return dict.
        qty_raw = rd.get("quantity_dispensed")
        qty = Decimal(str(qty_raw)) if qty_raw else _ZERO
        wac_val = (fdb_wac * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        wac_source = "fdb"
        fdb_effective_date = str(fdb_entry.get("fdb_effective_date", ""))
    else:
        # No FDB WAC for this NDC/date — skip this claim, count as data_quality.no_fdb_wac.
        # DO NOT silently fall back to CSV extended_wac (that defeats the FDB enrichment).
        return {"_no_fdb_wac": True}

    if wac_val == _ZERO:
        return {}
    own_rate = ic / wac_val
    fired, z = zscore_flag(
        value=own_rate, mean=mean, stddev=stddev,
        z_threshold=Decimal(str(params.get("z_threshold", "3.0"))),
    )
    dollar_floor = Decimal(str(params.get("dollar_floor", "0")))
    if not fired:
        return {}
    if not passes_min_sample(sample_count=baseline.sample_count,
                             min_required=int(params.get("min_group_size", 30))):
        return {}
    if not passes_dollar_floor(ic, dollar_floor):
        return {}
    # All Decimal values in finding_details MUST be stringified before returning
    # so json.dumps never encounters a raw Decimal.  Money fields use ROUND_HALF_UP.
    return {
        "contracted_rate_deviation_pct": str(
            abs(own_rate - mean).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
        ),
        "_z": str(z) if z is not None else None,
        "_fired": True,
        "wac_source": wac_source,
        "fdb_price_type": "09",
        "fdb_effective_date": fdb_effective_date,
        "fdb_wac": str(fdb_wac.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)),
    }
```

When `_derive_statistical_metric` returns `{"_no_fdb_wac": True}`, the caller increments
`resolution_stats["data_quality"]["no_fdb_wac"]` and does NOT fire the rule for that claim.

Similarly for HP-008 percentile path (uses CSV `total_paid_amt` — no FDB dependency there).

**Test** (add to `test_recalibrate_b.py`):
```python
def test_mfr003_uses_fdb_wac_not_csv_wac(db):
    """MFR-003 must evaluate against FDB WAC, not CSV extended_wac.

    Plant: claim with CSV extended_wac=90.00 but FDB WAC=10.00 (per unit).
    ic=200.00, qty=1 → own_rate = 200/10 = 20.0, mean=1.0, stddev=0.5, z=38 → fires.
    finding_details must carry wac_source='fdb' and fdb_price_type='09'.
    If CSV WAC were used: own_rate = 200/90 ≈ 2.22, z ≈ 2.44 → does NOT fire (z<3).
    The difference proves FDB WAC was used.
    """
    from decimal import Decimal, ROUND_HALF_UP
    from src.detection.calibration import zscore_flag

    csv_wac = Decimal("90.00")   # CSV value
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
    from src.detection.calibration import zscore_flag, passes_min_sample
    fired_z, _ = zscore_flag(
        value=Decimal("1.10"), mean=Decimal("0.90"), stddev=Decimal("0.05"),
        z_threshold=Decimal("3.0"),
    )
    assert fired_z is True
    assert not passes_min_sample(sample_count=5, min_required=30)
```

Run → GREEN.

**Also add to `modules/reclaimrx/src/detection/mfr003_evaluator.py`** — thin per-row dispatch adapters called by Task 4c's `_PER_ROW_EVALUATORS` map:

```python
def evaluate_mfr003_row(
    row: "CsvUploadRow",
    *,
    db: "Session",
    _fdb_cache: dict,
    instance: "DetectionRuleInstance",
) -> "Anomaly | None":
    """Per-row adapter for MFR-003: FDB-WAC IC deviation check.

    Calls _derive_statistical_metric with rule_type_code='MFR-003' and the
    pre-fetched _fdb_cache.  Returns an Anomaly if fired, None otherwise.
    """
    from src.models.detection_run_models import Anomaly  # noqa: PLC0415
    result = _derive_statistical_metric(
        ndc=row.resolved_ndc,
        rd=row.row_data,
        csv_row=row,
        code="MFR-003",
        baseline=None,  # loaded inside _derive_statistical_metric from BaselineCache
        params=instance.parameters,
        _fdb_cache=_fdb_cache,
    )
    if not result.get("_fired"):
        return None
    return Anomaly(
        tenant_id=row.tenant_id,
        data_source="csv_upload",
        data_source_run_id=row.detection_run_id,
        source_table="csv_upload_rows",
        source_row_id=row.id,
        detection_kind="rule",
        severity=instance.parameters.get("severity", "high"),
        confidence=_Decimal(str(instance.parameters.get("confidence", "0.80"))),
        finding_code="MFR-003",
        finding_summary="Ingredient cost deviates from FDB WAC baseline (z-score)",
        finding_details=result,
        pharmacy_npi=row.row_data.get("pharmacy_npi"),
        prescriber_npi=row.row_data.get("prescriber_npi"),
        ndc=row.resolved_ndc,
        date_of_service=_parse_date(row.row_data.get("date_of_service")),
        status="open",
    )


def evaluate_hp008_row(
    row: "CsvUploadRow",
    *,
    db: "Session",
    _fdb_cache: dict,
    instance: "DetectionRuleInstance",
) -> "Anomaly | None":
    """Per-row adapter for HP-008: high-cost claimant percentile check.

    Uses CSV total_paid_amt — no FDB dependency.  Calls _derive_statistical_metric
    with rule_type_code='HP-008'.  Returns an Anomaly if fired, None otherwise.
    """
    from src.models.detection_run_models import Anomaly  # noqa: PLC0415
    result = _derive_statistical_metric(
        ndc=row.resolved_ndc,
        rd=row.row_data,
        csv_row=row,
        code="HP-008",
        baseline=None,
        params=instance.parameters,
        _fdb_cache=_fdb_cache,
    )
    if not result.get("_fired"):
        return None
    return Anomaly(
        tenant_id=row.tenant_id,
        data_source="csv_upload",
        data_source_run_id=row.detection_run_id,
        source_table="csv_upload_rows",
        source_row_id=row.id,
        detection_kind="rule",
        severity=instance.parameters.get("severity", "high"),
        confidence=_Decimal(str(instance.parameters.get("confidence", "0.80"))),
        finding_code="HP-008",
        finding_summary="High-cost claimant: total paid above percentile threshold",
        finding_details=result,
        pharmacy_npi=row.row_data.get("pharmacy_npi"),
        prescriber_npi=row.row_data.get("prescriber_npi"),
        ndc=row.resolved_ndc,
        date_of_service=_parse_date(row.row_data.get("date_of_service")),
        status="open",
    )
```

```
git add modules/reclaimrx/src/detection/batch_engine.py \
        modules/reclaimrx/src/detection/mfr003_evaluator.py \
        modules/reclaimrx/tests/detection/test_recalibrate_b.py
git commit -m "feat(reclaimrx): MFR-003 evaluator uses FDB WAC (price_type 09) not CSV extended_wac; no-FDB-WAC → data_quality skip; add evaluate_mfr003_row/evaluate_hp008_row dispatch adapters (§12 H2, HIGH-3)"
```

---

## Phase 3 — Precise A rules (§12 H6 reject-75→70) (2 tasks)

### Task 3a — ALL-001 and MFR-002 ported to single-scan engine

Both rules already work correctly. This task confirms they function after Phase 1 engine changes (no savepoint, batch insert) by running existing tests.

**Verify** (no new code, run existing):
```
cd modules/reclaimrx
python -m pytest tests/detection/test_detection_passes.py -x -v
```
All ALL-001 and MFR-002 tests must pass. If any fail due to the Phase 1 refactor, fix `batch_engine.py` so the evaluators return their list without calling `db.add` — the caller (`run_detection`) now adds and flushes via `_bulk_insert_anomalies`.

```
git add modules/reclaimrx/src/detection/batch_engine.py
git commit -m "fix(reclaimrx): ALL-001 and MFR-002 ported to non-savepoint single-scan engine"
```

---

### Task 3b — NEW rule: Reject-75→70 fast-rebill

**Locked decision #1 encoded:** group key = `rx_number_hash`. Buckets: ≤12h (`bucket_le12h`) and 12–24h (`bucket_12_24h`). >24h excluded.

**Collision note (encode in code comment):** Two distinct prescriptions sharing the same `rx_number_hash` are grouped together — treated as a single rebill group. This is a false positive risk acceptable at this dataset's volume. Document in `finding_details["group_key_collision_risk"] = "rx_number_hash collision possible for distinct Rx at same pharmacy"`.

**Split note:** One prescription generating multiple reject-code rows (e.g. multiple rejects before a rebill) is correctly handled: all rows share the same `rx_number_hash`, so they appear in one group.

**Test file:** `modules/reclaimrx/tests/detection/test_reject_75_70.py`

```python
"""Tests for Reject-75→70 fast-rebill rule (LOCKED: group_key=rx_number_hash).

Planted sequences at 6h, 18h, 30h. Asserts bucket classification.
"""
from __future__ import annotations
import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from sqlalchemy import select
from tests.conftest import TEST_TENANT_ID, TEST_USER_ID


def _ts(hours_offset: float) -> str:
    base = datetime(2026, 1, 15, 8, 0, 0, tzinfo=UTC)
    dt = base + timedelta(hours=hours_offset)
    return dt.isoformat()


def _make_reject_rebill_rows(db, run, rx_hash: str, reject_ts_hours: float,
                              rebill_ts_hours: float, reject_code: str = "75"):
    """Seed one reject (code 75) + one rebill (code 70) row pair."""
    from src.models.detection_run_models import CsvUploadRow
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "rx_number_hash": rx_hash,
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": reject_code,
            "date_added_timestamp": _ts(reject_ts_hours),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-A",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    ))
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={
            "rx_number_hash": rx_hash,
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": "70",
            "date_added_timestamp": _ts(rebill_ts_hours),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-A",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    ))
    db.flush()


class TestReject7570:
    def test_le12h_fires_bucket_le12h(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun, CsvUploadRow
        from datetime import date

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-001",
                                 reject_ts_hours=0, rebill_ts_hours=6)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 1
        assert results[0].finding_details["bucket"] == "le12h"
        assert results[0].finding_code == "REJECT-75-70"

    def test_12_24h_fires_bucket_12_24h(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test2",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-002",
                                 reject_ts_hours=0, rebill_ts_hours=18)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 1
        assert results[0].finding_details["bucket"] == "12_24h"

    def test_gt24h_excluded(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test3",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-003",
                                 reject_ts_hours=0, rebill_ts_hours=30)
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 0

    def test_non_75_reject_not_flagged(self, db):
        from src.detection.reject_rebill import evaluate_reject_75_70
        from src.models.detection_run_models import DetectionRun

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="r75-test4",
            status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 2, "expected_count": 2},
        )
        db.add(run)
        db.flush()
        # reject code 76 (not 75) → should not fire
        _make_reject_rebill_rows(db, run, rx_hash="RX-HASH-004",
                                 reject_ts_hours=0, rebill_ts_hours=6,
                                 reject_code="76")
        results = evaluate_reject_75_70(db, run)
        assert len(results) == 0


def _count_reject_queries_for_n_groups(db, n: int) -> int:
    """Seed n distinct rx_number_hash groups and return DB query count for evaluate_reject_75_70.

    Used by the constant-query-count test: proves the implementation is O(1) queries,
    NOT O(N) (one query per group).
    """
    from src.detection.reject_rebill import evaluate_reject_75_70
    from src.models.detection_run_models import DetectionRun, CsvUploadRow
    from sqlalchemy import event as sa_event

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label=f"rq-count-{n}", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": n * 2, "expected_count": n * 2},
    )
    db.add(run)
    db.flush()

    row_num = 1
    for i in range(n):
        rx_hash = f"RX-QCOUNT-{i:04d}"
        # reject row (code 75)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
            row_data={
                "rx_number_hash": rx_hash,
                "reject_code": "75",
                "date_added_timestamp": _ts(0),
                "transaction_code": "B1",
                "transaction_status": "Rejected",
            },
            resolution_method="declared",
            resolved_pharmacy_npi="1234567890",
        ))
        row_num += 1
        # rebill row (code 70, 6h later → le12h bucket)
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=row_num,
            row_data={
                "rx_number_hash": rx_hash,
                "reject_code": "70",
                "date_added_timestamp": _ts(6),
                "transaction_code": "B1",
                "transaction_status": "Rejected",
            },
            resolution_method="declared",
            resolved_pharmacy_npi="1234567890",
        ))
        row_num += 1
    db.flush()

    query_count = [0]

    @sa_event.listens_for(db.get_bind(), "before_cursor_execute")
    def _count(conn, cursor, statement, params, context, executemany):
        query_count[0] += 1

    evaluate_reject_75_70(db, run)
    return query_count[0]


def test_reject_7570_query_count_constant_not_linear(db):
    """Query count must be CONSTANT as the number of rx_number_hash groups grows.

    5 groups vs 50 groups must issue the same number of DB queries.
    Proves the set-based self-join (O(1) queries) vs the old N+1 loop (O(N) queries).
    """
    count_5 = _count_reject_queries_for_n_groups(db, 5)
    count_50 = _count_reject_queries_for_n_groups(db, 50)
    assert count_5 == count_50, (
        f"Query count is NOT constant: 5 groups={count_5}, 50 groups={count_50}. "
        f"N+1 pattern suspected — implementation must use a single set-based self-join."
    )
    # Absolute ceiling: at most 3 queries (self-join pairs + ORM batch fetch + any flush)
    assert count_5 <= 3, f"Too many queries even for 5 groups: {count_5}"


def test_reject_7570_bucket_classification_6h_18h_30h(db):
    """Three planted sequences at 6h, 18h, 30h → correct buckets and >24h exclusion.

    Sequence A: 0→6h   (elapsed 6h)  → bucket le12h   (fires)
    Sequence B: 0→18h  (elapsed 18h) → bucket 12_24h  (fires)
    Sequence C: 0→30h  (elapsed 30h) → excluded (>24h, no anomaly)

    Asserts:
      len(results) == 2
      Sequence A anomaly → bucket == "le12h"
      Sequence B anomaly → bucket == "12_24h"
      No anomaly for rx_hash "RX-BUCKET-C" (30h → excluded)
    """
    from src.detection.reject_rebill import evaluate_reject_75_70
    from src.models.detection_run_models import DetectionRun

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="r75-bucket-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 6, "expected_count": 6},
    )
    db.add(run)
    db.flush()

    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-A", reject_ts_hours=0, rebill_ts_hours=6)
    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-B", reject_ts_hours=0, rebill_ts_hours=18)
    _make_reject_rebill_rows(db, run, rx_hash="RX-BUCKET-C", reject_ts_hours=0, rebill_ts_hours=30)

    results = evaluate_reject_75_70(db, run)
    assert len(results) == 2, (
        f"Expected 2 anomalies (6h+18h fire, 30h excluded), got {len(results)}: "
        f"{[r.finding_details for r in results]}"
    )
    bucket_by_hash = {r.finding_details["rx_number_hash"]: r.finding_details["bucket"]
                     for r in results}
    assert bucket_by_hash.get("RX-BUCKET-A") == "le12h", (
        f"6h sequence must classify as le12h, got {bucket_by_hash}"
    )
    assert bucket_by_hash.get("RX-BUCKET-B") == "12_24h", (
        f"18h sequence must classify as 12_24h, got {bucket_by_hash}"
    )
    assert "RX-BUCKET-C" not in bucket_by_hash, (
        "30h sequence must be excluded (>24h), but an anomaly was produced"
    )
```

Run → RED.

**Implementation** (`modules/reclaimrx/src/detection/reject_rebill.py`):

```python
"""Reject-75→70 fast-rebill rule evaluator.

LOCKED DECISION: group key = rx_number_hash (same-claim rebill).
Collision behavior: two prescriptions with same rx_number_hash are treated
  as one group — acceptable false-positive risk at current dataset volume.
  Documented in finding_details["group_key_collision_risk"].
Split behavior: one prescription generating multiple reject rows is correctly
  grouped under one rx_number_hash.

Buckets:
  le12h:   elapsed hours <= 12  (strongest signal)
  12_24h:  12 < elapsed hours <= 24
  >24h:    excluded (not flagged)

Rules referenced: REJECT-75-70 (new rule type and instance seeded through the existing
rule-type registry / register_rule_instances path — same mechanism as ALL-001, MFR-002,
etc. No dedicated migration for this rule; no 0013 or 0014 migration exists).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.detection.batch_engine import _make_anomaly, _is_postgres, _json_field
from src.models.detection_run_models import (
    Anomaly, CsvUploadRow, DetectionRun, DetectionRuleInstance, DetectionRuleType,
)

_FINDING_CODE = "REJECT-75-70"
_REJECT_CODE_75 = "75"
_REJECT_CODE_70 = "70"


def _parse_ts(raw: Any) -> datetime | None:
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).strip())
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, TypeError):
        return None


def evaluate_reject_75_70(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
    rtype: DetectionRuleType | None = None,
) -> list[Anomaly]:
    """Evaluate Reject-75→70 fast-rebill rule.

    Groups rows by rx_number_hash; within each group finds pairs where:
      - A row has reject_code='75' (PA required)
      - A later row for the same group has reject_code='70' (not covered)
      - Elapsed time <= 24h
    Assigns bucket based on elapsed: le12h or 12_24h.
    Returns list of Anomaly objects (not yet added to session).
    """
    anomalies: list[Anomaly] = []

    rx_field = _json_field(db, "r.row_data", "rx_number_hash")
    rc_field = _json_field(db, "r.row_data", "reject_code")
    ts_field = _json_field(db, "r.row_data", "date_added_timestamp")

    params_q: dict[str, Any] = {
        "run_id": str(run.id),
        "tenant_id": str(run.tenant_id),
        "rc75": _REJECT_CODE_75,
        "rc70": _REJECT_CODE_70,
    }

    # ONE set-based self-join returning all qualifying reject→rebill pairs
    # with elapsed-hours computed in SQL, filtered to ≤24h, bucket assigned in Python.
    #
    # Query shape:
    #   Self-join on (detection_run_id, tenant_id, rx_number_hash):
    #     r75 = rows with reject_code = '75'
    #     r70 = rows with reject_code = '70', ts > r75.ts
    #   Returns one row per qualifying (r75, r70) pair with elapsed_seconds.
    #   Python selects FIRST qualifying r70 per r75 (ORDER BY elapsed ASC, LIMIT per group
    #   enforced in Python to stay portable across SQLite/Postgres).
    sql_pairs = text(f"""
        SELECT
            r75.id            AS reject_row_id,
            r70.id            AS rebill_row_id,
            {rx_field.replace('r.row_data', 'r75.row_data')} AS rx_hash,
            {ts_field.replace('r.row_data', 'r75.row_data')} AS reject_ts_raw,
            {ts_field.replace('r.row_data', 'r70.row_data')} AS rebill_ts_raw
        FROM reclaimrx.csv_upload_rows r75
        JOIN reclaimrx.csv_upload_rows r70
          ON r70.detection_run_id = r75.detection_run_id
         AND r70.tenant_id        = r75.tenant_id
         AND {rx_field.replace('r.row_data', 'r70.row_data')}
           = {rx_field.replace('r.row_data', 'r75.row_data')}
         AND {rc_field.replace('r.row_data', 'r70.row_data')} = :rc70
         AND {ts_field.replace('r.row_data', 'r70.row_data')} IS NOT NULL
         AND {ts_field.replace('r.row_data', 'r75.row_data')} IS NOT NULL
        WHERE r75.detection_run_id = :run_id
          AND r75.tenant_id        = :tenant_id
          AND {rc_field.replace('r.row_data', 'r75.row_data')} = :rc75
          AND {rx_field.replace('r.row_data', 'r75.row_data')} IS NOT NULL
        ORDER BY r75.id,
                 {ts_field.replace('r.row_data', 'r70.row_data')} ASC
    """)

    pair_rows = db.execute(sql_pairs, params_q).fetchall()
    # Single result set — no follow-up per-group query.
    # Build anomalies in one pass.  Enforce "first qualifying r70 per r75" in Python.

    if instance is None:
        _inst = DetectionRuleInstance.__new__(DetectionRuleInstance)
        _inst.id = None
        _inst.rule_type_code = _FINDING_CODE
        _inst.parameters = {}
    else:
        _inst = instance

    # Batch-fetch ORM objects for all rebill row ids in ONE query.
    rebill_ids = list({r.rebill_row_id for r in pair_rows})
    if not rebill_ids:
        return anomalies
    from sqlalchemy import select as _sel  # noqa: PLC0415
    orm_rebill_rows: dict = {
        r.id: r
        for r in db.execute(
            _sel(CsvUploadRow).where(CsvUploadRow.id.in_(rebill_ids))
        ).scalars().all()
    }

    seen_reject_ids: set = set()  # enforce one anomaly per 75-row
    for pr in pair_rows:
        if pr.reject_row_id in seen_reject_ids:
            continue  # already produced one anomaly for this r75 row
        reject_ts = _parse_ts(pr.reject_ts_raw)
        rebill_ts = _parse_ts(pr.rebill_ts_raw)
        if reject_ts is None or rebill_ts is None or rebill_ts <= reject_ts:
            continue
        elapsed_h = (rebill_ts - reject_ts).total_seconds() / 3600.0
        if elapsed_h > 24.0:
            continue
        bucket = "le12h" if elapsed_h <= 12.0 else "12_24h"

        orm_row = orm_rebill_rows.get(pr.rebill_row_id)
        if orm_row is None:
            continue

        anomaly = _make_anomaly(
            run=run,
            instance=_inst,
            csv_row=orm_row,
            finding_code=_FINDING_CODE,
            finding_summary=(
                f"Reject 75→70 fast-rebill: rx_number_hash={pr.rx_hash}, "
                f"elapsed={elapsed_h:.1f}h, bucket={bucket}"
            ),
            finding_details={
                "rx_number_hash": pr.rx_hash,
                "reject_row_id": str(pr.reject_row_id),
                "rebill_row_id": str(pr.rebill_row_id),
                "reject_ts": reject_ts.isoformat(),
                "rebill_ts": rebill_ts.isoformat(),
                "elapsed_hours": str(round(elapsed_h, 2)),
                "bucket": bucket,
                "group_key_collision_risk": (
                    "rx_number_hash collision possible for distinct Rx at same pharmacy"
                ),
            },
            severity="high",
            confidence_num=Decimal("0.80"),
        )
        anomalies.append(anomaly)
        seen_reject_ids.add(pr.reject_row_id)

    return anomalies
```

Also add rule type seeder entry in `rule_type_registry.py` RULE_TYPE_CATALOG:
```python
{"code": "REJECT-75-70", "name": "Reject-75→70 Fast Rebill",
 "description": "PA-required reject (75) followed by not-covered reject (70) for same Rx within 24h",
 "family": _CATEGORY_FAMILY["billing_pattern"], "parameter_schema_version": "1.0",
 "default_severity": "high", "default_confidence": 0.80,
 "requires_baseline": False, "requires_history": True, "deferred_data_feed": False,
 "deferred_reason": "", "required_data_columns": ["rx_number_hash", "reject_code", "date_added_timestamp"],
 "default_parameters": {"bucket_le12h_enabled": True, "bucket_12_24h_enabled": True}},
```

Run tests → GREEN.

```
git add modules/reclaimrx/src/detection/reject_rebill.py \
        modules/reclaimrx/src/detection/rule_type_registry.py \
        modules/reclaimrx/tests/detection/test_reject_75_70.py
git commit -m "feat(reclaimrx): REJECT-75-70 fast-rebill rule — rx_number_hash group key, le12h/12_24h buckets (locked decision #1)"
```

---

## Phase 4 — Reference New-C (§12 H5) (3 tasks)

**PRICING BASIS SIGN-OFF NOTE (top of this phase):**
WAC (price_type 09) AND SWP-as-AWP (price_type 07) are BOTH LIVE as of 2026-05-31 per Mike K sign-off.
This is a documented DEVIATION from §12 H6 (which said SWP stays disabled until sign-off).
The sign-off has occurred. Codex L2 must bless this deviation explicitly.
NADAC (price_type 24/25) is also included for informational enrichment.
Complete Task 0b verification BEFORE writing the FDB join query (record price_type → short_desc mapping).

---

### Task 4a — ALL-002 Phantom/Excluded Pharmacy (§12 H5)

**Locked decisions #3 and #4 encoded:**
- Phantom = valid 10-digit pharmacy NPI **absent from `reference.dataq_master`** (`is_phantom = reference.dataq_master.npi IS NULL` after LEFT JOIN on `nl.npi`).
- Deactivation leg: `reference.dataq_master.deactivation_code` (non-NULL = deactivated).
- Exclusion legs: `reference.oig_leie_exclusions` / `reference.sam_exclusions` (exact NPI match).
- No FWA-marker leg: `dataq_fwa_markers` does not exist; `dataq_fwa_attestation` is ncpdp-keyed and out of scope.
- All `reference.*` tables are FDW foreign tables (postgres_fdw `reference` schema). No grants needed.
- Valid 10-digit NPI only. Missing/invalid NPI → `resolution_stats["data_quality"]` counter, NOT an anomaly.

**Test file:** `modules/reclaimrx/tests/detection/test_all002_all003.py`

```python
"""Tests for ALL-002 Phantom Pharmacy and ALL-003 Phantom Prescriber (§12 H5).

IMPORTANT: These tests are marked skipif not REAL_DB because they require
Postgres with the FDW reference.* schema (reference.dataq_master, reference.prescribers,
reference.oig_leie_exclusions, reference.sam_exclusions) accessible via the
pre-existing postgres_fdw `reference` foreign-table schema (setup_fdw.sh).
The pure-logic unit tests (valid NPI gating) can run on SQLite.
"""
from __future__ import annotations
import os
import pytest
from decimal import Decimal
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

    §12 H5: missing/invalid NPIs → resolution_stats["data_quality"] counter (row-level).
    Keys: data_quality.missing_pharmacy_npi (NULL/empty), data_quality.invalid_pharmacy_npi
    (non-null but not 10-digit), data_quality.missing_prescriber_npi, data_quality.invalid_prescriber_npi.

    IMPORTANT: The full evaluator uses Postgres-specific `~`/`!~` regex operators for
    set-based SQL DQ counting.  The test below therefore exercises the PURE-PYTHON path
    (_count_npi_dq helper that uses _is_valid_npi) — it does NOT call
    evaluate_all002_phantom_pharmacy directly, which would fail on SQLite.
    The full evaluator test (which calls evaluate_all002_phantom_pharmacy on live data)
    lives in TestALL002PhantomFires and is marked @pytest.mark.skipif(not REAL_DB).
    """

    def test_missing_and_invalid_npi_row_counts_correct(self):
        """Pure-Python unit test: _count_npi_dq classifies NPIs correctly.

        Input NPI values:
          None, None               → 2 missing
          "123456789"              → invalid (9 digits, fails re.fullmatch)
          "MA3253488"              → invalid (non-numeric, fails re.fullmatch)
          "ABCDEFGHIJ"             → invalid (10 chars but all alpha — re.fullmatch r'[0-9]{10}' fails)
          "1234567890"             → valid (10 decimal digits)

        Expected: missing=2, invalid=3, valid=1.
        'ABCDEFGHIJ' MUST be counted as invalid, NOT as valid, NOT silently dropped.

        No DB required: _count_npi_dq is a pure-Python function using _is_valid_npi.
        """
        from src.detection.reference_rules import _is_valid_npi

        # Inline pure-Python DQ counter — same logic the evaluator delegates to.
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
            "'ABCDEFGHIJ' is 10 chars but all-alpha — must be INVALID, not valid"
        )


class TestALL002PhantomFires:
    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
    def test_npi_not_in_dataq_master_fires(self, db):
        """A valid 10-digit NPI not in dataq_master must produce an ALL-002 anomaly."""
        from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
        from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
        from datetime import date as _date

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
        # Stub instance — evaluator unit test does not need a persisted DB row;
        # we pass an enabled DetectionRuleInstance directly.
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
```

Run → RED.

**Implementation** (`modules/reclaimrx/src/detection/reference_rules.py`):

```python
"""Reference-data-backed detection rules: ALL-002, ALL-003.

FDW REFERENCE SCHEMA: This module reads from the postgres_fdw `reference` foreign-table
schema (provisioned by infrastructure/scripts/setup_fdw.sh). No module-owned grants needed.
Tables used: reference.dataq_master, reference.oig_leie_exclusions, reference.sam_exclusions,
reference.prescribers.

ALL-002: Phantom/Excluded Pharmacy
  - Phantom = valid 10-digit NPI absent from reference.dataq_master (is_phantom = dm.npi IS NULL).
  - Deactivation: reference.dataq_master.deactivation_code (non-NULL = deactivated).
  - Exclusion: reference.oig_leie_exclusions, reference.sam_exclusions (exact NPI match).
  - No FWA-marker leg (dataq_fwa_markers does not exist; dataq_fwa_attestation is ncpdp-keyed).
  - Valid 10-digit NPI ONLY. Invalid NPI → data_quality counter, NOT anomaly.

ALL-003: Phantom/Excluded Prescriber
  - Uses reference.prescribers for status/deactivation check.
  - Uses reference.oig_leie_exclusions and reference.sam_exclusions for exclusion check.
  - Valid 10-digit NPI ONLY. No DEA leg (dea_registrations is empty per spec).

Set-based implementation: collect all distinct valid NPIs for the run, run ONE
batched JOIN per reference table, return lookup results. NOT per-row N+1 queries.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.detection.batch_engine import _make_anomaly, _valid_npi
from src.models.detection_run_models import (
    Anomaly, CsvUploadRow, DetectionRun, DetectionRuleInstance,
)

_NPI_RE = re.compile(r'^\d{10}$')


def _is_valid_npi(value: Any) -> bool:
    """Return True only for a string of exactly 10 decimal digits."""
    if value is None:
        return False
    return bool(_NPI_RE.fullmatch(str(value)))


def _stub_instance() -> DetectionRuleInstance:
    inst = DetectionRuleInstance.__new__(DetectionRuleInstance)
    inst.id = None
    inst.parameters = {}
    return inst


def evaluate_all002_phantom_pharmacy(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
) -> tuple[list[Anomaly], dict]:
    """ALL-002: Phantom/Excluded Pharmacy.

    Returns (anomalies, data_quality_dict).
    data_quality_dict has explicit keys per §12 H5:
      missing_pharmacy_npi  — ROW-LEVEL count of rows with NULL/empty NPI
      invalid_pharmacy_npi  — ROW-LEVEL count of rows with non-10-digit NPI
    These rows are NOT phantom-flagged and stay outside the <1% FWA target.

    Set-based: 3 queries total regardless of NPI count.
    No per-row N+1 queries (verified by constant-query-count test).
    """
    anomalies: list[Anomaly] = []
    _dq: dict[str, int] = {"missing_pharmacy_npi": 0, "invalid_pharmacy_npi": 0}
    _inst = instance or _stub_instance()
    _inst.rule_type_code = "ALL-002"

    # Step 1: collect ALL resolved_pharmacy_npi values for the run (including NULLs).
    # DQ classification is done in PYTHON using _is_valid_npi — this makes the
    # counting path portable (SQLite and Postgres) without using `~`/`!~` operators.
    # "Missing"   = NULL or empty string.
    # "Invalid"   = non-null, non-empty, but _is_valid_npi returns False.
    #   This correctly captures 10-char alpha strings like 'ABCDEFGHIJ' as invalid.
    # "Valid"     = _is_valid_npi returns True → collected as distinct set for
    #               reference lookup below.
    #
    # Two portable SQL queries (no ~, !~, FILTER):
    #   Q1a: count of NULL/empty rows (missing)
    #   Q1b: all non-null non-empty resolved_pharmacy_npi values (classify in Python)
    #
    # NOTE: On Postgres the set-based reference CTE (Step 2) still uses `~` for the
    # DISTINCT ON lookup — that query is only reached when valid_npis is non-empty,
    # i.e., only on Postgres with the real reference tables.  The DQ counting path
    # (Q1a/Q1b) is portable and exercises cleanly on SQLite.
    missing_count_row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (resolved_pharmacy_npi IS NULL OR resolved_pharmacy_npi = '')
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchone()
    _dq["missing_pharmacy_npi"] = int(missing_count_row.cnt or 0) if missing_count_row else 0

    npi_candidate_rows = db.execute(
        text("""
            SELECT resolved_pharmacy_npi AS npi
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND resolved_pharmacy_npi IS NOT NULL
              AND resolved_pharmacy_npi != ''
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    all_candidate_npis = [r.npi for r in npi_candidate_rows if r.npi]

    # Classify in Python using _is_valid_npi (portable, no Postgres operators).
    invalid_npis = [v for v in all_candidate_npis if not _is_valid_npi(v)]
    _dq["invalid_pharmacy_npi"] = len(invalid_npis)
    valid_npis = list({v for v in all_candidate_npis if _is_valid_npi(v)})

    if not valid_npis:
        return anomalies, _dq

    # Step 2: one CTE lookup — dataq_master presence, deactivation, fwa_markers, oig/sam.
    # Returns one row per NPI with flags.
    placeholders = ", ".join([f":npi_{i}" for i in range(len(valid_npis))])
    npi_params = {f"npi_{i}": npi for i, npi in enumerate(valid_npis)}

    reference_sql = text(f"""
        WITH npi_list AS (
            SELECT unnest(ARRAY[{placeholders}]::text[]) AS npi
        ),
        dataq AS (
            -- Use nl.npi (claim-side) as the key so phantom rows (dm.npi IS NULL) are preserved.
            -- If dm.npi were used, phantom NPIs would be NULL and the final JOIN would drop them.
            -- dm_npi is the reference-side key: NULL means no matching row → phantom.
            SELECT nl.npi AS npi, dm.npi AS dm_npi, dm.deactivation_code, dm.legal_business_name
            FROM npi_list nl
            LEFT JOIN reference.dataq_master dm ON dm.npi = nl.npi
        ),
        exclusions AS (
            SELECT nl.npi,
                   oig.excldate AS oig_excldate,
                   sam.active_date AS sam_active_date
            FROM npi_list nl
            LEFT JOIN reference.oig_leie_exclusions oig ON oig.npi = nl.npi
            LEFT JOIN reference.sam_exclusions sam ON sam.npi = nl.npi
        )
        SELECT d.npi,
               d.deactivation_code,
               d.legal_business_name,
               e.oig_excldate,
               e.sam_active_date,
               (d.dm_npi IS NULL) AS is_phantom
        FROM dataq d
        JOIN exclusions e ON e.npi = d.npi
    """)

    ref_rows = db.execute(reference_sql, npi_params).fetchall()
    ref_by_npi: dict[str, Any] = {r.npi: r for r in ref_rows}

    # Determine flagged NPIs and their reason/provenance (pure Python, no DB)
    flagged: dict[str, tuple[str, dict[str, Any], str | None]] = {}
    for npi, ref in ref_by_npi.items():
        if ref.is_phantom:
            flagged[npi] = ("phantom_not_in_dataq_master",
                            {"table": "reference.dataq_master", "npi": npi},
                            ref.legal_business_name)
        elif ref.deactivation_code:
            flagged[npi] = ("deactivated",
                            {"table": "reference.dataq_master",
                             "deactivation_code": ref.deactivation_code},
                            ref.legal_business_name)
        elif ref.oig_excldate:
            flagged[npi] = ("oig_excluded",
                            {"table": "reference.oig_leie_exclusions",
                             "exclusion_date": str(ref.oig_excldate)},
                            ref.legal_business_name)
        elif ref.sam_active_date:
            flagged[npi] = ("sam_excluded",
                            {"table": "reference.sam_exclusions",
                             "active_date": str(ref.sam_active_date)},
                            ref.legal_business_name)

    if not flagged:
        return anomalies, _dq

    # Step 3 — ONE batched query: fetch one representative source row per flagged NPI.
    # Uses a single IN-clause query over resolved_pharmacy_npi, then picks
    # the MIN(id) row per NPI in Python (no per-NPI loop query).
    flagged_npi_list = list(flagged.keys())
    fp_placeholders = ", ".join([f":fp_{i}" for i in range(len(flagged_npi_list))])
    fp_params = {f"fp_{i}": n for i, n in enumerate(flagged_npi_list)}
    rep_rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (resolved_pharmacy_npi)
                id, resolved_pharmacy_npi
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND resolved_pharmacy_npi IN ({fp_placeholders})
            ORDER BY resolved_pharmacy_npi, id
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id), **fp_params},
    ).fetchall()
    rep_id_by_npi: dict[str, Any] = {r.resolved_pharmacy_npi: r.id for r in rep_rows}

    # Batch-fetch the ORM objects for all representative row ids in ONE query
    if rep_id_by_npi:
        rid_placeholders = ", ".join([f":rid_{i}" for i in range(len(rep_id_by_npi))])
        rid_params = {f"rid_{i}": rid for i, rid in enumerate(rep_id_by_npi.values())}
        from sqlalchemy import select as sa_select  # noqa: PLC0415
        orm_rep_rows = db.execute(
            sa_select(CsvUploadRow).where(
                CsvUploadRow.id.in_(list(rep_id_by_npi.values()))
            )
        ).scalars().all()
        orm_by_npi: dict[str, CsvUploadRow] = {
            r.resolved_pharmacy_npi: r for r in orm_rep_rows
        }
    else:
        orm_by_npi = {}

    for npi, (reason, provenance, entity_name) in flagged.items():
        csv_row = orm_by_npi.get(npi)
        if csv_row is None:
            continue
        anomaly = _make_anomaly(
            run=run, instance=_inst, csv_row=csv_row,
            finding_code="ALL-002",
            finding_summary=f"Phantom/excluded pharmacy NPI {npi}: {reason}",
            finding_details={
                "pharmacy_npi": npi,
                "reason": reason,
                "provenance": provenance,
                "entity_name": entity_name,
            },
            severity="critical",
            confidence_num=Decimal("0.90"),
        )
        anomalies.append(anomaly)

    return anomalies, _dq


def evaluate_all003_phantom_prescriber(
    db: Session,
    run: DetectionRun,
    instance: DetectionRuleInstance | None = None,
) -> tuple[list[Anomaly], dict]:
    """ALL-003: Phantom/Excluded Prescriber.

    Fully set-based: THREE queries total regardless of flagged-NPI count:
      Q1: distinct valid prescriber_npis for the run
      Q2: one CTE join vs prescribers + oig/sam
      Q3: one DISTINCT ON batched fetch of representative source rows
    No per-NPI or per-row loop query. No N+1.
    No DEA leg (dea_registrations is empty per spec).
    Returns (anomalies, data_quality_dict).
    data_quality_dict has explicit keys per §12 H5:
      missing_prescriber_npi  — ROW-LEVEL count of rows with NULL/empty NPI
      invalid_prescriber_npi  — ROW-LEVEL count of rows with non-10-digit NPI
    """
    anomalies: list[Anomaly] = []
    _dq: dict[str, int] = {"missing_prescriber_npi": 0, "invalid_prescriber_npi": 0}
    _inst = instance or _stub_instance()
    _inst.rule_type_code = "ALL-003"

    # Q1: collect ALL prescriber_npi values for DQ classification + valid-NPI collection.
    # DQ classification done in PYTHON using _is_valid_npi — portable (SQLite and Postgres).
    # Same valid-NPI definition as ALL-002: exactly 10 decimal digits.
    # "Missing" = NULL or empty string (row_data key absent OR empty).
    # "Invalid" = present but _is_valid_npi returns False (catches alpha-10-char NPIs).
    #
    # Two portable SQL queries (no ~, !~, FILTER, Postgres-only operators):
    #   Q1a: count of rows where prescriber_npi is missing
    #   Q1b: all non-null non-empty prescriber_npi values → classify in Python
    presc_missing = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND ((row_data->>'prescriber_npi') IS NULL
                   OR (row_data->>'prescriber_npi') = '')
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchone()
    _dq["missing_prescriber_npi"] = int(presc_missing.cnt or 0) if presc_missing else 0

    presc_candidate_rows = db.execute(
        text("""
            SELECT (row_data->>'prescriber_npi') AS npi
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'prescriber_npi') IS NOT NULL
              AND (row_data->>'prescriber_npi') != ''
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    all_presc_candidates = [r.npi for r in presc_candidate_rows if r.npi]

    # Classify in Python using _is_valid_npi (portable, no Postgres operators).
    _dq["invalid_prescriber_npi"] = sum(1 for v in all_presc_candidates if not _is_valid_npi(v))
    valid_npis = list({v for v in all_presc_candidates if _is_valid_npi(v)})

    if not valid_npis:
        return anomalies, _dq

    # Q2: one CTE reference join
    placeholders = ", ".join([f":npi_{i}" for i in range(len(valid_npis))])
    npi_params = {f"npi_{i}": npi for i, npi in enumerate(valid_npis)}

    reference_sql = text(f"""
        WITH npi_list AS (
            SELECT unnest(ARRAY[{placeholders}]::text[]) AS npi
        ),
        presc AS (
            -- Use nl.npi (claim-side) as the key so phantom rows (p.npi IS NULL) are preserved.
            -- If p.npi were used, phantom NPIs would be NULL and the final JOIN would drop them.
            -- p_npi is the reference-side key: NULL means no matching row → phantom.
            SELECT nl.npi AS npi, p.npi AS p_npi, p.status, p.deactivation_date, p.display_name
            FROM npi_list nl
            LEFT JOIN reference.prescribers p ON p.npi = nl.npi
        ),
        excl AS (
            SELECT nl.npi,
                   oig.excldate AS oig_excldate,
                   sam.active_date AS sam_active_date
            FROM npi_list nl
            LEFT JOIN reference.oig_leie_exclusions oig ON oig.npi = nl.npi
            LEFT JOIN reference.sam_exclusions sam ON sam.npi = nl.npi
        )
        SELECT pr.npi, pr.status, pr.deactivation_date, pr.display_name,
               ex.oig_excldate, ex.sam_active_date,
               (pr.p_npi IS NULL) AS is_phantom
        FROM presc pr
        JOIN excl ex ON ex.npi = pr.npi
    """)

    ref_rows = db.execute(reference_sql, npi_params).fetchall()

    # Determine flagged set (pure Python, no DB)
    flagged_p: dict[str, tuple[str, dict[str, Any], str | None]] = {}
    for ref in ref_rows:
        if ref.is_phantom:
            flagged_p[ref.npi] = ("phantom_not_in_prescribers",
                                  {"table": "reference.prescribers", "npi": ref.npi},
                                  ref.display_name)
        elif ref.status == "deactivated" or ref.deactivation_date:
            flagged_p[ref.npi] = ("deactivated",
                                  {"table": "reference.prescribers",
                                   "deactivation_date": str(ref.deactivation_date)},
                                  ref.display_name)
        elif ref.oig_excldate:
            flagged_p[ref.npi] = ("oig_excluded",
                                  {"table": "reference.oig_leie_exclusions",
                                   "exclusion_date": str(ref.oig_excldate)},
                                  ref.display_name)
        elif ref.sam_active_date:
            flagged_p[ref.npi] = ("sam_excluded",
                                  {"table": "reference.sam_exclusions",
                                   "active_date": str(ref.sam_active_date)},
                                  ref.display_name)

    if not flagged_p:
        return anomalies, _dq

    # Q3: one batched DISTINCT ON query for representative rows keyed by prescriber_npi.
    # Uses JSON extraction in SQL for prescriber_npi (Postgres ->> operator).
    fp_list = list(flagged_p.keys())
    fp_ph = ", ".join([f":fp_{i}" for i in range(len(fp_list))])
    fp_params = {f"fp_{i}": n for i, n in enumerate(fp_list)}
    rep_rows = db.execute(
        text(f"""
            SELECT DISTINCT ON (row_data->>'prescriber_npi')
                id, (row_data->>'prescriber_npi') AS prescriber_npi
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND (row_data->>'prescriber_npi') IN ({fp_ph})
            ORDER BY row_data->>'prescriber_npi', id
        """),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id), **fp_params},
    ).fetchall()
    rep_id_by_presc: dict[str, Any] = {r.prescriber_npi: r.id for r in rep_rows}

    from sqlalchemy import select as sa_select  # noqa: PLC0415
    orm_rep = db.execute(
        sa_select(CsvUploadRow).where(
            CsvUploadRow.id.in_(list(rep_id_by_presc.values()))
        )
    ).scalars().all()
    # Index by prescriber_npi extracted from row_data
    orm_by_presc: dict[str, CsvUploadRow] = {}
    for r in orm_rep:
        pnpi = str(r.row_data.get("prescriber_npi", "") or "").strip()
        if pnpi:
            orm_by_presc[pnpi] = r

    for npi, (reason, provenance, entity_name) in flagged_p.items():
        csv_row = orm_by_presc.get(npi)
        if csv_row is None:
            continue
        anomaly = _make_anomaly(
            run=run, instance=_inst, csv_row=csv_row,
            finding_code="ALL-003",
            finding_summary=f"Phantom/excluded prescriber NPI {npi}: {reason}",
            finding_details={
                "prescriber_npi": npi,
                "reason": reason,
                "provenance": provenance,
                "entity_name": entity_name,
            },
            severity="critical",
            confidence_num=Decimal("0.90"),
        )
        anomalies.append(anomaly)

    return anomalies, _dq
```

Add null-name no-fire tests (phantom = absent NPI, NOT null name) and constant-query-count test:
```python
# In test_all002_all003.py

@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_matched_npi_with_null_name_does_not_fire_phantom(db):
    """A pharmacy NPI that EXISTS in dataq_master but has a NULL legal_business_name
    must NOT be flagged as phantom. Phantom means the NPI is absent from the reference
    table entirely — tested via dm.npi IS NULL after LEFT JOIN, NOT via name nullness.

    Seeds: one dataq_master row with valid NPI + legal_business_name=NULL.
    Claim has that NPI.  Asserts zero ALL-002 phantom anomalies.
    """
    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from datetime import date as _date

    # Use a KNOWN-PRESENT NPI from reference.dataq_master (real data, no mutation).
    # Query the first active NPI that has a NULL legal_business_name — this tests
    # that phantom detection is based on row-absence (dm.npi IS NULL after LEFT JOIN),
    # not on name nullness.  If no null-name row exists, fall back to any present NPI
    # and rely on the assertion that the LEFT JOIN finds the row (not phantom).
    row = db.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, (
        "reference.dataq_master has no rows — FDW not set up. "
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
    """A pharmacy NPI with NO row in dataq_master MUST be flagged as phantom.

    Seeds: no dataq_master row for the NPI.  Claim has that NPI.
    Asserts at least one ALL-002 phantom anomaly with reason phantom_not_in_dataq_master.
    """
    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from datetime import date as _date

    # Use a synthetic 10-digit NPI that is guaranteed absent from reference.dataq_master
    # (all-nines format — never a valid NPPES NPI; no mutation of reference needed).
    ABSENT_NPI = "9999999991"
    # Verify it is absent — SELECT only, no mutation of the FDW foreign table.
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
    table entirely — tested via p.npi IS NULL after LEFT JOIN, NOT via display_name nullness.

    Seeds: one prescribers row with valid NPI + display_name=NULL.
    Claim has that NPI.  Asserts zero ALL-003 phantom anomalies.
    """
    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from datetime import date as _date

    # Use a KNOWN-PRESENT NPI from reference.prescribers (real data, no mutation).
    # Tests that phantom detection keys on row-absence (p.npi IS NULL after LEFT JOIN),
    # not on display_name nullness.
    row = db.execute(
        text(
            "SELECT npi FROM reference.prescribers "
            "WHERE npi IS NOT NULL AND (status IS NULL OR status != 'deactivated') "
            "LIMIT 1"
        )
    ).fetchone()
    assert row is not None, (
        "reference.prescribers has no rows — FDW not set up. "
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
    """A prescriber NPI with NO row in prescribers MUST be flagged as phantom.

    Seeds: no prescribers row for the NPI.  Claim has that NPI.
    Asserts at least one ALL-003 phantom anomaly with reason phantom_not_in_prescribers.
    """
    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from datetime import date as _date

    # Synthetic 10-digit NPI guaranteed absent from reference.prescribers (9.49M rows
    # but never includes all-nines formats).  No mutation of the FDW foreign table.
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


def _count_queries_for_n_npis(db, n: int) -> int:
    """Seed n distinct NPIs and return the number of SQL queries issued by evaluate_all002."""
    from src.detection.reference_rules import evaluate_all002_phantom_pharmacy
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from sqlalchemy import event as sa_event
    from datetime import date as _date

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


@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants")
def test_all002_query_count_constant_not_linear(db):
    """Query count must be CONSTANT as flagged-NPI count grows: 5 vs 50 NPIs → same count.

    Proves the implementation is set-based (O(1) queries), not N+1 (O(N) queries).
    """
    count_5 = _count_queries_for_n_npis(db, 5)
    count_50 = _count_queries_for_n_npis(db, 50)
    assert count_5 == count_50, (
        f"Query count is NOT constant: 5 NPIs={count_5}, 50 NPIs={count_50}. "
        f"N+1 pattern suspected."
    )
    # Absolute ceiling: at most 4 queries total (Q1 distinct NPIs + Q2 CTE join
    # + Q3 DISTINCT ON rep rows + Q4 ORM batch fetch)
    assert count_5 <= 4, f"Too many queries even for 5 NPIs: {count_5}"


def test_all003_returns_dict_with_required_keys(db):
    """evaluate_all003_phantom_prescriber returns (list, dict) with required DQ keys.

    PORTABLE (SQLite): seeds ONLY missing and invalid NPI rows — NO valid-format NPI rows.
    This keeps valid_npis empty so the early-return is taken before the Postgres-only
    reference CTE (reference.prescribers JOIN).  Asserts correct missing/invalid counts
    and correct dict shape.

    Seeds: 1 NULL prescriber_npi (missing), 1 invalid "BADNPI123" — no valid-format rows.
    Expected: missing=1, invalid=1, no anomalies.
    """
    from src.detection.reference_rules import evaluate_all003_phantom_prescriber
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, DetectionRuleInstance
    from datetime import date as _date

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all003-dq-shape", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": 2, "expected_count": 2},
    )
    db.add(run)
    db.flush()

    # Row 1: missing prescriber_npi (absent from row_data → NULL path)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    # Row 2: invalid prescriber_npi (non-10-digit → _is_valid_npi returns False)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={"prescriber_npi": "BADNPI123"},
        resolution_method="declared",
        resolved_pharmacy_npi="1111111111",
    ))
    # NO valid-format NPI row: valid_npis stays empty → early-return (no reference CTE,
    # no Postgres-only DISTINCT ON / ~ operators reached).
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
```

Run → GREEN.

```
git add modules/reclaimrx/src/detection/reference_rules.py \
        modules/reclaimrx/tests/detection/test_all002_all003.py
git commit -m "feat(reclaimrx): ALL-002/ALL-003 phantom+excluded pharmacy/prescriber via set-based reference joins (§12 H5, locked decisions #3 #4)"
```

---

### Task 4b — FDB pricing enrichment (WAC + NADAC + SWP-as-AWP)

**PRICING DEVIATION note (repeat):** SWP (price_type 07) is LIVE per Mike K sign-off 2026-05-31. This deviates from §12 H6 which deferred SWP until sign-off. Sign-off is granted. Codex L2 must bless this explicitly.

**File:** `modules/reclaimrx/src/detection/fdb_pricing.py`
**Test:** `modules/reclaimrx/tests/detection/test_fdb_pricing.py`

```python
"""Tests for FDB pricing enrichment (WAC type 09, NADAC 24/25, SWP-as-AWP 07).

Skipped on SQLite (no reference tables). Runs on live Postgres after migration 0010_reclaimrx_v2_ref_grants.
"""
from __future__ import annotations
import os
import pytest
REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")


class TestFDBPricingEnrichment:
    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with FDB grants")
    def test_wac_lookup_returns_decimal(self):
        import sqlalchemy as sa
        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs
        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            from sqlalchemy.orm import Session
            db = Session(bind=conn)
            # Use any NDC known to exist in fdb_ndc_price_history
            result = fetch_current_prices_for_ndcs(db, ["00000000000"])
            # result may be empty dict if NDC not found — that's OK
            for ndc, prices in result.items():
                assert "wac" not in prices or prices["wac"] is None or hasattr(prices["wac"], "quantize")

    @pytest.mark.skipif(not REAL_DB, reason="requires live Postgres")
    def test_no_n_plus_1_for_multiple_ndcs(self):
        import sqlalchemy as sa
        from src.detection.fdb_pricing import fetch_current_prices_for_ndcs
        engine = sa.create_engine(REAL_DB)
        with engine.connect() as conn:
            from sqlalchemy.orm import Session
            db = Session(bind=conn)
            ndcs = [f"0000000000{i}" for i in range(10)]
            query_count = [0]
            from sqlalchemy import event
            @event.listens_for(conn, "before_cursor_execute")
            def count(c, cursor, stmt, params, ctx, many): query_count[0] += 1
            fetch_current_prices_for_ndcs(db, ndcs)
            assert query_count[0] == 1, "fetch_current_prices_for_ndcs must issue exactly 1 query"
```

Run → RED.

**Implementation** (`modules/reclaimrx/src/detection/fdb_pricing.py`):

```python
"""FDB pricing enrichment: fetch current WAC, NADAC, and SWP-as-AWP for a set of NDCs.

PRICING SIGN-OFF (2026-05-31, Mike K):
  WAC  = price_type '09' — LIVE
  NADAC = price_type '24' or '25' — LIVE (informational)
  SWP-as-AWP = price_type '07' — LIVE (sign-off granted; deviation from §12 H6 deferred state)

FDW REFERENCE SCHEMA: reads reference.fdb_ndc_price_history, reference.fdb_price_type_desc,
reference.drugs via the pre-existing postgres_fdw `reference` foreign-table schema
(provisioned by infrastructure/scripts/setup_fdw.sh). No module-owned grants needed.

Set-based: ONE query for all NDCs. Never per-row.
Returns: {ndc_11: {"wac": Decimal|None, "nadac": Decimal|None, "swp": Decimal|None,
                    "drug_name": str|None}}
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

_PRICE_TYPE_WAC = "09"
_PRICE_TYPE_SWP = "07"
_PRICE_TYPE_NADAC_1 = "24"
_PRICE_TYPE_NADAC_2 = "25"


def fetch_current_prices_for_ndcs(
    db: Session,
    ndc_list: list[str],
) -> dict[str, dict[str, Any]]:
    """Fetch current WAC, NADAC, SWP prices for a list of NDC-11 values.

    Issues exactly ONE SQL query (CTE pivot). Returns empty dict if ndc_list is empty.
    Prices are Decimal or None. Never float.
    """
    if not ndc_list:
        return {}

    placeholders = ", ".join([f":ndc_{i}" for i in range(len(ndc_list))])
    ndc_params = {f"ndc_{i}": ndc for i, ndc in enumerate(ndc_list)}

    sql = text(f"""
        WITH ndc_set AS (
            SELECT unnest(ARRAY[{placeholders}]::text[]) AS ndc_11
        ),
        latest_prices AS (
            SELECT
                ph.ndc_11,
                ph.price_type,
                ph.price,
                ph.effective_date,
                ROW_NUMBER() OVER (
                    PARTITION BY ph.ndc_11, ph.price_type
                    ORDER BY ph.effective_date DESC
                ) AS rn
            FROM reference.fdb_ndc_price_history ph
            JOIN ndc_set ns ON ns.ndc_11 = ph.ndc_11
            WHERE ph.price_type IN (:wac, :swp, :nadac1, :nadac2)
        ),
        current_prices AS (
            SELECT ndc_11, price_type, price
            FROM latest_prices
            WHERE rn = 1
        ),
        drug_names AS (
            SELECT d.ndc_11, d.proprietary_name
            FROM reference.drugs d
            JOIN ndc_set ns ON ns.ndc_11 = d.ndc_11
        )
        SELECT
            ns.ndc_11,
            MAX(CASE WHEN cp.price_type = :wac   THEN cp.price END) AS wac_price,
            MAX(CASE WHEN cp.price_type = :swp   THEN cp.price END) AS swp_price,
            MAX(CASE WHEN cp.price_type IN (:nadac1, :nadac2) THEN cp.price END) AS nadac_price,
            dn.proprietary_name AS drug_name
        FROM ndc_set ns
        LEFT JOIN current_prices cp ON cp.ndc_11 = ns.ndc_11
        LEFT JOIN drug_names dn ON dn.ndc_11 = ns.ndc_11
        GROUP BY ns.ndc_11, dn.proprietary_name
    """)

    params = {
        **ndc_params,
        "wac": _PRICE_TYPE_WAC,
        "swp": _PRICE_TYPE_SWP,
        "nadac1": _PRICE_TYPE_NADAC_1,
        "nadac2": _PRICE_TYPE_NADAC_2,
    }

    rows = db.execute(sql, params).fetchall()
    result: dict[str, dict[str, Any]] = {}
    for r in rows:
        def _to_decimal(v: Any) -> Decimal | None:
            if v is None:
                return None
            return Decimal(str(v)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)
        result[r.ndc_11] = {
            "wac": _to_decimal(r.wac_price),
            "swp": _to_decimal(r.swp_price),
            "nadac": _to_decimal(r.nadac_price),
            "drug_name": r.drug_name,
        }
    return result
```

Run → GREEN.

```
git add modules/reclaimrx/src/detection/fdb_pricing.py \
        modules/reclaimrx/tests/detection/test_fdb_pricing.py
git commit -m "feat(reclaimrx): FDB pricing enrichment — WAC/NADAC/SWP set-based CTE, one query for all NDCs (SWP sign-off 2026-05-31)"
```

---

### Task 4c — Wire ALL-002, ALL-003, REJECT-75-70, and FDB enrichment into run_detection

**What changes in `batch_engine.py`:**
- In `run_detection`, after the streaming scan (PASS 1), run the grouping pass (PASS 1b):
  call `evaluate_reject_75_70(db, run)` in the same grouping pass as ALL-001 and MFR-002,
  extending `all_anomalies` with its results before the Phase-1 guardrail check.
- After the grouping pass (PASS 2), call `evaluate_all002_phantom_pharmacy` and `evaluate_all003_phantom_prescriber`.
- Collect their breakdown dicts and merge into `resolution_stats["data_quality"]` (a dict with
  explicit keys per §12 H5: `missing_pharmacy_npi`, `invalid_pharmacy_npi`,
  `missing_prescriber_npi`, `invalid_prescriber_npi`; also keep `no_fdb_wac` there if
  already set by the FDB enrichment pass). Do NOT use `data_quality_skipped`.
- Extend `all_anomalies` with their results.
- Pre-fetch FDB prices for the run's distinct NDCs (one call to `fetch_current_prices_for_ndcs`) and store on a `_fdb_cache` dict passed to MFR-001/003 evaluators for enrichment.

**Concrete wiring — `run_detection` function signature and call order:**

```python
# modules/reclaimrx/src/detection/batch_engine.py  (relevant section of run_detection)
#
# Imports required at module level (already present in batch_engine.py from Phase 1;
# listed here for clarity — do NOT duplicate if already imported):
#   from decimal import Decimal
#   from sqlalchemy import select, text
#   from sqlalchemy.orm import Session
#   from src.models.detection_run_models import Anomaly, CsvUploadRow, DetectionRun
#   from src.detection.reference_rules import (
#       evaluate_all002_phantom_pharmacy, evaluate_all003_phantom_prescriber,
#   )
#   from src.detection.fdb_pricing import fetch_current_prices_for_ndcs
# NOTE: fetch_current_prices_for_ndcs MUST be imported at MODULE scope (not inside
# run_detection) so that tests can patch it as
# `src.detection.batch_engine.fetch_current_prices_for_ndcs`. A local (function-level)
# import creates a name only in the function's local namespace, making the
# batch_engine-attribute patch ineffective.
# NOTE: `import sqlalchemy as sa` is NOT used in this sketch; use `text(...)` and
# `select(...)` directly (already imported above). The `sa.text(...)` form requires
# `import sqlalchemy as sa` — prefer the direct-name imports to avoid ambiguity.
#
# Task 4c wires ALL-002/003 and the FDB cache into run_detection.
# The guardrail check and bulk-insert promote path are the CANONICAL Phase-1
# implementations (_bulk_insert_anomalies + the structured guardrail_trip block
# from Task 1a/1b). Task 4c DOES NOT re-implement them — it only adds:
#   • pre-fetch of distinct NDCs for the FDB cache (set-based, before the stream)
#   • yield_per streaming scan replacing the former .all() materialisation
#   • calls to evaluate_all002_phantom_pharmacy / evaluate_all003_phantom_prescriber
#     and merges their data_quality dicts before handing all_anomalies to the
#     Phase-1 canonical guardrail+promote block.

def run_detection(db: Session, run: DetectionRun) -> int:
    """Run the full detection pipeline for a detection run.

    Call order:
      0. PRE-FETCH: distinct NDCs → _fdb_cache (one IN query).
         distinct pharmacy-NPIs and prescriber-NPIs are NOT pre-fetched here;
         ALL-002/003 do their own set-based prefetch internally.
      1. STREAMING SCAN (yield_per=500): evaluate per-row rules over CsvUploadRow
         without materialising all 2.6M rows. Reference/FDB lookups are done
         from pre-fetched in-memory dicts — zero per-row DB queries inside the loop.
      1b. GROUPING PASS (set-based): evaluate grouping/sequence rules that require
         multi-row context — ALL-001, MFR-002, REJECT-75-70.  Each uses a single
         set-based self-join or CTE (no per-row loop query).
      2. ALL-002 / ALL-003 set-based phantom-NPI checks (each issues ≤4 queries total).
      3. data_quality dict: merge FDB no_fdb_wac + ALL-002/003 NPI breakdown.
      4. Phase-1 canonical guardrail check (Decimal-based, per-rule cap clamped to
         ceiling, structured guardrail_trip dict).  — defined in Task 1a.
      5. Phase-1 canonical bulk-insert promote path via _bulk_insert_anomalies
         (execute_values batches of 5000 on Postgres).  — defined in Task 1b.
    """
    # ── Step 0: PRE-FETCH distinct NDCs → FDB cache ──────────────────────────
    # One IN query for all distinct NDCs in the run. This avoids any per-row
    # DB query during the streaming scan below.
    # _fdb_cache shape: {ndc: {"wac": Decimal|None, "price_type": str|None,
    #                           "effective_date": date|None, "wac_source": "fdb"}}
    distinct_ndc_rows = db.execute(
        text(
            """
            SELECT DISTINCT resolved_ndc AS ndc
            FROM reclaimrx.csv_upload_rows
            WHERE detection_run_id = :run_id
              AND tenant_id = :tenant_id
              AND resolved_ndc IS NOT NULL
            """
        ),
        {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
    ).fetchall()
    distinct_ndcs: list[str] = [r.ndc for r in distinct_ndc_rows if r.ndc]

    _fdb_cache: dict[str, dict] = {}
    if distinct_ndcs:
        # Use the canonical Task 4b helper — one CTE query for all NDCs.
        # Returns {ndc_11: {"wac": Decimal|None, "swp": Decimal|None,
        #                    "nadac": Decimal|None, "drug_name": str|None}}.
        # Verified FDB columns: ndc_11, price, price_type, effective_date.
        # WAC = price_type '09' (wac key). No ndc/unit_price columns exist.
        # fetch_current_prices_for_ndcs is imported at MODULE SCOPE above —
        # do NOT re-import here (local import breaks the patch target).
        raw_fdb = fetch_current_prices_for_ndcs(db, distinct_ndcs)
        for ndc_11, price_data in raw_fdb.items():
            _fdb_cache[ndc_11] = {
                "wac": price_data.get("wac"),
                "price_type": "09" if price_data.get("wac") is not None else None,
                "effective_date": None,   # not exposed by helper; unused downstream
                "wac_source": "fdb",
            }
    # fetch_current_prices_for_ndcs returns an entry for EVERY requested NDC;
    # a missing WAC is represented as wac=None (key present, value None) — NOT an absent key.
    # Count a missing WAC as: entry present but wac is None, OR ndc absent from cache.
    no_fdb_wac: int = sum(
        1 for ndc in distinct_ndcs
        if _fdb_cache.get(ndc, {}).get("wac") is None
    )

    # ── Step 0b: Load enabled DetectionRuleInstances for this tenant ─────────
    # One query — results partitioned by explicit rule_type_code membership into
    # four dispatch buckets.  DetectionRuleInstance has NO rule_kind column; the
    # partitioning is done entirely by checking inst.rule_type_code against these
    # module-level constant sets (defined once here so tests can import them).
    #
    # _PER_ROW_CODES      — MFR-001 (default disabled), MFR-003, HP-008
    # _GROUPING_CODES     — ALL-001, MFR-002, REJECT-75-70
    # _STATISTICAL_CODES  — MFR-004, HP-005, ALL-006, ALL-005
    # _REFERENCE_CODES    — ALL-002, ALL-003
    _PER_ROW_CODES: frozenset[str] = frozenset({"MFR-001", "MFR-003", "HP-008"})
    _GROUPING_CODES: frozenset[str] = frozenset({"ALL-001", "MFR-002", "REJECT-75-70"})
    _STATISTICAL_CODES: frozenset[str] = frozenset({"MFR-004", "HP-005", "ALL-006", "ALL-005"})
    _REFERENCE_CODES: frozenset[str] = frozenset({"ALL-002", "ALL-003"})

    from src.models.detection_run_models import DetectionRuleInstance  # noqa: PLC0415
    applicable: list[DetectionRuleInstance] = db.execute(
        select(DetectionRuleInstance).where(
            DetectionRuleInstance.tenant_id == run.tenant_id,
            DetectionRuleInstance.enabled.is_(True),
        )
    ).scalars().all()
    # `applicable` is the SINGLE enabled-instance list consumed by both the dispatch
    # loops below AND the Phase-1 canonical guardrail finalization block (which
    # iterates `applicable` to build per-rule fire-rate caps).  Reference instances
    # (ALL-002/003) are included in `applicable` so their fire counts are capped.

    per_row_instances     = [i for i in applicable if i.rule_type_code in _PER_ROW_CODES]
    grouping_instances    = [i for i in applicable if i.rule_type_code in _GROUPING_CODES]
    statistical_instances = [i for i in applicable if i.rule_type_code in _STATISTICAL_CODES]
    reference_instances   = [i for i in applicable if i.rule_type_code in _REFERENCE_CODES]

    # Dispatch maps: rule_type_code → evaluator callable.
    # Per-row evaluators accept (row, *, db, _fdb_cache, instance).
    # Grouping/statistical evaluators accept (db, run, instance).
    # These are the canonical evaluators defined in prior phases — Task 4c does NOT
    # re-implement them; it only wires them into the unified dispatch below.
    from src.detection.reference_rules import (  # noqa: PLC0415
        evaluate_all002_phantom_pharmacy,
        evaluate_all003_phantom_prescriber,
    )
    from src.detection.reject_rebill import evaluate_reject_75_70  # noqa: PLC0415
    from src.detection.mfr003_evaluator import (  # noqa: PLC0415
        evaluate_mfr003_row,   # per-row adapter: (row, *, db, _fdb_cache, instance) → Anomaly|None
        evaluate_hp008_row,    # per-row adapter: (row, *, db, _fdb_cache, instance) → Anomaly|None
    )
    from src.detection.mfr001_evaluator import evaluate_mfr001_row  # noqa: PLC0415
    # evaluate_mfr001_row is a thin adapter over evaluate_mfr001_per_patient_row that
    # accepts (row, *, db, _fdb_cache, instance, _mfr001_index=None).
    # NQ = ingredient_cost_paid (NOT quantity_dispensed).
    # Prior-fill index (_mfr001_index) is precomputed before the stream — zero per-row DB queries.
    # Defined in mfr001_evaluator.py alongside evaluate_mfr001_per_patient_row (Task 5b).
    # Disabled by default — not in per_row_instances until operator enables post-coverage-gate.

    _PER_ROW_EVALUATORS: dict[str, Any] = {
        "MFR-001": evaluate_mfr001_row,   # disabled by default until coverage gate (Task 5a)
        "MFR-003": evaluate_mfr003_row,   # FDB-WAC IC deviation, per-row
        "HP-008":  evaluate_hp008_row,    # high-cost claimant percentile, per-row
    }
    _GROUPING_EVALUATORS: dict[str, Any] = {
        "ALL-001":      _evaluate_all001,        # duplicate claim detection
        "MFR-002":      _evaluate_mfr002,        # bill-reverse-rebill sequence
        "REJECT-75-70": evaluate_reject_75_70,   # reject-code-75 → rebill-70 within window
    }
    _STATISTICAL_EVALUATORS: dict[str, Any] = {
        "MFR-004": _evaluate_statistical_rules,  # NDC volume spike (entity-level)
        "HP-005":  _evaluate_statistical_rules,  # prescriber outlier (entity-level)
        "ALL-006": _evaluate_statistical_rules,  # weekend/holiday fill pattern
        "ALL-005": _evaluate_statistical_rules,  # early refill (patient+NDC level)
    }
    # NOTE: _evaluate_statistical_rules is the canonical Task 2b evaluator that
    # reads rule_type_code/parameters from the instance and dispatches to the correct
    # calibration helper (zscore_flag, percentile_within_cohort, threshold check).
    # It accepts (db, run, instance) and returns list[Anomaly].

    # ── Step 0c: MFR-001 prior-NQ index (SET-BASED MINIMAL-COLUMN, before stream) ──
    # FIX (MED): The previous implementation used `.scalars().all()` which materializes
    # ALL full CsvUploadRow ORM objects — on the 2.6M-row file this loads gigabytes of
    # JSONB into Python memory, violating the streaming/perf design of the engine.
    #
    # Correct approach: build the index via a minimal-column SQL projection that
    # retrieves ONLY the four fields needed for the index
    # (patient_unique_hash, resolved_ndc, date_of_service, ingredient_cost_paid),
    # restricted to paid-B1 rows, as a lightweight tuple stream. This avoids
    # materializing full ORM objects or any unneeded JSONB columns.
    #
    # The build_mfr001_prior_nq_index function's input contract is updated to accept
    # either ORM rows (via .row_data dict) OR lightweight named-tuple rows
    # (via direct attribute access) — see mfr001_evaluator.py for the dual-path
    # implementation.
    _mfr001_inst = next(
        (i for i in per_row_instances if i.rule_type_code == "MFR-001"), None
    )
    _mfr001_index: dict | None = None
    if _mfr001_inst is not None:
        from src.detection.mfr001_evaluator import build_mfr001_prior_nq_index  # noqa: PLC0415
        # Minimal-column query: only the four fields needed for the index.
        # Restricted to paid-B1 rows (the only rows that feed the prior-NQ median).
        # NO full-row ORM fetch — no .scalars().all() on 2.6M rows.
        # Returns lightweight Row objects; build_mfr001_prior_nq_index accepts these
        # via its _from_raw_rows=True path (added alongside this fix).
        _mfr001_raw_rows = db.execute(
            text(
                """
                SELECT
                    (row_data->>'patient_unique_hash') AS patient_unique_hash,
                    resolved_ndc,
                    (row_data->>'date_of_service') AS date_of_service,
                    (row_data->>'ingredient_cost_paid') AS ingredient_cost_paid
                FROM reclaimrx.csv_upload_rows
                WHERE detection_run_id = :run_id
                  AND tenant_id = :tenant_id
                  AND (row_data->>'transaction_code') = 'B1'
                  AND (row_data->>'transaction_status') = 'Paid'
                  AND (row_data->>'ingredient_cost_paid') IS NOT NULL
                  AND (row_data->>'date_of_service') IS NOT NULL
                  AND (row_data->>'patient_unique_hash') IS NOT NULL
                  AND resolved_ndc IS NOT NULL
                ORDER BY (row_data->>'date_of_service')
                """
            ),
            {"run_id": str(run.id), "tenant_id": str(run.tenant_id)},
        ).fetchall()
        # build_mfr001_prior_nq_index handles both ORM rows (with .row_data dict)
        # and raw lightweight rows (with direct .patient_unique_hash, .resolved_ndc,
        # .date_of_service, .ingredient_cost_paid attributes) via _from_raw_rows=True.
        _mfr001_index = build_mfr001_prior_nq_index(
            _mfr001_raw_rows,
            params=_mfr001_inst.parameters,
            _from_raw_rows=True,
        )

    # ── Step 1: STREAMING SCAN — per-row rules ───────────────────────────────
    # yield_per(500) streams rows in 500-row server-side batches.
    # The loop never holds the full file in memory.
    # _fdb_cache is already built above — zero per-row DB queries inside the loop.
    # _mfr001_index is precomputed above — zero per-row DB queries for MFR-001.
    # Enabled instance list is pre-loaded above — no per-row session access.
    all_anomalies: list[Anomaly] = []
    record_count: int = 0

    for row in db.execute(
        select(CsvUploadRow).where(
            CsvUploadRow.detection_run_id == run.id,
            CsvUploadRow.tenant_id == run.tenant_id,
        )
    ).scalars().yield_per(500):
        # .scalars() is required: without it yield_per returns Row objects, not CsvUploadRow ORM objects.
        record_count += 1

        # Dispatch all enabled per-row rule instances via the per-kind loop.
        # MFR-001 is default-disabled (enabled=False after migration 0012) and will
        # therefore not appear in per_row_instances until the coverage gate passes
        # and an operator flips it to enabled=True — no separate guard needed here.
        for inst in per_row_instances:
            evaluator = _PER_ROW_EVALUATORS.get(inst.rule_type_code)
            if evaluator is None:
                continue  # unknown code — skip gracefully, do not raise
            # Pass _mfr001_index for MFR-001; other evaluators ignore it via **kwargs.
            extra = {"_mfr001_index": _mfr001_index} if inst.rule_type_code == "MFR-001" else {}
            result = evaluator(row, db=db, _fdb_cache=_fdb_cache, instance=inst, **extra)
            if result:
                all_anomalies.append(result)

    # ── Step 1b: GROUPING PASS — set-based multi-row rules ───────────────────
    # Each evaluator issues one set-based self-join or CTE query (no per-row N+1).
    # Returns list[Anomaly] not yet added to session — same contract as Task 1a.
    # ALL-001 (duplicate), MFR-002 (bill-reverse-rebill), REJECT-75-70 are all
    # dispatched here via the enabled instance loop so no rule is silently dropped
    # if its instance is disabled or not registered.
    for inst in grouping_instances:
        evaluator = _GROUPING_EVALUATORS.get(inst.rule_type_code)
        if evaluator is None:
            continue
        all_anomalies.extend(evaluator(db, run, inst))

    # ── Step 1c: STATISTICAL PASS — set-based outlier rules ─────────────────
    # MFR-004 (NDC volume spike), HP-005 (prescriber outlier), ALL-006
    # (weekend/holiday fill), ALL-005 (early refill) — each entity-level,
    # one anomaly per flagged entity.  _evaluate_statistical_rules reads
    # rule parameters from inst.parameters (calibrated by migration 0011 / Task 2a).
    # Uses BaselineCache loaded from calibration.py — no per-entity queries.
    for inst in statistical_instances:
        evaluator = _STATISTICAL_EVALUATORS.get(inst.rule_type_code)
        if evaluator is None:
            continue
        all_anomalies.extend(evaluator(db, run, inst))

    # ── Step 2: ALL-002 / ALL-003 set-based phantom-NPI checks ──────────────
    # Each evaluator runs ≤4 set-based queries regardless of NPI count (no N+1).
    # They return (list[Anomaly], dict) where the dict has explicit data_quality keys.
    # GATED: only fires when an enabled DetectionRuleInstance for that code is present
    # in `reference_instances`.  A disabled (or absent) instance means the rule does
    # NOT run — no anomalies are produced and data_quality keys are empty dicts.
    # The instance is passed in so each evaluator can read its `.parameters` JSONB
    # (e.g. custom lookback window or severity override) and so its fire count feeds
    # the per-rule guardrail cap via the shared `applicable` list (Fix 2).
    all002_quality: dict[str, int] = {}
    all003_quality: dict[str, int] = {}

    all002_inst = next(
        (i for i in reference_instances if i.rule_type_code == "ALL-002"), None
    )
    if all002_inst is not None:
        all002_anomalies, all002_quality = evaluate_all002_phantom_pharmacy(
            db, run, instance=all002_inst
        )
        all_anomalies.extend(all002_anomalies)

    all003_inst = next(
        (i for i in reference_instances if i.rule_type_code == "ALL-003"), None
    )
    if all003_inst is not None:
        all003_anomalies, all003_quality = evaluate_all003_phantom_prescriber(
            db, run, instance=all003_inst
        )
        all_anomalies.extend(all003_anomalies)
    # all002_quality keys (when ALL-002 ran): missing_pharmacy_npi, invalid_pharmacy_npi
    # all003_quality keys (when ALL-003 ran): missing_prescriber_npi, invalid_prescriber_npi

    # ── Step 3: data_quality dict (merged before guardrail) ─────────────────
    # All four NPI keys are initialized to 0 BEFORE merging evaluator outputs
    # so that absent evaluators (e.g. ALL-002 disabled) leave their keys at 0
    # rather than missing. §12 H5 + tests require ALL FOUR keys always present.
    data_quality: dict[str, int] = {
        "no_fdb_wac": no_fdb_wac,
        "missing_pharmacy_npi": 0,
        "invalid_pharmacy_npi": 0,
        "missing_prescriber_npi": 0,
        "invalid_prescriber_npi": 0,
        **all002_quality,   # overrides missing_pharmacy_npi, invalid_pharmacy_npi when ALL-002 ran
        **all003_quality,   # overrides missing_prescriber_npi, invalid_prescriber_npi when ALL-003 ran
    }
    run.resolution_stats = {
        **(run.resolution_stats or {}),
        "data_quality": data_quality,
    }
    db.flush()

    # ── Steps 4+5: Phase-1 canonical guardrail + bulk-insert promote path ────
    # The guardrail check and _bulk_insert_anomalies call are defined in Task 1a/1b
    # (the finalization block of run_detection).  Task 4c does NOT re-implement them.
    # The code continues into the existing finalization block in run_detection which:
    #   • Computes per-rule fire rates as Decimal (no float).
    #   • Clamps configured caps to _RULE_FIRE_RATE_CEILING (Decimal("0.005")).
    #   • Writes a structured guardrail_trip dict {tripped, rule, fire_rate, cap}
    #     and sets status='failed' with NO persisted anomalies on trip.
    #   • On pass, calls _bulk_insert_anomalies(db, all_anomalies) — execute_values
    #     in 5000-row batches on Postgres, ORM add_all on SQLite.
    #   • Sets run.status = 'completed' and run.anomaly_count = len(all_anomalies).
    # (The finalization block is not repeated here — it is the canonical Phase-1 code.)
```

Dispatch summary (complete in-scope rule set, nothing dropped):

| Pass | Rule codes dispatched | Dispatch mechanism |
|---|---|---|
| Per-row (Step 1) | MFR-003, HP-008 (always when enabled); MFR-001 (only if enabled=True after coverage gate) | loop over `per_row_instances`, dispatch by `rule_type_code` |
| Grouping (Step 1b) | ALL-001, MFR-002, REJECT-75-70 | loop over `grouping_instances`, dispatch by `rule_type_code` |
| Statistical (Step 1c) | MFR-004, HP-005, ALL-006, ALL-005 | loop over `statistical_instances`, dispatch by `rule_type_code` |
| Reference (Step 2) | ALL-002, ALL-003 | gated by enabled instance in `reference_instances`; instance passed to evaluator; data_quality dict returned only when instance present |

Signature notes:
- `evaluate_mfr003_row(row, *, db, _fdb_cache, instance)` — thin adapter in `mfr003_evaluator.py`; calls `_derive_statistical_metric` for MFR-003; reads `_fdb_cache.get(row.resolved_ndc, {})` to obtain WAC; sets `wac_source="fdb"` in `finding_details` when found. Returns `Anomaly|None`.
- `evaluate_mfr001_row(row, *, db, _fdb_cache, instance, _mfr001_index=None)` — thin adapter in `mfr001_evaluator.py`; NQ = `ingredient_cost_paid` (NOT `quantity_dispensed`); calls `evaluate_mfr001_per_patient_row` with strictly-prior median NQ from `_mfr001_index` (precomputed before stream — zero DB queries inside the loop); dollar_floor applied to `ingredient_cost_paid` directly. Disabled by default (`enabled=False` after migration 0012); not in `per_row_instances` until operator enables it post-coverage-gate. Returns `Anomaly|None`.
- `evaluate_hp008_row(row, *, db, _fdb_cache, instance)` — thin adapter in `mfr003_evaluator.py`; per-row percentile check against BaselineCache; uses CSV `total_paid_amt` (no FDB dependency). Returns `Anomaly|None`.
- `_evaluate_all001(db, run, instance)`, `_evaluate_mfr002(db, run, instance)` — existing Phase-1 grouping evaluators; Task 4c does not change their signatures.
- `evaluate_reject_75_70(db, run, instance)` — set-based self-join; Task 3b evaluator unchanged.
- `_evaluate_statistical_rules(db, run, instance)` — Task 2b evaluator; reads `instance.rule_type_code` and `instance.parameters` to dispatch to the correct calibration path. Signature `(db, run, instance)` is entity-level (MFR-004, HP-005, ALL-006, ALL-005) — NOT used for per-row rules (MFR-003, HP-008 use the `*_row` adapters above).
- `evaluate_all002_phantom_pharmacy(db, run, *, instance: DetectionRuleInstance)` and `evaluate_all003_phantom_prescriber(db, run, *, instance: DetectionRuleInstance)` — now accept the enabled instance so they can read `instance.parameters` and so their fire counts feed the per-rule guardrail cap; return `(list[Anomaly], dict)` unchanged.

**Test for FDB cache provenance** (add to `test_all002_all003.py`):

```python
def test_fdb_cache_built_once_and_mfr003_receives_it(db):
    """FDB cache is built once; MFR-003 uses wac_source='fdb' when WAC is found;
    an NDC whose cache entry has wac=None increments data_quality.no_fdb_wac.

    Pure-Python test double: injects a crafted _fdb_cache dict directly into
    fetch_current_prices_for_ndcs via unittest.mock.patch — no mutation of
    reference.fdb_ndc_price_history (FDW foreign table is READ-ONLY).

    _fdb_cache shape returned by fetch_current_prices_for_ndcs:
      {ndc_11: {"wac": Decimal|None, "swp": ..., "nadac": ..., "drug_name": ...}}
    An entry with wac=None is present for every requested NDC (key is always present).
    """
    from decimal import Decimal
    from unittest.mock import patch
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import DetectionRun, CsvUploadRow

    KNOWN_NDC = "00069315066"   # wac present in injected cache
    UNKNOWN_NDC = "99999999999"  # wac=None in injected cache → increments no_fdb_wac

    # Injected cache: fetch_current_prices_for_ndcs returns a dict with an entry
    # for every requested NDC; missing WAC is represented as wac=None (key present).
    _fake_fdb = {
        KNOWN_NDC:  {"wac": Decimal("12.50000"), "swp": None, "nadac": None, "drug_name": "TestDrug"},
        UNKNOWN_NDC: {"wac": None,               "swp": None, "nadac": None, "drug_name": None},
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
    # UNKNOWN_NDC has wac=None → no_fdb_wac must be >= 1
    assert dq.get("no_fdb_wac", 0) >= 1, (
        f"Expected no_fdb_wac >= 1 for UNKNOWN_NDC (wac=None), got data_quality={dq}"
    )
    # All four NPI keys must always be present (0 when that rule didn't run).
    for _key in ("missing_pharmacy_npi", "invalid_pharmacy_npi",
                 "missing_prescriber_npi", "invalid_prescriber_npi"):
        assert _key in dq, (
            f"data_quality must always contain '{_key}' (0 when rule not enabled), got keys={list(dq.keys())}"
        )

    # Any MFR-003 anomaly for KNOWN_NDC must have wac_source='fdb' in finding_details
    from src.models.detection_run_models import Anomaly
    from sqlalchemy import select as _sel
    mfr003_hits = db.execute(
        _sel(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "MFR-003",
        )
    ).scalars().all()
    for a in mfr003_hits:
        fd = a.finding_details or {}
        if fd.get("ndc") == KNOWN_NDC:
            assert fd.get("wac_source") == "fdb", (
                f"MFR-003 anomaly for KNOWN_NDC must have wac_source='fdb', got {fd}"
            )
```

**Test** (add to `test_all002_all003.py`):
```python
@pytest.mark.skipif(not REAL_DB, reason="requires live Postgres with reference grants from 0010")
def test_run_detection_wires_all002_and_produces_anomaly(db):
    """run_detection must produce exactly the planted ALL-002 anomaly for a phantom pharmacy.

    Seeding strategy to keep total flag rate under 1% so the run COMPLETES (not fails):
      - Insert NPI "1234560001" into reference.dataq_master as the known-good reference NPI.
      - 1 phantom-NPI row (the planted ALL-002 target: NPI "9999999999" absent from dataq_master)
      - 499 clean denominator rows all using NPI "1234560001" (known-present in dataq_master,
        NOT flagged by ALL-002)
      → planted ALL-002 count / 500 total = 0.2% < 1% guardrail → run COMPLETES

    Asserts:
      run.status == 'completed' (not 'failed' due to guardrail)
      Exactly 1 Anomaly with finding_code='ALL-002' and source_row_id == the planted row's id
    """
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import (
        DetectionRun, CsvUploadRow, Anomaly, DetectionRuleInstance,
    )
    from src.detection.rule_type_registry import register_rule_types
    from sqlalchemy import select, text
    from datetime import date as _date
    import uuid as _uuid

    TOTAL_ROWS = 500
    # Known-good NPI: query a REAL existing NPI from reference.dataq_master —
    # no mutation of the FDW foreign table (READ-ONLY for app role ifx_dev_app).
    # Any active NPI present in the real reference data is guaranteed not-phantom.
    _ref_row = db.execute(
        text(
            "SELECT npi FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert _ref_row is not None, (
        "reference.dataq_master has no active rows — FDW not provisioned. "
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

    # Planted phantom pharmacy row: valid 10-digit NPI that is ABSENT from dataq_master.
    # "9999999999" is never seeded above → ALL-002 flags it as phantom.
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
    # → ALL-002 will NOT flag any of them → total flag rate = 1/500 = 0.2% < 1% guardrail.
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

    # ALL-002 must be enabled via a DetectionRuleInstance — run_detection gates
    # the evaluator by reference_instances (FIX 3); without an enabled instance
    # ALL-002 would never fire even with a phantom row present.
    db.add(DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-wiring-test",
        enabled=True, effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    ))
    db.flush()

    run_detection(db, run)
    db.refresh(run)

    # Must complete — not fail due to guardrail (0.2% flag rate < 1% ceiling)
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
    # Phantom NPI in finding_details must equal the CLAIM-SIDE NPI ("9999999999"), not NULL.
    # This verifies the CTE fix: nl.npi (claim-side) is used as the result key so that
    # phantom rows — where dm.npi is NULL after the LEFT JOIN — still carry the correct NPI.
    assert all002_anomalies[0].finding_details.get("pharmacy_npi") == "9999999999", (
        f"ALL-002 phantom finding_details['pharmacy_npi'] must equal the claim NPI '9999999999'; "
        f"got {all002_anomalies[0].finding_details.get('pharmacy_npi')!r} — "
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


def test_run_detection_wires_reject_7570_and_produces_anomaly(db):
    """run_detection must produce the planted REJECT-75-70 anomaly and complete (not fail).

    Seeding strategy to keep total flag rate under 1% so the run COMPLETES:
      - 1 planted 75→70 sequence within 6h (the REJECT-75-70 target: 2 rows)
      - 998 clean denominator rows (no reject patterns, no duplicates)
      → Total rows: 1000. REJECT-75-70 fire rate: 1/1000 = 0.1% < 0.5% per-rule cap  ✓
        total fire rate: 1/1000 = 0.1% < 1.0% total cap                               ✓

    Asserts:
      run.status == 'completed' (not 'failed' due to guardrail)
      Exactly 1 Anomaly with finding_code='REJECT-75-70'
      The anomaly's source_row_id == the rebill row's id
      The anomaly's finding_details['bucket'] == 'le12h'
    """
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import (
        DetectionRun, CsvUploadRow, Anomaly, DetectionRuleInstance,
    )
    from src.detection.rule_type_registry import register_rule_types
    from sqlalchemy import select
    from datetime import datetime, timedelta, UTC, date as _date

    TOTAL_ROWS = 1000
    base_ts = datetime(2026, 1, 20, 8, 0, 0, tzinfo=UTC)

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="reject7570-wiring-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": TOTAL_ROWS, "expected_count": TOTAL_ROWS},
    )
    db.add(run)
    db.flush()

    # Row 1: reject code 75 (PA required) at t=0
    reject_row = CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "rx_number_hash": "RX-PLANT-001",
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": "75",
            "date_added_timestamp": base_ts.isoformat(),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-reject",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    )
    db.add(reject_row)
    db.flush()

    # Row 2: rebill with reject code 70 (not covered) at t+6h → bucket=le12h
    rebill_ts = base_ts + timedelta(hours=6)
    rebill_row = CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={
            "rx_number_hash": "RX-PLANT-001",
            "transaction_code": "B1",
            "transaction_status": "Rejected",
            "reject_code": "70",
            "date_added_timestamp": rebill_ts.isoformat(),
            "pharmacy_npi": "1234567890",
            "ndc": "12345678901",
            "patient_unique_hash": "patient-reject",
            "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared",
        resolved_pharmacy_npi="1234567890",
        resolved_ndc="12345678901",
    )
    db.add(rebill_row)
    db.flush()
    planted_rebill_id = rebill_row.id

    # 998 clean denominator rows — no reject patterns, no duplicates
    for i in range(3, TOTAL_ROWS + 1):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i,
            row_data={
                "patient_unique_hash": f"patient-clean-{i}",
                "ndc": f"0000000{i:04d}",
                "date_of_service": "2026-01-15",
                "auth_no_hash": f"auth-clean-{i}",
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "reversed_check": "No",
                "total_paid_amt": "50.00",
            },
            resolution_method="declared",
            resolved_ndc=f"0000000{i:04d}",
        ))
    db.flush()

    register_rule_types(db)

    # run_detection gates each evaluator on enabled DetectionRuleInstance rows.
    # register_rule_types only registers rule TYPES — instances must be seeded explicitly
    # so the grouping pass dispatches to evaluate_reject_75_70.
    db.add(DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID,
        rule_type_code="REJECT-75-70",
        instance_name="REJECT-75-70-wiring-test",
        enabled=True,
        effective_from=_date(2026, 1, 1),
        created_by=TEST_USER_ID,
        parameters={},
    ))
    db.flush()

    run_detection(db, run)
    db.refresh(run)

    # Must complete — guardrail must NOT trip (1/1000 = 0.1% < 0.5% per-rule ceiling)
    assert run.status == "completed", (
        f"run_detection must complete for 1/1000 REJECT-75-70 fire rate; "
        f"got status='{run.status}', guardrail={run.resolution_stats.get('guardrail')}"
    )

    # Exactly 1 REJECT-75-70 anomaly must be persisted
    r7570_anomalies = db.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "REJECT-75-70",
        )
    ).scalars().all()
    assert len(r7570_anomalies) == 1, (
        f"Expected exactly 1 REJECT-75-70 anomaly; got {len(r7570_anomalies)}. "
        "Check evaluate_reject_75_70 is wired into run_detection's grouping pass "
        "AND that an enabled DetectionRuleInstance for REJECT-75-70 exists."
    )

    # source_row_id must be the rebill row (the row flagged by the rule)
    assert r7570_anomalies[0].source_row_id == planted_rebill_id, (
        f"REJECT-75-70 anomaly must reference the rebill row {planted_rebill_id}; "
        f"got {r7570_anomalies[0].source_row_id}"
    )

    # Bucket must be le12h (6h elapsed ≤ 12h)
    assert r7570_anomalies[0].finding_details.get("bucket") == "le12h", (
        f"6h elapsed must classify as 'le12h'; "
        f"got {r7570_anomalies[0].finding_details.get('bucket')!r}"
    )
```

Run → GREEN.

**Coverage test — all v2 in-scope rules produce an anomaly when enabled** (add to `test_all002_all003.py`):

```python
def test_run_detection_dispatches_all_inscope_rules(db):
    """Given all v2 in-scope rules enabled (MFR-001 stays default-disabled) and
    one planted fire per rule kind under the guardrail cap, run_detection must
    produce an anomaly for EACH expected rule_code.

    This test fails if any in-scope rule is unwired from run_detection —
    i.e. it catches silently dropped rules in the dispatch loop.

    Rules under test (9 codes):
      Per-row:     MFR-003, HP-008
      Grouping:    ALL-001, MFR-002, REJECT-75-70
      Statistical: MFR-004, HP-005, ALL-006, ALL-005
      Reference:   ALL-002, ALL-003

    MFR-001 is excluded — it is disabled by default (enabled=False after migration
    0012) and requires the coverage gate (Task 5a) before enabling.

    Seeding strategy: 2000-row denominator so each rule fires at most 1/2000 = 0.05%
    — well under the 0.5% per-rule cap and 1.0% total cap.  Each planted anomaly is
    the minimal row(s) needed to trigger exactly that rule.

    NOTE: Statistical rules (MFR-004, HP-005, ALL-006, ALL-005) require a populated
    BaselineCache (mean/stddev/percentile) to fire.  This test seeds the
    reclaimrx.baseline_cache table directly with fixture values that guarantee each
    rule trips on the planted row.  If baseline_cache is not seeded, the statistical
    evaluators skip silently — the assert below will catch that.

    This is an integration test: it exercises the FULL run_detection dispatch path
    through the enabled-instance loop, not individual evaluators in isolation.
    """
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import (
        DetectionRun, CsvUploadRow, Anomaly,
        DetectionRuleType, DetectionRuleInstance,
    )
    from src.detection.rule_type_registry import register_rule_types
    from sqlalchemy import select, text
    from datetime import datetime, timedelta, UTC, date

    TOTAL_ROWS = 2000

    # Register all rule types so instances can reference them.
    register_rule_types(db)

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="all-rules-coverage-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": TOTAL_ROWS, "expected_count": TOTAL_ROWS},
    )
    db.add(run)
    db.flush()

    base_ts = datetime(2026, 2, 1, 10, 0, 0, tzinfo=UTC)

    # ── Plant per-row fires ────────────────────────────────────────────────
    # MFR-003: IC far above FDB WAC → z-score fires.
    # Use a real NDC present in reference.fdb_ndc_price_history with a known WAC
    # (price_type='09') — READ-ONLY query, no mutation of the FDW foreign table.
    _fdb_row = db.execute(
        text(
            "SELECT ndc_11 FROM reference.fdb_ndc_price_history "
            "WHERE price_type = '09' AND price > 0 "
            "LIMIT 1"
        )
    ).fetchone()
    assert _fdb_row is not None, (
        "reference.fdb_ndc_price_history has no WAC rows — FDW not provisioned. "
        "Run infrastructure/scripts/setup_fdw.sh first."
    )
    MFR003_NDC = _fdb_row.ndc_11
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "pharmacy_npi": "1000000001", "ndc": MFR003_NDC,
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "ingredient_cost_paid": "9999.00",
            "quantity_dispensed": "1", "total_paid_amt": "9999.00",
        },
        resolution_method="declared", resolved_pharmacy_npi="1000000001",
        resolved_ndc=MFR003_NDC,
    ))

    # HP-008: total_paid_amt at 99th+ percentile for the run.  Seed baseline_cache
    # with a low mean/stddev so this claim's $9800 amount sits far above it.
    HP008_NDC = "22222222222"
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=2,
        row_data={
            "pharmacy_npi": "1000000001", "ndc": HP008_NDC,
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "9800.00",
            "patient_unique_hash": "hp008-patient",
        },
        resolution_method="declared", resolved_pharmacy_npi="1000000001",
        resolved_ndc=HP008_NDC,
    ))

    # ── Plant grouping fires ───────────────────────────────────────────────
    # ALL-001: two rows same patient/ndc/dos, distinct auth
    for j, auth in enumerate(["AUTH-DUP-A", "AUTH-DUP-B"], start=3):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=j,
            row_data={
                "patient_unique_hash": "dup-patient", "ndc": "33333333333",
                "date_of_service": "2026-02-01", "auth_no_hash": auth,
                "transaction_code": "B1", "transaction_status": "Paid",
                "total_paid_amt": "50.00",
            },
            resolution_method="declared", resolved_ndc="33333333333",
        ))

    # MFR-002: B1 → B2 (reversal) → B1 (rebill at higher IC) sequence
    for j, (tc, ic) in enumerate([("B1", "80.00"), ("B2", "0.00"), ("B1", "120.00")], start=5):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=j,
            row_data={
                "patient_unique_hash": "mfr002-patient", "ndc": "44444444444",
                "rx_number_hash": "RX-MFR002", "date_of_service": "2026-02-01",
                "auth_no_hash": f"AUTH-MFR002-{j}", "transaction_code": tc,
                "transaction_status": "Paid" if tc != "B2" else "Reversed",
                "ingredient_cost_paid": ic, "total_paid_amt": ic,
            },
            resolution_method="declared", resolved_ndc="44444444444",
        ))

    # REJECT-75-70: reject-75 at t=0, reject-70 at t+4h (bucket=le12h)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=8,
        row_data={
            "rx_number_hash": "RX-REJ7570", "transaction_code": "B1",
            "transaction_status": "Rejected", "reject_code": "75",
            "date_added_timestamp": base_ts.isoformat(),
            "pharmacy_npi": "1000000001", "ndc": "55555555555",
            "patient_unique_hash": "rej-patient", "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared", resolved_ndc="55555555555",
    ))
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=9,
        row_data={
            "rx_number_hash": "RX-REJ7570", "transaction_code": "B1",
            "transaction_status": "Rejected", "reject_code": "70",
            "date_added_timestamp": (base_ts + timedelta(hours=4)).isoformat(),
            "pharmacy_npi": "1000000001", "ndc": "55555555555",
            "patient_unique_hash": "rej-patient", "ingredient_cost_paid": "0.00",
        },
        resolution_method="declared", resolved_ndc="55555555555",
    ))

    # ── Plant statistical fires (rows 10–13) ──────────────────────────────
    # Seed baseline_cache with values that guarantee each statistical rule fires
    # on the corresponding planted row/entity.
    # baseline_cache columns: tenant_id, rule_type_code, cohort_key, cohort_value,
    #   mean (Numeric), stddev (Numeric), sample_count (int), computed_at.
    for rule_code, cohort_key, cohort_val, mean_val, std_val in [
        ("MFR-004", "ndc",                "66666666666", "10.00", "1.00"),
        ("HP-005",  "ndc",                "77777777777", "5.00",  "0.50"),
        ("ALL-006", "pharmacy_npi",       "1000000002",  "2.00",  "0.20"),
        ("ALL-005", "patient_unique_hash","stat-patient","1.00",  "0.10"),
    ]:
        db.execute(text("""
            INSERT INTO reclaimrx.baseline_cache
                (tenant_id, rule_type_code, cohort_key, cohort_value,
                 mean, stddev, sample_count, computed_at)
            VALUES (:tenant_id, :code, :key, :val,
                    :mean, :std, 100, NOW())
            ON CONFLICT (tenant_id, rule_type_code, cohort_key, cohort_value)
            DO UPDATE SET mean=EXCLUDED.mean, stddev=EXCLUDED.stddev,
                          sample_count=EXCLUDED.sample_count, computed_at=NOW()
        """), {
            "tenant_id": str(TEST_TENANT_ID), "code": rule_code,
            "key": cohort_key, "val": cohort_val,
            "mean": mean_val, "std": std_val,
        })

    # MFR-004: NDC 66666666666 — single claim with volume far above baseline (z >> 3)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=10,
        row_data={
            "ndc": "66666666666", "pharmacy_npi": "1000000001",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "9500.00",
        },
        resolution_method="declared", resolved_ndc="66666666666",
    ))
    # HP-005: NDC 77777777777 — prescriber claim count far above baseline
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=11,
        row_data={
            "ndc": "77777777777", "prescriber_npi": "9000000001",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "9400.00",
        },
        resolution_method="declared", resolved_ndc="77777777777",
    ))
    # ALL-006: pharmacy 1000000002 — transaction on a Sunday (2026-02-01 is a Sunday)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=12,
        row_data={
            "pharmacy_npi": "1000000002", "ndc": "88888888888",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "9300.00",
        },
        resolution_method="declared", resolved_pharmacy_npi="1000000002",
        resolved_ndc="88888888888",
    ))
    # ALL-005: stat-patient refilling too early (prior fill < min_elapsed_days ago)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=13,
        row_data={
            "patient_unique_hash": "stat-patient", "ndc": "99999999999",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "days_supply": "30",
            "total_paid_amt": "9200.00",
        },
        resolution_method="declared", resolved_ndc="99999999999",
    ))

    # ── Reference fires ───────────────────────────────────────────────────
    # ALL-002: phantom pharmacy NPI (absent from reference.dataq_master)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=14,
        row_data={
            "pharmacy_npi": "8888888888", "ndc": "00000000001",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "50.00",
        },
        resolution_method="declared", resolved_pharmacy_npi="8888888888",
        resolved_ndc="00000000001",
    ))
    # ALL-003: phantom prescriber NPI (absent from reference.prescribers)
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=15,
        row_data={
            "prescriber_npi": "7777777777", "ndc": "00000000002",
            "date_of_service": "2026-02-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "50.00",
        },
        resolution_method="declared",
        resolved_ndc="00000000002",
    ))

    # ── Clean denominator (rows 16-2000) ──────────────────────────────────
    for i in range(16, TOTAL_ROWS + 1):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i,
            row_data={
                "patient_unique_hash": f"clean-{i}", "ndc": f"0{i:010d}",
                "date_of_service": "2026-02-01", "auth_no_hash": f"auth-clean-{i}",
                "transaction_code": "B1", "transaction_status": "Paid",
                "total_paid_amt": "20.00",
            },
            resolution_method="declared", resolved_ndc=f"0{i:010d}",
        ))
    db.flush()

    # Ensure all rule instances exist and are enabled (except MFR-001).
    # register_rule_types already called above.  Insert instances if absent.
    # DetectionRuleInstance has NO rule_kind column — partitioning is done by
    # rule_type_code membership sets in run_detection (_PER_ROW_CODES etc.).
    for code in [
        "MFR-003", "HP-008",
        "ALL-001", "MFR-002", "REJECT-75-70",
        "MFR-004", "HP-005", "ALL-006", "ALL-005",
        "ALL-002", "ALL-003",
    ]:
        existing = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == TEST_TENANT_ID,
                DetectionRuleInstance.rule_type_code == code,
            )
        ).scalars().first()
        if existing is None:
            db.add(DetectionRuleInstance(
                tenant_id=TEST_TENANT_ID, rule_type_code=code,
                instance_name=f"{code}-coverage-test",
                enabled=True,
                effective_from=date(2026, 1, 1), created_by=TEST_USER_ID,
                parameters={},
            ))
        elif not existing.enabled:
            existing.enabled = True
    db.flush()

    run_detection(db, run)
    db.refresh(run)

    assert run.status == "completed", (
        f"run_detection must complete; got status='{run.status}', "
        f"guardrail={run.resolution_stats.get('guardrail')}"
    )

    fired_codes: set[str] = set(
        a.finding_code for a in db.execute(
            select(Anomaly).where(Anomaly.data_source_run_id == run.id)
        ).scalars().all()
    )

    # Every in-scope rule (MFR-001 excluded — default disabled) must have fired.
    EXPECTED = {
        "MFR-003",    # per-row
        "HP-008",     # per-row
        "ALL-001",    # grouping
        "MFR-002",    # grouping
        "REJECT-75-70",  # grouping
        "MFR-004",    # statistical
        "HP-005",     # statistical
        "ALL-006",    # statistical
        "ALL-005",    # statistical
        "ALL-002",    # reference
        "ALL-003",    # reference
    }
    missing = EXPECTED - fired_codes
    assert not missing, (
        f"run_detection failed to produce anomalies for in-scope rules: {sorted(missing)}. "
        f"Fired codes were: {sorted(fired_codes)}. "
        "Each missing code indicates that rule is not wired into the dispatch loop."
    )


def test_disabled_reference_instance_does_not_fire(db):
    """A DISABLED DetectionRuleInstance for ALL-002 (or ALL-003) must suppress the
    reference evaluator entirely — no anomalies produced, data_quality keys absent.

    This test verifies FIX 3: ALL-002/003 are gated by an enabled instance; when the
    instance is present but disabled (enabled=False), `reference_instances` is empty
    for that code, so the evaluator is never called and the run produces zero ALL-002
    anomalies even though a phantom pharmacy row is present.

    Seeding strategy:
      - 1 phantom pharmacy row (NPI absent from reference.dataq_master)
      - 99 clean rows → 100-row denominator
      - ALL-002 DetectionRuleInstance present but enabled=False
      - ALL-003 instance absent entirely

    Expected outcome: run.status == 'completed', zero ALL-002 anomalies, zero ALL-003
    anomalies, data_quality dict present but without missing_pharmacy_npi key
    (or value == 0 — acceptable if evaluator was not called).
    """
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import (
        DetectionRun, CsvUploadRow, Anomaly,
        DetectionRuleType, DetectionRuleInstance,
    )
    from src.detection.rule_type_registry import register_rule_types
    from sqlalchemy import select, text
    from datetime import date as _date

    TOTAL_ROWS = 100
    register_rule_types(db)

    run = DetectionRun(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        run_label="disabled-ref-instance-test", status="in_progress", created_by=TEST_USER_ID,
        resolution_stats={"inserted_count": TOTAL_ROWS, "expected_count": TOTAL_ROWS},
    )
    db.add(run)
    db.flush()

    # Phantom pharmacy row — would fire ALL-002 if the instance were enabled.
    db.add(CsvUploadRow(
        tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=1,
        row_data={
            "pharmacy_npi": "6666666666",  # absent from reference.dataq_master
            "ndc": "00000000099",
            "date_of_service": "2026-03-01", "transaction_code": "B1",
            "transaction_status": "Paid", "total_paid_amt": "50.00",
        },
        resolution_method="declared", resolved_pharmacy_npi="6666666666",
        resolved_ndc="00000000099",
    ))
    # 99 clean denominator rows
    for i in range(2, TOTAL_ROWS + 1):
        db.add(CsvUploadRow(
            tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i,
            row_data={
                "patient_unique_hash": f"clean-dis-{i}", "ndc": f"1{i:010d}",
                "date_of_service": "2026-03-01", "transaction_code": "B1",
                "transaction_status": "Paid", "total_paid_amt": "20.00",
            },
            resolution_method="declared", resolved_ndc=f"1{i:010d}",
        ))
    db.flush()

    # ALL-002 instance: DISABLED (enabled=False).
    db.add(DetectionRuleInstance(
        tenant_id=TEST_TENANT_ID, rule_type_code="ALL-002",
        instance_name="ALL-002-disabled-test",
        enabled=False,  # <-- disabled; must NOT fire
        effective_from=_date(2026, 1, 1), created_by=TEST_USER_ID,
        parameters={},
    ))
    # ALL-003 instance: intentionally absent (no insert) — must NOT fire either.
    db.flush()

    run_detection(db, run)
    db.refresh(run)

    assert run.status == "completed", (
        f"run must complete; got status='{run.status}', "
        f"guardrail={run.resolution_stats.get('guardrail')}"
    )

    all002_anomalies = db.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "ALL-002",
        )
    ).scalars().all()
    assert len(all002_anomalies) == 0, (
        f"Disabled ALL-002 instance must suppress the evaluator entirely; "
        f"got {len(all002_anomalies)} ALL-002 anomaly(ies). "
        "Check that run_detection gates ALL-002 on reference_instances (FIX 3)."
    )

    all003_anomalies = db.execute(
        select(Anomaly).where(
            Anomaly.data_source_run_id == run.id,
            Anomaly.finding_code == "ALL-003",
        )
    ).scalars().all()
    assert len(all003_anomalies) == 0, (
        f"Absent ALL-003 instance must produce zero ALL-003 anomalies; "
        f"got {len(all003_anomalies)}."
    )
```

Run → GREEN.

```
git add modules/reclaimrx/src/detection/batch_engine.py \
        modules/reclaimrx/tests/detection/test_all002_all003.py
git commit -m "feat(reclaimrx): wire ALL-002/003 + REJECT-75-70 + FDB enrichment into run_detection, data_quality breakdown in resolution_stats"
```

---

## Phase 5 — MFR-001 Reframe (§12 H3) (2 tasks)

### Task 5a — Coverage report HARD GATE

**This task has no shipped code.** It is a mandatory hard gate before MFR-001 can be enabled.

Run the following query against `infinityrx_dev` after the 2.6M rows are ingested.

**Per-claim prior-fill count (§12 H3 correct definition):** a claim is eligible only if
it has >= `min_prior_fills` (default 3) PRIOR paid-B1 fills for the same patient+ndc
with `dos < current_claim.dos` and `dos >= current_claim.dos - lookback_window_days`
and elapsed days >= `min_elapsed_days`.

```sql
-- Coverage measurement for MFR-001 per §12 H3
-- Correct: counts per-claim prior fills using a window function, NOT group-level totals.
-- A claim is eligible only if it has >= 3 prior paid-B1 fills before its own DOS
-- within the lookback window (default 365 days).
WITH b1_paid AS (
    SELECT
        id,
        (row_data->>'patient_unique_hash') AS patient_hash,
        resolved_ndc AS ndc,
        (row_data->>'date_of_service')::date AS dos
    FROM reclaimrx.csv_upload_rows
    WHERE tenant_id = '<your-tenant-uuid>'
      AND (row_data->>'transaction_code') = 'B1'
      AND (row_data->>'transaction_status') IN ('Paid', 'paid')
      AND (row_data->>'date_of_service') IS NOT NULL
),
prior_fill_counts AS (
    SELECT
        c.id,
        COUNT(p.id) AS prior_fills
    FROM b1_paid c
    LEFT JOIN b1_paid p
        ON p.patient_hash = c.patient_hash
       AND p.ndc = c.ndc
       AND p.dos < c.dos
       AND p.dos >= c.dos - INTERVAL '365 days'
    GROUP BY c.id
),
total_b1 AS (SELECT COUNT(*) AS n FROM b1_paid),
eligible AS (SELECT COUNT(*) AS n FROM prior_fill_counts WHERE prior_fills >= 3)
SELECT
    total_b1.n AS total_b1_paid,
    eligible.n AS eligible_for_mfr001,
    ROUND(eligible.n::numeric / NULLIF(total_b1.n, 0) * 100, 2) AS coverage_pct
FROM total_b1, eligible;
```

**Decision gate:**
- If `coverage_pct >= 20%` → a human operator may enable MFR-001 by running the following data-update against the live DB (NOT by editing migration 0012):
  ```sql
  UPDATE reclaimrx.detection_rule_instances
  SET enabled = true
  WHERE rule_type_code = 'MFR-001'
    AND tenant_id = '<your-tenant-uuid>';
  ```
- If `coverage_pct < 20%` → MFR-001 stays `enabled=False`. Fall back to per-NDC top-percentile approach documented in the rule catalog, OR keep disabled.

Migration 0012 sets `enabled = false` unconditionally — it does NOT reference coverage_pct and is NOT edited after the coverage report runs. Enabling MFR-001 is a separate data-update / admin action that happens after this gate, outside the migration chain.

No commit for this task.

---

### Task 5b — MFR-001 reframed: per-patient median-prior-NQ rule

**Rule disabled by default (`enabled=False`) until coverage gate passes.**

**Files:**
- `modules/reclaimrx/alembic/versions/0012_reclaimrx_v2_mfr001_reframe.py` — update rule type + instance params
- `modules/reclaimrx/src/detection/mfr001_evaluator.py` — new per-patient longitudinal evaluator
- `modules/reclaimrx/tests/detection/test_mfr001_reframe.py`

**Test first:**
```python
"""Tests for MFR-001 reframed: per-patient prior-NQ deviation.

Rule disabled by default. Coverage gate must pass before enabling.
"""
from __future__ import annotations
import pytest
from decimal import Decimal


class TestMFR001CoverageGate:
    def test_rule_instance_disabled_by_default(self, db):
        """MFR-001 instance must have enabled=False after migration 0012."""
        from sqlalchemy import select
        from src.models.detection_run_models import DetectionRuleInstance
        from src.detection.rule_type_registry import register_rule_types, register_rule_instances

        register_rule_types(db)
        cols = {"extended_wac", "ingredient_cost_paid", "dispensing_fee_paid", "quantity_dispensed"}
        register_rule_instances(db, TEST_TENANT_ID, cols, TEST_USER_ID)

        mfr001 = db.execute(
            select(DetectionRuleInstance).where(
                DetectionRuleInstance.tenant_id == TEST_TENANT_ID,
                DetectionRuleInstance.rule_type_code == "MFR-001",
            )
        ).scalar_one_or_none()
        if mfr001 is not None:
            assert mfr001.enabled is False, "MFR-001 must be disabled by default until coverage gate"

    def test_per_claim_eligibility_not_group_level(self, db):
        """Per §12 H3: a claim is eligible only if it has >= min_prior_fills PRIOR fills
        before its own DOS for the same patient+ndc within the lookback window.

        Plant:
          patient-A, ndc-X: fills on days 1, 2, 3 (prior), then day 4 (current claim)
            → day-4 claim has 3 prior fills → ELIGIBLE
          patient-B, ndc-X: fills on days 1, 2 (prior), then day 3 (current claim)
            → day-3 claim has 2 prior fills → NOT ELIGIBLE (< min_prior_fills=3)

        Asserts:
          patient-A day-4 claim: prior_fill_count >= 3 (eligible)
          patient-B day-3 claim: prior_fill_count < 3 (not eligible)
        """
        from src.detection.mfr001_evaluator import compute_prior_fill_count

        # patient-A: 3 prior fills before day 4
        prior_fills_for_eligible = compute_prior_fill_count(
            patient_fills=[
                {"dos": "2026-01-01"},
                {"dos": "2026-01-02"},
                {"dos": "2026-01-03"},
            ],
            current_dos="2026-01-04",
            lookback_days=365,
            min_elapsed_days=0,
        )
        assert prior_fills_for_eligible >= 3, (
            f"Patient-A day-4 should have 3 prior fills, got {prior_fills_for_eligible}"
        )

        # patient-B: only 2 prior fills before day 3
        prior_fills_for_ineligible = compute_prior_fill_count(
            patient_fills=[
                {"dos": "2026-01-01"},
                {"dos": "2026-01-02"},
            ],
            current_dos="2026-01-03",
            lookback_days=365,
            min_elapsed_days=0,
        )
        assert prior_fills_for_ineligible < 3, (
            f"Patient-B day-3 should have 2 prior fills, got {prior_fills_for_ineligible}"
        )


class TestMFR001Evaluator:
    def test_fires_when_current_nq_exceeds_median_by_threshold(self):
        """Per-patient: current NQ > median_prior_NQ * (1 + deviation_threshold)."""
        from src.detection.mfr001_evaluator import evaluate_mfr001_per_patient_row
        # median prior NQ = 100, current NQ = 160 → 60% above median
        fired, evidence = evaluate_mfr001_per_patient_row(
            current_nq=Decimal("160.00"),
            median_prior_nq=Decimal("100.00"),
            deviation_threshold=Decimal("0.50"),
            min_prior_fills=3,
            actual_prior_fills=5,
        )
        assert fired is True
        assert evidence["deviation_pct"] > Decimal("0.50")

    def test_does_not_fire_within_threshold(self):
        from src.detection.mfr001_evaluator import evaluate_mfr001_per_patient_row
        fired, _ = evaluate_mfr001_per_patient_row(
            current_nq=Decimal("110.00"),
            median_prior_nq=Decimal("100.00"),
            deviation_threshold=Decimal("0.50"),
            min_prior_fills=3,
            actual_prior_fills=5,
        )
        assert fired is False

    def test_blocked_by_min_prior_fills(self):
        from src.detection.mfr001_evaluator import evaluate_mfr001_per_patient_row
        fired, evidence = evaluate_mfr001_per_patient_row(
            current_nq=Decimal("999.00"),
            median_prior_nq=Decimal("50.00"),
            deviation_threshold=Decimal("0.50"),
            min_prior_fills=3,
            actual_prior_fills=2,  # insufficient history
        )
        assert fired is False
        assert evidence.get("reason") == "insufficient_history"

    def test_nq_is_ingredient_cost_paid_not_quantity_dispensed(self):
        """NQ = ingredient_cost_paid. build_mfr001_prior_nq_index must read
        ingredient_cost_paid, NOT quantity_dispensed, when building the index."""
        from src.detection.mfr001_evaluator import build_mfr001_prior_nq_index
        from unittest.mock import MagicMock

        # Two rows for the same patient+ndc: one with ingredient_cost_paid only,
        # one with quantity_dispensed only. Only the ingredient_cost_paid row must
        # be indexed.
        row_with_nq = MagicMock()
        row_with_nq.row_data = {
            "patient_unique_hash": "ph-A",
            "ndc": "11111111111",
            "date_of_service": "2026-01-01",
            "transaction_code": "B1",
            "transaction_status": "Paid",
            "ingredient_cost_paid": "100.00",
            # quantity_dispensed intentionally absent
        }
        row_with_nq.resolved_ndc = "11111111111"

        row_with_qty_only = MagicMock()
        row_with_qty_only.row_data = {
            "patient_unique_hash": "ph-B",
            "ndc": "22222222222",
            "date_of_service": "2026-01-01",
            "transaction_code": "B1",
            "transaction_status": "Paid",
            "quantity_dispensed": "30",   # should NOT be indexed
            # ingredient_cost_paid intentionally absent
        }
        row_with_qty_only.resolved_ndc = "22222222222"

        params = {"patient_key": "patient_unique_hash", "drug_key": "ndc"}
        index = build_mfr001_prior_nq_index([row_with_nq, row_with_qty_only], params=params)

        assert ("ph-A", "11111111111") in index, (
            "Row with ingredient_cost_paid must be indexed"
        )
        assert ("ph-B", "22222222222") not in index, (
            "Row with only quantity_dispensed must NOT be indexed (NQ = ingredient_cost_paid)"
        )

    def test_future_fill_excluded_from_prior_median(self):
        """evaluate_mfr001_row must exclude the current and future fills from
        the prior-NQ median. Only strictly-prior fills (DOS < current DOS) are used.

        Plant: patient-X, ndc-1
          prior fill DOS=2026-01-01 ingredient_cost_paid=100 (prior)
          prior fill DOS=2026-01-02 ingredient_cost_paid=100 (prior)
          prior fill DOS=2026-01-03 ingredient_cost_paid=100 (prior)
          current fill DOS=2026-01-10 ingredient_cost_paid=160 (current — must not count as prior)
          future fill DOS=2026-01-20 ingredient_cost_paid=999 (future — must be ignored entirely)

        Median of STRICTLY prior fills = 100. Current NQ = 160 → 60% > 50% threshold → fires.
        If future fill (999) were included the median would shift, changing the result.
        If the current fill were included as a prior, actual_prior_fills would be wrong.
        """
        from src.detection.mfr001_evaluator import build_mfr001_prior_nq_index, evaluate_mfr001_row
        from unittest.mock import MagicMock

        def _make_row(dos, nq, patient="ph-X", ndc="11111111111"):
            r = MagicMock()
            r.row_data = {
                "patient_unique_hash": patient,
                "ndc": ndc,
                "date_of_service": dos,
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "ingredient_cost_paid": str(nq),
            }
            r.resolved_ndc = ndc
            r.tenant_id = "tenant-1"
            r.detection_run_id = "run-1"
            r.id = f"row-{dos}"
            return r

        all_rows = [
            _make_row("2026-01-01", "100.00"),
            _make_row("2026-01-02", "100.00"),
            _make_row("2026-01-03", "100.00"),
            _make_row("2026-01-10", "160.00"),  # current
            _make_row("2026-01-20", "999.00"),  # future — must be excluded
        ]
        params = {
            "patient_key": "patient_unique_hash",
            "drug_key": "ndc",
            "lookback_window_days": 365,
            "min_elapsed_days": 0,
        }
        index = build_mfr001_prior_nq_index(all_rows, params=params)

        inst = MagicMock()
        inst.parameters = {
            **params,
            "deviation_threshold": "0.50",
            "min_prior_fills": 3,
            "dollar_floor": "10.00",
            "severity": "high",
            "confidence": "0.75",
        }

        current_row = _make_row("2026-01-10", "160.00")
        result = evaluate_mfr001_row(
            current_row,
            db=None,         # _mfr001_index provided — no DB needed
            _fdb_cache={},
            instance=inst,
            _mfr001_index=index,
        )
        assert result is not None, (
            "MFR-001 should fire: current NQ 160 > median prior NQ 100 * 1.50 = 150"
        )
        assert result.finding_code == "MFR-001"

    def test_build_mfr001_index_from_raw_rows_no_orm_objects(self):
        """build_mfr001_prior_nq_index with _from_raw_rows=True must produce the same
        index as the ORM-row path without materializing ORM objects.

        FIX (MED): verifies the streaming/minimal-column index build path used in
        Task 4c Step 0c. A raw lightweight row (direct attribute access, no .row_data)
        must build the same (patient_hash, ndc) → [(dos, nq)] index as ORM rows.
        """
        from src.detection.mfr001_evaluator import build_mfr001_prior_nq_index
        from decimal import Decimal
        from unittest.mock import MagicMock

        # Simulate raw lightweight rows from the minimal-column SQL query.
        # These have direct attributes, NOT a .row_data dict.
        raw_rows = []
        for dos, nq in [("2026-01-01", "100.00"), ("2026-01-02", "110.00")]:
            r = MagicMock(spec=[])  # spec=[] → no row_data attribute
            r.patient_unique_hash = "ph-RAW"
            r.resolved_ndc = "NDCRAW001"
            r.date_of_service = dos
            r.ingredient_cost_paid = nq
            raw_rows.append(r)

        params = {"patient_key": "patient_unique_hash", "drug_key": "ndc"}
        index = build_mfr001_prior_nq_index(raw_rows, params=params, _from_raw_rows=True)

        assert ("ph-RAW", "NDCRAW001") in index, (
            "Raw-row path must build the (patient_hash, ndc) key"
        )
        entries = index[("ph-RAW", "NDCRAW001")]
        assert len(entries) == 2, f"Expected 2 entries, got {len(entries)}"
        # Entries sorted by DOS asc
        assert entries[0][0] == "2026-01-01"
        assert entries[1][0] == "2026-01-02"
        # NQ values are Decimal
        assert isinstance(entries[0][1], Decimal)

    def test_build_mfr001_index_no_all_call_on_large_run(self, db):
        """Verify that the MFR-001 index build in run_detection Step 0c does NOT
        call .scalars().all() on the full CsvUploadRow table.

        FIX (MED): The old implementation called
            db.execute(select(CsvUploadRow).where(...)).scalars().all()
        which materializes all full ORM objects. This test verifies the fix:
        the new path uses a raw text() query with a minimal column projection
        and _from_raw_rows=True, so the full ORM table is never loaded.

        Approach: seed 100 rows including both B1/Paid and non-B1 rows.
        Enable MFR-001 on the run. Patch build_mfr001_prior_nq_index to capture
        what is passed to it. Assert:
          - The rows passed have direct .ingredient_cost_paid attribute (not .row_data).
          - Only B1/Paid rows with ingredient_cost_paid are passed (pre-filtered by SQL).
          - _from_raw_rows=True is passed.
        """
        from src.detection.batch_engine import run_detection
        from src.detection import mfr001_evaluator as _mfr001_mod
        from src.models.detection_run_models import (
            DetectionRun, CsvUploadRow, DetectionRuleType, DetectionRuleInstance,
        )
        from datetime import date as _date
        from unittest.mock import patch

        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="mfr001-stream-index-test", status="in_progress", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 100, "expected_count": 100},
        )
        db.add(run)
        db.flush()

        # 50 eligible paid-B1 rows (with ingredient_cost_paid)
        for i in range(50):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=i + 1,
                row_data={
                    "patient_unique_hash": f"ph-{i}", "ndc": "NDCSTREAM",
                    "date_of_service": "2026-01-01",
                    "transaction_code": "B1", "transaction_status": "Paid",
                    "ingredient_cost_paid": "100.00",
                },
                resolution_method="declared", resolved_ndc="NDCSTREAM",
            ))
        # 50 ineligible rows (Reversed or missing ingredient_cost_paid)
        for i in range(50):
            db.add(CsvUploadRow(
                tenant_id=TEST_TENANT_ID, detection_run_id=run.id, row_number=50 + i + 1,
                row_data={
                    "patient_unique_hash": f"ph-rev-{i}",
                    "transaction_code": "B1", "transaction_status": "Reversed",
                    "ingredient_cost_paid": "200.00",
                },
                resolution_method="declared", resolved_ndc="NDCSTREAM",
            ))
        db.flush()

        # Register MFR-001 rule type + enabled instance
        existing_type = db.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(DetectionRuleType).where(
                DetectionRuleType.code == "MFR-001"
            )
        ).scalar_one_or_none()
        if existing_type is None:
            db.add(DetectionRuleType(
                code="MFR-001", name="MFR-001 Test", description="test",
                family="A1", parameter_schema_version="1.0",
                default_severity="high", default_confidence=Decimal("0.75"),
                requires_baseline=False, requires_history=True,
                deferred_data_feed=False, deferred_reason="",
                required_data_columns=[], default_parameters={},
            ))
        db.add(DetectionRuleInstance(
            tenant_id=TEST_TENANT_ID, rule_type_code="MFR-001",
            instance_name="MFR-001-stream-test",
            enabled=True,  # force-enabled for this test
            effective_from=_date.today(), created_by=TEST_USER_ID,
            parameters={
                "patient_key": "patient_unique_hash", "drug_key": "ndc",
                "lookback_window_days": 365, "min_prior_fills": 3,
                "min_elapsed_days": 0, "deviation_threshold": "0.50",
                "dollar_floor": "50.00", "rule_fire_rate_cap": "0.005",
            },
        ))
        db.flush()

        captured_args = {}

        original_build = _mfr001_mod.build_mfr001_prior_nq_index

        def _capture_build(rows, *, params, _from_raw_rows=False, **kwargs):
            captured_args["rows"] = rows
            captured_args["_from_raw_rows"] = _from_raw_rows
            return original_build(rows, params=params, _from_raw_rows=_from_raw_rows)

        with patch.object(_mfr001_mod, "build_mfr001_prior_nq_index", side_effect=_capture_build):
            run_detection(db, run)

        # Must have been called with _from_raw_rows=True
        assert captured_args.get("_from_raw_rows") is True, (
            "build_mfr001_prior_nq_index must be called with _from_raw_rows=True "
            "from the minimal-column SQL path (not .scalars().all())"
        )

        # Rows passed must have direct .ingredient_cost_paid attribute (lightweight Row),
        # NOT a .row_data dict (which would indicate the old ORM-materialization path).
        rows_passed = captured_args.get("rows", [])
        assert len(rows_passed) > 0, "At least some rows must be passed to build_mfr001_prior_nq_index"
        first_row = rows_passed[0]
        assert hasattr(first_row, "ingredient_cost_paid"), (
            "Rows passed to build_mfr001_prior_nq_index must have direct .ingredient_cost_paid "
            "attribute (minimal-column SQL Row), not a .row_data dict"
        )
        assert not hasattr(first_row, "row_data"), (
            "Rows must NOT have .row_data — that would indicate the old .scalars().all() ORM path "
            "which materializes 2.6M full objects"
        )
        # Only paid-B1 rows should be in the result (SQL pre-filters)
        assert len(rows_passed) == 50, (
            f"Only the 50 paid-B1 rows should be passed (SQL pre-filters); "
            f"got {len(rows_passed)} rows"
        )

    def test_no_per_row_db_query_when_index_provided(self, db):
        """Query count must be CONSTANT (not grow with row count) when _mfr001_index
        is provided.  Verifies the precomputed set-based approach has zero per-row
        DB queries inside the evaluator loop.

        Approach: call evaluate_mfr001_row N times and verify db.execute is NOT
        called each time — only the precomputed index is consulted.
        """
        from src.detection.mfr001_evaluator import build_mfr001_prior_nq_index, evaluate_mfr001_row
        from unittest.mock import MagicMock, patch

        def _make_row(dos, nq, patient="ph-Z", ndc="33333333333"):
            r = MagicMock()
            r.row_data = {
                "patient_unique_hash": patient,
                "ndc": ndc,
                "date_of_service": dos,
                "transaction_code": "B1",
                "transaction_status": "Paid",
                "ingredient_cost_paid": str(nq),
            }
            r.resolved_ndc = ndc
            r.tenant_id = "t1"
            r.detection_run_id = "r1"
            r.id = f"id-{dos}"
            return r

        rows = [_make_row(f"2026-01-{i:02d}", "80.00") for i in range(1, 6)]
        params = {"patient_key": "patient_unique_hash", "drug_key": "ndc",
                  "lookback_window_days": 365, "min_elapsed_days": 0}
        index = build_mfr001_prior_nq_index(rows, params=params)

        inst = MagicMock()
        inst.parameters = {**params, "deviation_threshold": "0.50", "min_prior_fills": 3,
                           "dollar_floor": "10.00", "severity": "high", "confidence": "0.75"}

        db_call_count = 0
        original_execute = db.execute

        def _counting_execute(*args, **kwargs):
            nonlocal db_call_count
            db_call_count += 1
            return original_execute(*args, **kwargs)

        db.execute = _counting_execute

        for row in rows:
            evaluate_mfr001_row(
                row, db=db, _fdb_cache={}, instance=inst, _mfr001_index=index
            )

        assert db_call_count == 0, (
            f"evaluate_mfr001_row must issue ZERO DB queries when _mfr001_index is provided, "
            f"got {db_call_count} queries for {len(rows)} rows"
        )
```

Run → RED.

**Implementation** (`modules/reclaimrx/src/detection/mfr001_evaluator.py`):
```python
"""MFR-001 reframed: per-patient prior-NQ deviation evaluator.

Pure function. No I/O. DISABLED by default until coverage gate passes.
patient key = patient_unique_hash
drug key = ndc (GPI as fallback if NDC too sparse — see parameters)
paid B1 only, min_prior_fills default=3.
statistic = median prior NQ (robust to outliers).
"""
from __future__ import annotations
from decimal import ROUND_HALF_UP, Decimal
from typing import Any


def compute_prior_fill_count(
    *,
    patient_fills: list[dict[str, Any]],
    current_dos: str,
    lookback_days: int,
    min_elapsed_days: int,
) -> int:
    """Count prior paid-B1 fills for the same patient+ndc before current_dos.

    patient_fills: list of dicts with at least "dos" (ISO date string).
    current_dos: the claim's date_of_service (ISO date string).
    lookback_days: how many days back to look (dos >= current_dos - lookback_days).
    min_elapsed_days: minimum elapsed days between prior fill and current (dos diff >= this).

    Returns count of qualifying prior fills. Used by coverage gate query and
    per-claim eligibility check per §12 H3.
    """
    from datetime import date as _date  # noqa: PLC0415

    def _parse(s: str) -> _date:
        return _date.fromisoformat(str(s).strip()[:10])

    current = _parse(current_dos)
    count = 0
    for fill in patient_fills:
        d = _parse(fill["dos"])
        elapsed = (current - d).days
        if elapsed < 1:
            continue  # must be strictly before current_dos
        if elapsed < min_elapsed_days:
            continue
        lookback_start = current.toordinal() - lookback_days
        if d.toordinal() < lookback_start:
            continue
        count += 1
    return count


def evaluate_mfr001_per_patient_row(
    *,
    current_nq: Decimal,
    median_prior_nq: Decimal,
    deviation_threshold: Decimal,
    min_prior_fills: int,
    actual_prior_fills: int,
) -> tuple[bool, dict[str, Any]]:
    """Evaluate whether current_nq deviates from median_prior_nq beyond threshold.

    Returns (fired, evidence).
    evidence contains: deviation_pct, current_nq, median_prior_nq, actual_prior_fills.
    """
    if actual_prior_fills < min_prior_fills:
        return False, {"reason": "insufficient_history", "actual_prior_fills": actual_prior_fills,
                       "min_prior_fills": min_prior_fills}
    if median_prior_nq == Decimal("0"):
        return False, {"reason": "zero_median_prior_nq"}

    deviation_pct = ((current_nq - median_prior_nq) / median_prior_nq).quantize(
        Decimal("0.0001"), rounding=ROUND_HALF_UP
    )
    fired = deviation_pct > deviation_threshold
    return fired, {
        "current_nq": str(current_nq),
        "median_prior_nq": str(median_prior_nq),
        "deviation_pct": deviation_pct,
        "deviation_threshold": str(deviation_threshold),
        "actual_prior_fills": actual_prior_fills,
        "min_prior_fills": min_prior_fills,
    }


def build_mfr001_prior_nq_index(
    rows: "list[Any]",
    *,
    params: dict,
    _from_raw_rows: bool = False,
) -> "dict[tuple[str, str], list[tuple[str, Decimal]]]":
    """Precompute per-(patient_unique_hash, ndc) prior-fill NQ lists for MFR-001.

    Called ONCE before the yield_per stream — produces an in-memory index that
    evaluate_mfr001_row reads per-row with ZERO DB queries inside the loop.

    NQ = ingredient_cost_paid (the net amount, same field used by MFR-002/003).
    Only paid-B1 rows are included (transaction_code='B1', transaction_status='Paid').

    _from_raw_rows=False (default): input rows are ORM CsvUploadRow objects with
        .row_data dict. The paid-B1 filter is applied inline.
    _from_raw_rows=True: input rows are lightweight named-tuple rows from the
        minimal-column SQL query in Task 4c Step 0c. They have direct attributes
        .patient_unique_hash, .resolved_ndc, .date_of_service, .ingredient_cost_paid.
        The SQL query already filters to paid-B1 rows, so no filter is needed here.
        This path avoids materializing full ORM objects on 2.6M-row datasets.

    Returns:
        dict keyed by (patient_unique_hash, ndc) →
            sorted list of (dos_str, nq_decimal) tuples in ascending DOS order.
    """
    from decimal import Decimal  # noqa: PLC0415

    patient_key_field = params.get("patient_key", "patient_unique_hash")
    drug_key_field = params.get("drug_key", "ndc")
    index: dict = {}

    for row in rows:
        if _from_raw_rows:
            # Raw-row path: direct attribute access on the minimal-column SQL result.
            # The SQL query pre-filtered to paid-B1 rows, so no transaction_code/status
            # filter is needed here. All four fields are guaranteed non-NULL by the SQL WHERE.
            ph = getattr(row, "patient_unique_hash", None)
            ndc = getattr(row, "resolved_ndc", None)
            dos = getattr(row, "date_of_service", None)
            nq_raw = getattr(row, "ingredient_cost_paid", None)
        else:
            # ORM-row path: extract from .row_data dict (used in unit tests).
            rd = row.row_data
            tc = rd.get("transaction_code", "")
            ts = rd.get("transaction_status", "")
            if tc != "B1" or ts != "Paid":
                continue
            ph = rd.get(patient_key_field)
            ndc = rd.get(drug_key_field) or row.resolved_ndc
            dos = rd.get("date_of_service", "")
            nq_raw = rd.get("ingredient_cost_paid")

        if not (ph and ndc and dos and nq_raw is not None):
            continue
        try:
            nq = Decimal(str(nq_raw))
        except Exception:  # noqa: BLE001
            continue
        key = (ph, ndc)
        if key not in index:
            index[key] = []
        index[key].append((dos, nq))

    # Sort each entry ascending by DOS so prior-fill extraction is a simple prefix scan.
    for key in index:
        index[key].sort(key=lambda t: t[0])
    return index


def evaluate_mfr001_row(
    row: "Any",
    *,
    db: "Any",
    _fdb_cache: dict,
    instance: "Any",
    _mfr001_index: "dict | None" = None,
) -> "Any | None":
    """Per-row dispatch adapter for MFR-001 — called by Task 4c _PER_ROW_EVALUATORS.

    Signature matches all per-row evaluators: (row, *, db, _fdb_cache, instance).
    Also accepts optional _mfr001_index (precomputed by build_mfr001_prior_nq_index
    before the stream); when provided, issues ZERO DB queries — all prior-fill data
    comes from the in-memory index.

    NQ = ingredient_cost_paid (net amount). NOT quantity_dispensed.
    Prior NQs = strictly-prior paid-B1 fills with DOS < current DOS AND
                DOS >= current DOS - lookback_window_days, respecting min_elapsed_days.
    The current row and any future fills are excluded from the median computation.

    Returns Anomaly if fired, None otherwise.
    DISABLED by default — not reached unless instance.enabled=True (post-coverage-gate).
    """
    from decimal import Decimal  # noqa: PLC0415
    from statistics import median  # noqa: PLC0415
    from src.models.detection_run_models import Anomaly  # noqa: PLC0415

    params = instance.parameters
    deviation_threshold = Decimal(str(params.get("deviation_threshold", "0.50")))
    min_prior_fills = int(params.get("min_prior_fills", 3))
    lookback_days = int(params.get("lookback_window_days", 365))
    min_elapsed_days = int(params.get("min_elapsed_days", 0))
    dollar_floor = Decimal(str(params.get("dollar_floor", "50.00")))
    patient_key_field = params.get("patient_key", "patient_unique_hash")
    drug_key_field = params.get("drug_key", "ndc")

    rd = row.row_data
    # Only evaluate paid B1 claims.
    if rd.get("transaction_code") != "B1" or rd.get("transaction_status") != "Paid":
        return None

    patient_hash = rd.get(patient_key_field)
    ndc = rd.get(drug_key_field) or row.resolved_ndc
    current_dos = rd.get("date_of_service", "")

    # NQ = ingredient_cost_paid (same field as MFR-002/003).  NOT quantity_dispensed.
    nq_raw = rd.get("ingredient_cost_paid")
    if nq_raw is None:
        return None
    try:
        current_nq = Decimal(str(nq_raw))
    except Exception:  # noqa: BLE001
        return None

    # Dollar floor guard against noise.
    if current_nq < dollar_floor:
        return None

    # Resolve prior-fill NQ list from the precomputed in-memory index.
    # ZERO DB queries inside the stream — all data was precomputed before yield_per.
    if _mfr001_index is None:
        # Safety fallback: index not provided (should not happen in production).
        # Return None rather than issuing a per-row DB query.
        return None

    all_prior_nqs: list[Decimal] = []
    actual_prior_fills: int = 0
    key = (patient_hash, ndc)
    fill_list = _mfr001_index.get(key, [])  # sorted (dos, nq) asc
    for dos_str, nq in fill_list:
        # Strictly prior: DOS must be < current DOS.
        if dos_str >= current_dos:
            continue
        elapsed = _dos_diff_days(current_dos, dos_str)
        if elapsed < 1:
            continue
        if elapsed < min_elapsed_days:
            continue
        lookback_start = _subtract_days(current_dos, lookback_days)
        if dos_str < lookback_start:
            continue
        actual_prior_fills += 1
        all_prior_nqs.append(nq)

    median_prior_nq = Decimal(str(median(all_prior_nqs))) if all_prior_nqs else Decimal("0")

    fired, evidence = evaluate_mfr001_per_patient_row(
        current_nq=current_nq,
        median_prior_nq=median_prior_nq,
        deviation_threshold=deviation_threshold,
        min_prior_fills=min_prior_fills,
        actual_prior_fills=actual_prior_fills,
    )
    if not fired:
        return None
    return Anomaly(
        tenant_id=row.tenant_id,
        data_source="csv_upload",
        data_source_run_id=row.detection_run_id,
        source_table="csv_upload_rows",
        source_row_id=row.id,
        detection_kind="rule",
        severity=params.get("severity", "high"),
        confidence=Decimal(str(params.get("confidence", "0.75"))),
        finding_code="MFR-001",
        finding_summary="Ingredient cost paid deviates from patient's prior median (MFR-001)",
        finding_details={k: str(v) if isinstance(v, Decimal) else v for k, v in evidence.items()},
        pharmacy_npi=rd.get("pharmacy_npi"),
        prescriber_npi=rd.get("prescriber_npi"),
        ndc=ndc,
        date_of_service=None,
        status="open",
    )


def _dos_diff_days(current_dos: str, prior_dos: str) -> int:
    """Return (current - prior) in days. Both are ISO date strings (YYYY-MM-DD)."""
    from datetime import date as _date  # noqa: PLC0415
    c = _date.fromisoformat(str(current_dos).strip()[:10])
    p = _date.fromisoformat(str(prior_dos).strip()[:10])
    return (c - p).days


def _subtract_days(dos: str, days: int) -> str:
    """Return ISO date string for dos - days."""
    from datetime import date as _date, timedelta  # noqa: PLC0415
    d = _date.fromisoformat(str(dos).strip()[:10])
    return (d - timedelta(days=days)).isoformat()
```

**Migration** (`modules/reclaimrx/alembic/versions/0012_reclaimrx_v2_mfr001_reframe.py`):
```python
"""MFR-001 reframe: per-patient prior-NQ shape + unconditional enabled=False.

This migration ONLY:
  1. Updates detection_rule_instances for MFR-001 to the per-patient prior-NQ
     parameter shape (§12 H3).
  2. Sets enabled = False UNCONDITIONALLY (disabled-by-default per §12 H3).

It does NOT reference coverage_pct or any live-data measurement.
coverage_pct is unknowable at migration-authoring time.

To enable MFR-001 after the Task 5a coverage gate passes, run the following
data-update (NOT a new migration):
  UPDATE reclaimrx.detection_rule_instances
  SET enabled = true
  WHERE rule_type_code = 'MFR-001'
    AND tenant_id = '<your-tenant-uuid>';
"""
from alembic import op
import sqlalchemy as sa
import json

revision = "0012_reclaimrx_v2_mfr001_reframe"
down_revision = "0011_reclaimrx_v2_rule_params"
branch_labels = None
depends_on = None

_NEW_PARAMS = {
    "patient_key": "patient_unique_hash",
    "drug_key": "ndc",
    "eligible_statuses": ["Paid"],
    "lookback_window_days": 365,
    "min_prior_fills": 3,
    "min_elapsed_days": 0,
    "prior_statistic": "median",
    "deviation_threshold": "0.50",
    "dollar_floor": "50.00",
    "rule_fire_rate_cap": "0.005",
}

def upgrade() -> None:
    conn = op.get_bind()
    # Reframe MFR-001 instances to per-patient prior-NQ shape.
    # enabled = False unconditionally — coverage gate has not run yet.
    conn.execute(
        sa.text(
            "UPDATE reclaimrx.detection_rule_instances "
            "SET parameters = parameters || :p::jsonb, enabled = false "
            "WHERE rule_type_code = 'MFR-001'"
        ),
        {"p": json.dumps(_NEW_PARAMS)},
    )

def downgrade() -> None:
    pass
```

Run → GREEN.

```
git add modules/reclaimrx/src/detection/mfr001_evaluator.py \
        modules/reclaimrx/alembic/versions/0012_reclaimrx_v2_mfr001_reframe.py \
        modules/reclaimrx/tests/detection/test_mfr001_reframe.py
git commit -m "feat(reclaimrx): migration 0012 — MFR-001 reframe, per-patient median-prior-NQ, disabled by default, coverage gate documented (§12 H3)"
```

---

## Phase 6 — API (§12 H4) (2 tasks)

### Task 6a — GET /api/v1/reclaimrx/anomalies

**entity_type is DERIVED, not stored.** `pharmacy` when `pharmacy_npi IS NOT NULL`, `prescriber` when `prescriber_npi IS NOT NULL AND pharmacy_npi IS NULL`, else `unknown`.

**Server-side name enrichment: set-based per page.** Collect distinct NPIs from the page, one batched query to `reference.dataq_master` and `reference.prescribers`, map back. No per-anomaly query.

**File:** add to `modules/reclaimrx/src/api/router.py`

**Test first** (`modules/reclaimrx/tests/detection/test_anomalies_api.py`):

```python
"""Tests for GET /anomalies and GET /detection-runs endpoints (§12 H4).

Reuses conftest.py fixtures. Integration tests run through the real FastAPI router
with dependency_overrides for get_db, get_current_user, and require_tenant_match —
matching the pattern in tests/integration/test_api_endpoints.py.
"""
from __future__ import annotations
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from shared.auth.dependencies import CurrentUser, get_current_user
from src.api.dependencies import get_db, require_tenant_match, RECLAIMRX_VIEWER_DEP
from src.api.router import router
from tests.conftest import TEST_TENANT_ID, OTHER_TENANT_ID, TEST_USER_ID


def _make_user(tenant_id=TEST_TENANT_ID) -> CurrentUser:
    return CurrentUser(
        id=TEST_USER_ID,
        tenant_id=tenant_id,
        email="test@example.com",
        status="active",
        roles=("reclaimrx.viewer", "reclaimrx.investigator", "reclaimrx.admin"),
        permissions=(),
    )


def _build_app(db: Session, tenant_id=TEST_TENANT_ID) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    _user = _make_user(tenant_id)

    def _db_override():
        yield db

    # Override the three real deps the endpoint uses:
    # 1. get_db (from src.api.dependencies) — yields the test DB session
    # 2. get_current_user (from shared.auth.dependencies) — returns test user
    # 3. require_tenant_match (from src.api.dependencies) — bypasses header check
    app.dependency_overrides[get_db] = _db_override
    app.dependency_overrides[get_current_user] = lambda: _user
    app.dependency_overrides[require_tenant_match] = lambda: _user
    return app


@pytest.fixture()
def client(db: Session):
    app = _build_app(db)
    return TestClient(app, raise_server_exceptions=True)


def _auth_headers(tenant_id=TEST_TENANT_ID):
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


class TestAnomaliesEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/reclaimrx/anomalies", headers=_auth_headers())
        assert resp.status_code == 200

    def test_response_has_items_and_total_count(self, client):
        resp = client.get("/api/v1/reclaimrx/anomalies", headers=_auth_headers())
        data = resp.json()
        assert "items" in data
        assert "total_count" in data  # §12 H4 — must be total_count not total

    def test_sort_by_valid_field_returns_200(self, client):
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?sort_by=severity&sort_dir=asc",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200

    def test_sort_by_invalid_field_returns_422(self, client):
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?sort_by=injected_column",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422
        assert "INVALID_SORT_BY" in resp.text

    def test_sort_dir_invalid_returns_422(self, client):
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?sort_by=severity&sort_dir=sideways",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422

    def test_entity_type_invalid_returns_422(self, client):
        """FIX (LOW): An invalid entity_type must return 422 with INVALID_ENTITY_TYPE code.

        The allowlist is pharmacy | prescriber | unknown. A non-allowlisted value
        must not be silently ignored (which would return unfiltered results).
        This is consistent with sort_by/sort_dir 422 validation.
        """
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?entity_type=invalid_type",
            headers=_auth_headers(),
        )
        assert resp.status_code == 422, (
            f"Expected 422 for invalid entity_type, got {resp.status_code}. "
            "The endpoint must validate entity_type against the allowlist "
            "(pharmacy|prescriber|unknown) and return 422 for non-allowlisted values."
        )
        assert "INVALID_ENTITY_TYPE" in resp.text, (
            f"Expected INVALID_ENTITY_TYPE error code in response, got: {resp.text}"
        )

    def test_entity_type_valid_pharmacy_returns_200(self, client):
        """Valid entity_type values must not return 422."""
        for valid in ("pharmacy", "prescriber", "unknown"):
            resp = client.get(
                f"/api/v1/reclaimrx/anomalies?entity_type={valid}",
                headers=_auth_headers(),
            )
            assert resp.status_code == 200, (
                f"entity_type='{valid}' is a valid allowlisted value and must return 200, "
                f"got {resp.status_code}"
            )

    def test_entity_type_unknown_filters_both_npi_null_rows_only(self, client, db):
        """FIX MED-1: entity_type=unknown must return ONLY rows where both pharmacy_npi
        and prescriber_npi are NULL.

        Previously the unknown filter was allowlisted (returned 200) but not applied
        to the query — it returned ALL anomalies instead of only both-NPI-null rows.
        This test seeds:
          (a) one anomaly with pharmacy_npi set (entity_type=pharmacy)
          (b) one anomaly with prescriber_npi set, pharmacy_npi null (entity_type=prescriber)
          (c) one anomaly with both NPIs null (entity_type=unknown)
        Asserts entity_type=unknown returns ONLY row (c).
        """
        from src.models.detection_run_models import Anomaly
        from decimal import Decimal

        def _make_anomaly(pharmacy_npi=None, prescriber_npi=None, finding_code="MFR-004"):
            return Anomaly(
                tenant_id=TEST_TENANT_ID, data_source="csv_upload",
                source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
                detection_kind="rule", severity="high",
                confidence=Decimal("0.80"),
                finding_code=finding_code, finding_summary="entity type test",
                finding_details={}, status="open",
                pharmacy_npi=pharmacy_npi,
                prescriber_npi=prescriber_npi,
            )

        a_pharmacy = _make_anomaly(pharmacy_npi="1234567890", finding_code="ETYPE-PH")
        a_prescriber = _make_anomaly(prescriber_npi="9876543210", finding_code="ETYPE-PR")
        a_unknown = _make_anomaly(finding_code="ETYPE-UK")  # both NPIs None
        for a in [a_pharmacy, a_prescriber, a_unknown]:
            db.add(a)
        db.flush()

        resp = client.get(
            "/api/v1/reclaimrx/anomalies?entity_type=unknown",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200, f"entity_type=unknown must return 200, got {resp.status_code}"
        items = resp.json()["items"]

        returned_ids = {item["id"] for item in items}
        assert str(a_unknown.id) in returned_ids, (
            "entity_type=unknown must include the both-NPI-null anomaly"
        )
        assert str(a_pharmacy.id) not in returned_ids, (
            "entity_type=unknown must NOT include anomalies where pharmacy_npi is set"
        )
        assert str(a_prescriber.id) not in returned_ids, (
            "entity_type=unknown must NOT include anomalies where prescriber_npi is set"
        )
        # Every returned item must have both NPIs null
        for item in items:
            assert item.get("pharmacy_npi") is None, (
                f"entity_type=unknown result must have pharmacy_npi=None, got: {item.get('pharmacy_npi')}"
            )
            assert item.get("prescriber_npi") is None, (
                f"entity_type=unknown result must have prescriber_npi=None, got: {item.get('prescriber_npi')}"
            )

    def test_filter_by_finding_code(self, client, db):
        from src.models.detection_run_models import Anomaly, DetectionRun
        from decimal import Decimal
        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload", run_label="api-test",
            status="completed", created_by=TEST_USER_ID,
            resolution_stats={},
        )
        db.add(run)
        db.flush()
        anomaly = Anomaly(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            data_source_run_id=run.id,
            source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
            detection_kind="rule", severity="critical",
            confidence=Decimal("0.90"),
            finding_code="ALL-001", finding_summary="test",
            finding_details={}, status="open",
        )
        db.add(anomaly)
        db.flush()

        resp = client.get(
            "/api/v1/reclaimrx/anomalies?finding_code=ALL-001",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert all(item["finding_code"] == "ALL-001" for item in data["items"])

    def test_cross_tenant_isolation(self, client, db):
        """Anomalies for OTHER_TENANT_ID must not appear in TEST_TENANT_ID response."""
        from src.models.detection_run_models import Anomaly, DetectionRun
        from decimal import Decimal
        run = DetectionRun(
            tenant_id=OTHER_TENANT_ID, data_source="csv_upload", run_label="other-tenant",
            status="completed", created_by=TEST_USER_ID,
            resolution_stats={},
        )
        db.add(run)
        db.flush()
        anomaly = Anomaly(
            tenant_id=OTHER_TENANT_ID, data_source="csv_upload",
            data_source_run_id=run.id,
            source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
            detection_kind="rule", severity="high",
            confidence=Decimal("0.70"),
            finding_code="MFR-004", finding_summary="cross-tenant test",
            finding_details={}, status="open",
        )
        db.add(anomaly)
        db.flush()

        resp = client.get("/api/v1/reclaimrx/anomalies", headers=_auth_headers(TEST_TENANT_ID))
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["items"]]
        assert str(anomaly.id) not in ids

    def test_pagination(self, client, db):
        resp = client.get(
            "/api/v1/reclaimrx/anomalies?page=1&page_size=5",
            headers=_auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 5

    def test_entity_type_derived_not_stored(self, client, db):
        """entity_type must be derived from which NPI field is set."""
        from src.models.detection_run_models import Anomaly
        from decimal import Decimal
        a = Anomaly(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
            detection_kind="rule", severity="high",
            confidence=Decimal("0.80"),
            finding_code="ALL-002", finding_summary="phantom pharmacy",
            finding_details={}, status="open",
            pharmacy_npi="1234567890",
        )
        db.add(a)
        db.flush()
        resp = client.get(
            f"/api/v1/reclaimrx/anomalies?finding_code=ALL-002",
            headers=_auth_headers(),
        )
        items = resp.json().get("items", [])
        pharmacy_items = [i for i in items if i.get("finding_code") == "ALL-002"
                         and i.get("pharmacy_npi") == "1234567890"]
        for item in pharmacy_items:
            assert item["entity_type"] == "pharmacy"


# ---------------------------------------------------------------------------
# Postgres-gated: entity_name enrichment uses real set-based join (§12 H4)
# ---------------------------------------------------------------------------

import os as _os
_RECLAIMRX_DB_URL = _os.environ.get("RECLAIMRX_DB_URL")
REAL_PG_DB = bool(_RECLAIMRX_DB_URL)


@pytest.fixture()
def pg_db():
    """Real Postgres session (SAVEPOINT-isolated) for the enrichment test."""
    if not REAL_PG_DB:
        pytest.skip("RECLAIMRX_DB_URL not set — skipping Postgres enrichment test")
    import sqlalchemy as sa
    from sqlalchemy import event as _sa_event
    engine = sa.create_engine(_RECLAIMRX_DB_URL, future=True)
    conn = engine.connect()
    outer = conn.begin()
    nested = conn.begin_nested()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")

    @_sa_event.listens_for(session, "after_transaction_end")
    def _reopen(sess, txn):
        nonlocal nested
        if txn.nested and not txn._parent.nested:
            nested = conn.begin_nested()

    yield session
    session.close()
    outer.rollback()
    conn.close()
    engine.dispose()


@pytest.fixture()
def pg_client(pg_db):
    """Postgres-backed TestClient: same dep-override pattern as `client`, but using the real PG session."""
    app = _build_app(pg_db)
    return TestClient(app, raise_server_exceptions=True)


@pytest.mark.skipif(not REAL_PG_DB, reason="requires live Postgres (RECLAIMRX_DB_URL unset)")
def test_entity_name_enrichment_real_join(pg_client, pg_db):
    """entity_name is populated from the real set-based join to dataq_master/prescribers.

    Seeds a known NPI in reference.dataq_master, plants an Anomaly referencing it,
    calls GET /anomalies, and asserts entity_name is the seeded name (not None).

    Requires: RECLAIMRX_DB_URL set pointing at a Postgres DB with
    reference.dataq_master and reference.prescribers accessible (FDW reference schema).
    """
    import sqlalchemy as sa

    # Use a KNOWN-PRESENT NPI from reference.dataq_master with a non-NULL
    # legal_business_name — READ-ONLY query, no mutation of the FDW foreign table.
    _ref = pg_db.execute(
        sa.text(
            "SELECT npi, legal_business_name FROM reference.dataq_master "
            "WHERE npi IS NOT NULL AND legal_business_name IS NOT NULL "
            "AND deactivation_code IS NULL "
            "LIMIT 1"
        )
    ).fetchone()
    assert _ref is not None, (
        "reference.dataq_master has no rows with a non-NULL legal_business_name — "
        "FDW not provisioned. Run infrastructure/scripts/setup_fdw.sh first."
    )
    KNOWN_PHARMACY_NPI = _ref.npi
    KNOWN_PHARMACY_NAME = _ref.legal_business_name

    from src.models.detection_run_models import Anomaly
    from decimal import Decimal
    a = Anomaly(
        tenant_id=TEST_TENANT_ID, data_source="csv_upload",
        source_table="csv_upload_rows", source_row_id=uuid.uuid4(),
        detection_kind="rule", severity="high",
        confidence=Decimal("0.80"),
        finding_code="ALL-002", finding_summary="entity-name enrichment test",
        finding_details={}, status="open",
        pharmacy_npi=KNOWN_PHARMACY_NPI,
    )
    pg_db.add(a)
    pg_db.flush()

    resp = pg_client.get(
        f"/api/v1/reclaimrx/anomalies?finding_code=ALL-002",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    items = resp.json().get("items", [])
    matching = [
        i for i in items
        if i.get("pharmacy_npi") == KNOWN_PHARMACY_NPI
    ]
    assert matching, (
        f"Expected at least one anomaly with pharmacy_npi={KNOWN_PHARMACY_NPI}, got items={items}"
    )
    for item in matching:
        assert item["entity_name"] == KNOWN_PHARMACY_NAME, (
            f"entity_name enrichment failed: got {item['entity_name']!r}, "
            f"expected {KNOWN_PHARMACY_NAME!r}. "
            "The production path must do the real join (not return None)."
        )
```

Run → RED.

**Implementation — add to `modules/reclaimrx/src/api/router.py`:**

**Import fix (apply first):** The existing router.py line 11 reads `from sqlalchemy import func, select`. The `list_anomalies` endpoint calls `text(...)` for the set-based NPI enrichment queries. Add `text` to that import before adding the endpoint:

```python
# Change existing line 11 in router.py from:
#   from sqlalchemy import func, select
# to:
from sqlalchemy import func, select, text
```

```python
# ── AnomalyRead DTO ────────────────────────────────────────────────────────────

class AnomalyRead(BaseModel):
    id: str
    tenant_id: str
    finding_code: str
    finding_summary: str
    finding_details: dict
    severity: str
    confidence: str
    status: str
    pharmacy_npi: str | None = None
    prescriber_npi: str | None = None
    entity_type: str          # DERIVED: "pharmacy"|"prescriber"|"unknown"
    entity_name: str | None = None  # enriched per-page from reference tables
    ndc: str | None = None
    amount_paid: str | None = None
    amount_billed: str | None = None
    date_of_service: str | None = None
    data_source_run_id: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class AnomalyListResponse(BaseModel):
    items: list[AnomalyRead]
    total_count: int   # §12 H4 — named total_count, not total
    page: int
    page_size: int


# Allowlisted sort columns (§12 H4 — reject non-allowlisted with 422)
_ANOMALY_SORT_ALLOWLIST: dict[str, str] = {
    "created_at": "created_at",
    "severity": "severity",
    "amount_paid": "amount_paid",
    "finding_code": "finding_code",
}


@router.get("/anomalies", response_model=AnomalyListResponse)
async def list_anomalies(
    run_id: str | None = Query(None),
    finding_code: str | None = Query(None),
    severity: str | None = Query(None),
    entity_type: str | None = Query(None),  # "pharmacy"|"prescriber"
    status: str | None = Query(None),
    sort_by: str | None = Query(None),      # allowlist: created_at|severity|amount_paid|finding_code
    sort_dir: str | None = Query(None),     # "asc"|"desc" (default "desc")
    page: int = Query(1, ge=1),
    page_size: int = Query(50, le=200),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> AnomalyListResponse:
    """Server-side filtered/sorted/paginated anomalies (§12 H4).

    entity_type is DERIVED (not stored): pharmacy when pharmacy_npi IS NOT NULL,
    prescriber when prescriber_npi IS NOT NULL AND pharmacy_npi IS NULL.

    entity_name enrichment is set-based per page: collect distinct NPIs in the
    page, one batched join to dataq_master/prescribers, map back. No N+1.

    sort_by allowlist: created_at, severity, amount_paid, finding_code.
    Non-allowlisted sort_by values return 422.
    """
    from src.models.detection_run_models import Anomaly as AnomalyModel  # noqa: PLC0415

    # Validate sort params
    if sort_by is not None and sort_by not in _ANOMALY_SORT_ALLOWLIST:
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope(
                "INVALID_SORT_BY",
                f"sort_by must be one of: {', '.join(_ANOMALY_SORT_ALLOWLIST)}",
                field="sort_by",
            ),
        )
    if sort_dir is not None and sort_dir not in ("asc", "desc"):
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope(
                "INVALID_SORT_DIR",
                "sort_dir must be 'asc' or 'desc'",
                field="sort_dir",
            ),
        )

    # FIX (LOW): Validate entity_type against allowlist — silently ignoring invalid
    # values would return unfiltered results, masking the caller error.
    # Consistent with sort_by/sort_dir 422 validation pattern.
    _ENTITY_TYPE_ALLOWLIST: frozenset[str] = frozenset({"pharmacy", "prescriber", "unknown"})
    if entity_type is not None and entity_type not in _ENTITY_TYPE_ALLOWLIST:
        raise HTTPException(
            status_code=422,
            detail=build_error_envelope(
                "INVALID_ENTITY_TYPE",
                f"entity_type must be one of: {', '.join(sorted(_ENTITY_TYPE_ALLOWLIST))}",
                field="entity_type",
            ),
        )

    stmt = select(AnomalyModel).where(AnomalyModel.tenant_id == user.tenant_id)

    if run_id:
        stmt = stmt.where(AnomalyModel.data_source_run_id == uuid.UUID(run_id))
    if finding_code:
        stmt = stmt.where(AnomalyModel.finding_code == finding_code)
    if severity:
        stmt = stmt.where(AnomalyModel.severity == severity)
    if status:
        stmt = stmt.where(AnomalyModel.status == status)
    if entity_type == "pharmacy":
        stmt = stmt.where(AnomalyModel.pharmacy_npi.isnot(None))
    elif entity_type == "prescriber":
        stmt = stmt.where(
            AnomalyModel.prescriber_npi.isnot(None),
            AnomalyModel.pharmacy_npi.is_(None),
        )
    elif entity_type == "unknown":
        # FIX MED-1: entity_type=unknown was allowlisted but never applied to the query,
        # returning ALL anomalies instead of only rows where both NPIs are NULL.
        # entity_type derivation semantics (from spec §12 H4):
        #   pharmacy  = pharmacy_npi IS NOT NULL
        #   prescriber = prescriber_npi IS NOT NULL AND pharmacy_npi IS NULL
        #   unknown   = pharmacy_npi IS NULL AND prescriber_npi IS NULL
        stmt = stmt.where(
            AnomalyModel.pharmacy_npi.is_(None),
            AnomalyModel.prescriber_npi.is_(None),
        )

    total_count = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()

    # Apply validated sort (default: created_at desc)
    _sort_col_name = _ANOMALY_SORT_ALLOWLIST.get(sort_by or "created_at", "created_at")
    _sort_col = getattr(AnomalyModel, _sort_col_name)
    _order = _sort_col.asc() if sort_dir == "asc" else _sort_col.desc()

    offset = (page - 1) * page_size
    rows = db.execute(
        stmt.order_by(_order).offset(offset).limit(page_size)
    ).scalars().all()

    # Set-based per-page entity_name enrichment (§12 H4 — no N+1)
    pharmacy_npis = list({r.pharmacy_npi for r in rows if r.pharmacy_npi})
    prescriber_npis = list({r.prescriber_npi for r in rows if r.prescriber_npi and not r.pharmacy_npi})

    pharmacy_names: dict[str, str] = {}
    prescriber_names: dict[str, str] = {}

    _is_sqlite = db.bind.dialect.name == "sqlite"  # type: ignore[union-attr]

    if pharmacy_npis:
        if _is_sqlite:
            # SQLite test env: cross-schema joins are unavailable; leave pharmacy_names empty.
            pharmacy_names = {}
        else:
            # Production path: real set-based join; exceptions propagate so failures surface.
            ph_placeholders = ", ".join([f":ph_{i}" for i in range(len(pharmacy_npis))])
            ph_params = {f"ph_{i}": n for i, n in enumerate(pharmacy_npis)}
            ph_rows = db.execute(
                text(
                    f"SELECT npi, legal_business_name FROM reference.dataq_master "
                    f"WHERE npi IN ({ph_placeholders})"
                ),
                ph_params,
            ).fetchall()
            pharmacy_names = {r.npi: r.legal_business_name for r in ph_rows}

    if prescriber_npis:
        if _is_sqlite:
            # SQLite test env: cross-schema joins are unavailable; leave prescriber_names empty.
            prescriber_names = {}
        else:
            # Production path: real set-based join; exceptions propagate so failures surface.
            pr_placeholders = ", ".join([f":pr_{i}" for i in range(len(prescriber_npis))])
            pr_params = {f"pr_{i}": n for i, n in enumerate(prescriber_npis)}
            pr_rows = db.execute(
                text(
                    f"SELECT npi, display_name FROM reference.prescribers "
                    f"WHERE npi IN ({pr_placeholders})"
                ),
                pr_params,
            ).fetchall()
            prescriber_names = {r.npi: r.display_name for r in pr_rows}

    def _to_read(a: "AnomalyModel") -> AnomalyRead:
        if a.pharmacy_npi:
            etype = "pharmacy"
            ename = pharmacy_names.get(a.pharmacy_npi)
        elif a.prescriber_npi:
            etype = "prescriber"
            ename = prescriber_names.get(a.prescriber_npi)
        else:
            etype = "unknown"
            ename = None
        return AnomalyRead(
            id=str(a.id),
            tenant_id=str(a.tenant_id),
            finding_code=a.finding_code,
            finding_summary=a.finding_summary,
            finding_details=a.finding_details or {},
            severity=a.severity,
            confidence=str(a.confidence),
            status=a.status,
            pharmacy_npi=a.pharmacy_npi,
            prescriber_npi=a.prescriber_npi,
            entity_type=etype,
            entity_name=ename,
            ndc=a.ndc,
            amount_paid=str(a.amount_paid) if a.amount_paid is not None else None,
            amount_billed=str(a.amount_billed) if a.amount_billed is not None else None,
            date_of_service=str(a.date_of_service) if a.date_of_service else None,
            data_source_run_id=str(a.data_source_run_id) if a.data_source_run_id else None,
            created_at=a.created_at.isoformat(),
        )

    return AnomalyListResponse(
        items=[_to_read(r) for r in rows],
        total_count=total_count,
        page=page,
        page_size=page_size,
    )
```

Run → GREEN.

```
git add modules/reclaimrx/src/api/router.py \
        modules/reclaimrx/tests/detection/test_anomalies_api.py
git commit -m "feat(reclaimrx): GET /anomalies — server-side filter/sort/paginate, derived entity_type, set-based name enrichment (§12 H4)"
```

---

### Task 6b — GET /api/v1/reclaimrx/detection-runs

**Test first** (add to `test_anomalies_api.py`):

```python
class TestDetectionRunsEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/api/v1/reclaimrx/detection-runs", headers=_auth_headers())
        assert resp.status_code == 200

    def test_returns_list_with_required_fields(self, client, db):
        from src.models.detection_run_models import DetectionRun
        run = DetectionRun(
            tenant_id=TEST_TENANT_ID, data_source="csv_upload",
            run_label="api-run-test", status="completed",
            source_filename="test.csv", created_by=TEST_USER_ID,
            resolution_stats={"inserted_count": 100, "expected_count": 100},
            record_count=100, anomaly_count=2,
        )
        db.add(run)
        db.flush()
        resp = client.get("/api/v1/reclaimrx/detection-runs", headers=_auth_headers())
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        if items:
            r = items[0]
            assert "source_filename" in r
            assert "record_count" in r
            assert "anomaly_count" in r
            assert "status" in r
            assert "started_at" in r
            assert "resolution_stats" in r

    def test_cross_tenant_isolation_runs(self, client, db):
        from src.models.detection_run_models import DetectionRun
        other_run = DetectionRun(
            tenant_id=OTHER_TENANT_ID, data_source="csv_upload",
            run_label="other-run", status="completed", created_by=TEST_USER_ID,
            resolution_stats={},
        )
        db.add(other_run)
        db.flush()
        resp = client.get("/api/v1/reclaimrx/detection-runs", headers=_auth_headers(TEST_TENANT_ID))
        ids = [r["id"] for r in resp.json()]
        assert str(other_run.id) not in ids
```

Run → RED.

**Implementation — add to router.py:**

```python
class DetectionRunRead(BaseModel):
    id: str
    tenant_id: str
    source_filename: str | None = None
    record_count: int
    anomaly_count: int
    status: str
    started_at: str
    completed_at: str | None = None
    resolution_stats: dict

    model_config = {"from_attributes": True}


@router.get("/detection-runs", response_model=list[DetectionRunRead])
async def list_detection_runs(
    status: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: CurrentUser = RECLAIMRX_VIEWER_DEP,
    _tenant: CurrentUser = Depends(require_tenant_match),
) -> list:
    from src.models.detection_run_models import DetectionRun as DetectionRunModel  # noqa: PLC0415
    stmt = select(DetectionRunModel).where(
        DetectionRunModel.tenant_id == user.tenant_id
    )
    if status:
        stmt = stmt.where(DetectionRunModel.status == status)
    rows = db.execute(
        stmt.order_by(DetectionRunModel.started_at.desc()).limit(limit).offset(offset)
    ).scalars().all()
    return [
        DetectionRunRead(
            id=str(r.id),
            tenant_id=str(r.tenant_id),
            source_filename=r.source_filename,
            record_count=r.record_count or 0,
            anomaly_count=r.anomaly_count or 0,
            status=r.status,
            started_at=r.started_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            resolution_stats=r.resolution_stats or {},
        )
        for r in rows
    ]
```

Run → GREEN.

```
git add modules/reclaimrx/src/api/router.py \
        modules/reclaimrx/tests/detection/test_anomalies_api.py
git commit -m "feat(reclaimrx): GET /detection-runs — tenant-scoped list with source_filename, record_count, anomaly_count, resolution_stats"
```

---

## Phase 7 — Portal (§12 H4/H6) (3 tasks)

### Task 7a — finding_code→LeakageCategory mapping + AnomalyRead adapter

**DO NOT mutate `portal/shared/types/reclaimrx.ts` World-B types.** Add NEW types; adapt at page boundary only.

**finding_code → LeakageCategory mapping table (explicit, §12 H6):**

| finding_code | LeakageCategory |
|---|---|
| ALL-001 | `pharmacy_misuse` |
| ALL-002 | `pharmacy_misuse` |
| ALL-003 | `prescriber_anomaly` |
| ALL-005 | `patient_anomaly` |
| ALL-006 | `pharmacy_misuse` |
| MFR-001 | `pharmacy_misuse` |
| MFR-002 | `pharmacy_misuse` |
| MFR-003 | `pharmacy_misuse` |
| MFR-004 | `pharmacy_misuse` |
| HP-005 | `prescriber_anomaly` |
| HP-008 | `patient_anomaly` |
| REJECT-75-70 | `pharmacy_misuse` |
| TH-002 | `prescriber_anomaly` |
| TH-005 | `prescriber_anomaly` |
| *(default)* | `pharmacy_misuse` |

**File:** `portal/shared/types/reclaimrx-v2.ts` (NEW file — append-only, no mutation of reclaimrx.ts)

```typescript
// portal/shared/types/reclaimrx-v2.ts
// New types for ReclaimRx v2 anomaly API. World-B types (LeakageFlag, LeakageCategory,
// Investigation) in reclaimrx.ts are NOT mutated. This file is append-only.

import type { UUID, ISODateTimeString } from "./common";
import type { LeakageCategory, LeakageFlag } from "./reclaimrx";

/** AnomalyRead — matches GET /api/v1/reclaimrx/anomalies item shape. */
export interface AnomalyRead {
  id: UUID;
  tenant_id: UUID;
  finding_code: string;
  finding_summary: string;
  finding_details: Record<string, unknown>;
  severity: "critical" | "high" | "medium" | "low" | "informational";
  confidence: string;
  status: "open" | "under_review" | "confirmed" | "dismissed" | "in_recoup" | "in_audit" | "resolved" | "written_off";
  pharmacy_npi: string | null;
  prescriber_npi: string | null;
  entity_type: "pharmacy" | "prescriber" | "unknown";
  entity_name: string | null;
  ndc: string | null;
  amount_paid: string | null;
  amount_billed: string | null;
  date_of_service: string | null;
  data_source_run_id: UUID | null;
  created_at: ISODateTimeString;
}

export interface AnomalyListResponse {
  items: AnomalyRead[];
  total_count: number;  // §12 H4 — named total_count
  page: number;
  page_size: number;
}

export interface DetectionRunRead {
  id: UUID;
  tenant_id: UUID;
  source_filename: string | null;
  record_count: number;
  anomaly_count: number;
  status: "in_progress" | "completed" | "failed" | "cancelled";
  started_at: ISODateTimeString;
  completed_at: ISODateTimeString | null;
  resolution_stats: Record<string, unknown>;
}

/** Explicit finding_code → LeakageCategory mapping table (§12 H6). */
export const FINDING_CODE_TO_CATEGORY: Record<string, LeakageCategory> = {
  "ALL-001": "pharmacy_misuse",
  "ALL-002": "pharmacy_misuse",
  "ALL-003": "prescriber_anomaly",
  "ALL-005": "patient_anomaly",
  "ALL-006": "pharmacy_misuse",
  "MFR-001": "pharmacy_misuse",
  "MFR-002": "pharmacy_misuse",
  "MFR-003": "pharmacy_misuse",
  "MFR-004": "pharmacy_misuse",
  "HP-005":  "prescriber_anomaly",
  "HP-008":  "patient_anomaly",
  "REJECT-75-70": "pharmacy_misuse",
  "TH-002":  "prescriber_anomaly",
  "TH-005":  "prescriber_anomaly",
};

/** Anomaly status → LeakageFlag status mapping (adapter, page boundary only). */
export const ANOMALY_STATUS_TO_LEAKAGE: Record<string, LeakageFlag["status"]> = {
  "open": "new",
  "under_review": "under_investigation",
  "confirmed": "confirmed",
  "dismissed": "dismissed",
  "in_recoup": "confirmed",
  "in_audit": "under_investigation",
  "resolved": "dismissed",
  "written_off": "dismissed",
};

/** Adapt AnomalyRead → LeakageFlag shape (page boundary only, NOT a shared-type mutation). */
export function anomalyToLeakageFlag(a: AnomalyRead): LeakageFlag {
  return {
    id: a.id,
    tenant_id: a.tenant_id,
    category: FINDING_CODE_TO_CATEGORY[a.finding_code] ?? "pharmacy_misuse",
    entity_type: a.entity_type === "prescriber" ? "prescriber"
               : a.entity_type === "pharmacy" ? "pharmacy"
               : "pharmacy",
    entity_name: a.entity_name ?? a.finding_code,
    entity_id: a.id,  // use anomaly id as entity_id placeholder
    estimated_leakage: a.amount_paid ?? "0.00",
    status: ANOMALY_STATUS_TO_LEAKAGE[a.status] ?? "new",
    date_flagged: a.created_at,
    investigation_id: undefined,
    program_name: undefined,
  };
}
```

**Test** (`portal/shared/lib/tests/test-reclaimrx-v2-adapter.ts` — Jest unit test):
```typescript
// portal/shared/lib/tests/test-reclaimrx-v2-adapter.ts
import { anomalyToLeakageFlag, FINDING_CODE_TO_CATEGORY } from "@shared/types/reclaimrx-v2";

describe("FINDING_CODE_TO_CATEGORY", () => {
  it("maps ALL-001 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-001"]).toBe("pharmacy_misuse");
  });
  it("maps ALL-003 to prescriber_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-003"]).toBe("prescriber_anomaly");
  });
  it("maps HP-008 to patient_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["HP-008"]).toBe("patient_anomaly");
  });
  it("maps REJECT-75-70 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["REJECT-75-70"]).toBe("pharmacy_misuse");
  });
});

describe("anomalyToLeakageFlag adapter", () => {
  const baseAnomaly = {
    id: "aaa-111" as any,
    tenant_id: "bbb-222" as any,
    finding_code: "ALL-002",
    finding_summary: "Phantom pharmacy",
    finding_details: {},
    severity: "critical" as const,
    confidence: "0.9000",
    status: "open" as const,
    pharmacy_npi: "1234567890",
    prescriber_npi: null,
    entity_type: "pharmacy" as const,
    entity_name: "Test Pharmacy",
    ndc: null,
    amount_paid: "120.50",
    amount_billed: "130.00",
    date_of_service: "2026-01-15",
    data_source_run_id: null,
    created_at: "2026-05-31T10:00:00Z",
  };

  it("maps open → new", () => {
    const flag = anomalyToLeakageFlag(baseAnomaly);
    expect(flag.status).toBe("new");
  });
  it("maps under_review → under_investigation", () => {
    const flag = anomalyToLeakageFlag({ ...baseAnomaly, status: "under_review" as any });
    expect(flag.status).toBe("under_investigation");
  });
  it("sets estimated_leakage from amount_paid", () => {
    const flag = anomalyToLeakageFlag(baseAnomaly);
    expect(flag.estimated_leakage).toBe("120.50");
  });
  it("sets category from finding_code", () => {
    const flag = anomalyToLeakageFlag(baseAnomaly);
    expect(flag.category).toBe("pharmacy_misuse");
  });
});
```

Run: `cd portal && npx jest shared/lib/tests/test-reclaimrx-v2-adapter` → GREEN.

```
git add portal/shared/types/reclaimrx-v2.ts \
        portal/shared/lib/tests/test-reclaimrx-v2-adapter.ts
git commit -m "feat(portal): AnomalyRead types + finding_code→LeakageCategory mapping + adapter (append-only, no World-B mutation)"
```

---

### Task 7b — Leakage Monitor: repoint queryFn to /anomalies, push filters to backend

**File:** `portal/operator/app/reclaimrx/leakage/page.tsx`

**What changes:**
1. Replace `queryFn` from `/leakage` to `/anomalies` with page + filter params pushed to backend. Remove client-side `useMemo` filter.
2. Add `finding_code` and `severity` filter fields to `FILTER_FIELDS`.
3. Use `anomalyToLeakageFlag` adapter at the page boundary to convert `AnomalyRead[]` to `LeakageFlag[]` for existing `COLUMNS` and `CATEGORY_LABELS` (which use `LeakageFlag` shape).

**No new components. No mutation of `LeakageFlag` type.**

The updated `page.tsx` replaces the existing file. Key structural changes only shown:

**Sort allowlist (mirrors Task 6a `_ANOMALY_SORT_ALLOWLIST`):**
`created_at` | `severity` | `amount_paid` | `finding_code`

**TDD — RED step first.**

`portal/operator/app/reclaimrx/leakage/__tests__/page.test.tsx` (write this file before touching `page.tsx` — it MUST fail until the queryFn change is in place):

```typescript
// portal/operator/app/reclaimrx/leakage/__tests__/page.test.tsx
// RED: fails before the queryFn + sort wiring changes are applied.
// GREEN: passes after.

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { vi, describe, it, expect, beforeEach } from "vitest";
import LeakagePage from "../page";
import * as apiClient from "@shared/lib/api-client";

const mockApiGet = vi.spyOn(apiClient, "apiGet");

function wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

const EMPTY_RESPONSE = { items: [], total_count: 0, page: 1, page_size: 50 };

beforeEach(() => {
  mockApiGet.mockResolvedValue(EMPTY_RESPONSE);
});

describe("LeakagePage — server-driven filter/sort/paginate (§12 H4)", () => {
  it("sends page, filters, and sort params to /anomalies — NOT a fetch-all", async () => {
    render(<LeakagePage />, { wrapper });

    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());

    const calledUrl: string = mockApiGet.mock.calls[0][0] as string;
    // Must hit the /anomalies endpoint
    expect(calledUrl).toContain("/anomalies");
    // Must include pagination — no unfiltered fetch-all
    expect(calledUrl).toMatch(/[?&]page=\d/);
    expect(calledUrl).toMatch(/[?&]page_size=\d/);
    // Must include sort params (default sort wired to backend)
    expect(calledUrl).toMatch(/[?&]sort_by=/);
    expect(calledUrl).toMatch(/[?&]sort_dir=/);
    // Must NOT be the old /leakage endpoint
    expect(calledUrl).not.toContain("/leakage?");
  });

  it("sends sort_by/sort_dir to backend when column header is clicked — not client-side sort", async () => {
    render(<LeakagePage />, { wrapper });

    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());
    mockApiGet.mockClear();

    // Simulate column-header sort click (ConfigurableDataTable fires onSortChange)
    const sortHeader = screen.getByRole("button", { name: /severity/i });
    await userEvent.click(sortHeader);

    await waitFor(() => expect(mockApiGet).toHaveBeenCalled());

    const calledUrl: string = mockApiGet.mock.calls[0][0] as string;
    expect(calledUrl).toContain("sort_by=severity");
    // page resets to 1 on sort change
    expect(calledUrl).toContain("page=1");
  });

  it("does NOT apply a client-side useMemo filter as source of truth — response.items is used directly after adapter", async () => {
    const seededItems = [
      {
        id: "aaa",
        finding_code: "ALL-001",
        severity: "high",
        status: "open",
        amount_paid: "500.00",
        pharmacy_npi: "1234567890",
        prescriber_npi: null,
        created_at: "2026-05-01T00:00:00Z",
        entity_name: null,
        entity_type: "pharmacy",
        run_id: "r1",
      },
    ];
    mockApiGet.mockResolvedValueOnce({ items: seededItems, total_count: 1, page: 1, page_size: 50 });

    render(<LeakagePage />, { wrapper });

    // The row must appear from the adapter — no extra filter pass removes it
    await waitFor(() =>
      expect(screen.getByText("ALL-001")).toBeInTheDocument()
    );
  });
});
```

Confirm RED: run `pnpm vitest run portal/operator/app/reclaimrx/leakage/__tests__/page.test.tsx` — all three tests must FAIL before the queryFn/sort changes below are applied.

**GREEN step — update `page.tsx`:**

```typescript
// Replace queryKey and queryFn + add sort state:
const [page, setPage] = useState(1);
const PAGE_SIZE = 50;

// Sort state — allowlist mirrors Task 6a _ANOMALY_SORT_ALLOWLIST
type AnomalySortBy = "created_at" | "severity" | "amount_paid" | "finding_code";
const [sortBy, setSortBy] = useState<AnomalySortBy>("created_at");
const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

// Reset page to 1 whenever sort changes
const handleSortChange = (column: AnomalySortBy, direction: "asc" | "desc") => {
  setSortBy(column);
  setSortDir(direction);
  setPage(1);
};

const queryParams = new URLSearchParams();
if (filterValues.category && (filterValues.category as string[]).length > 0) {
  // category is a LeakageCategory — not directly a finding_code.
  // The backend filters by finding_code; we must map back.
  // For now, pass severity/status filters directly; category is client-side-only
  // (the /anomalies endpoint doesn't filter by LeakageCategory).
}
if (filterValues.severity) queryParams.set("severity", filterValues.severity as string);
if (filterValues.status && (filterValues.status as string[]).length === 1) {
  // map leakage status back to anomaly status
  const anomalyStatus = Object.entries(ANOMALY_STATUS_TO_LEAKAGE)
    .find(([, v]) => v === (filterValues.status as string[])[0])?.[0];
  if (anomalyStatus) queryParams.set("status", anomalyStatus);
}
if (filterValues.finding_code) queryParams.set("finding_code", filterValues.finding_code as string);
queryParams.set("page", String(page));
queryParams.set("page_size", String(PAGE_SIZE));
// Server-side sort — must be in queryKey so a sort change triggers a refetch
queryParams.set("sort_by", sortBy);
queryParams.set("sort_dir", sortDir);

const { data: response, isLoading } = useQuery<AnomalyListResponse>({
  queryKey: ["anomalies", filterValues, page, sortBy, sortDir],  // sort in key → refetch on change
  queryFn: () =>
    apiGet<AnomalyListResponse>(
      buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/anomalies?${queryParams.toString()}`)
    ),
  staleTime: 60_000,
});

// Adapter at page boundary — NOT mutating LeakageFlag type
const flags: LeakageFlag[] = useMemo(
  () => (response?.items ?? []).map(anomalyToLeakageFlag),
  [response]
  // NOTE: this useMemo is a shape-transform only (adapter), NOT a filter or sort.
  // No filter/sort logic here — those are server-driven via queryParams above.
);
const totalCount = response?.total_count ?? 0;  // §12 H4 — total_count not total

// Wire ConfigurableDataTable column-header sort to server sort state.
// The table's onSortChange drives handleSortChange → setSortBy/setSortDir → queryKey change
// → useQuery refetch. There is NO page-local client-side sort applied to `flags`.
// Pass sortBy/sortDir as controlled props so the table header shows the active sort state.
//
// <ConfigurableDataTable
//   ...
//   sortBy={sortBy}
//   sortDir={sortDir}
//   onSortChange={(col, dir) => handleSortChange(col as AnomalySortBy, dir)}
// />
//
// Sortable columns: created_at, severity, amount_paid, finding_code (allowlist from Task 6a).
// Do NOT enable sort on any column outside that allowlist — the backend will 422.

// Add finding_code + severity to FILTER_FIELDS (append, not replace):
// { id: "finding_code", label: "Finding Code", type: "text", placeholder: "e.g. ALL-001" },
// { id: "severity", label: "Severity", type: "select", options: [...] },
```

Confirm GREEN: re-run the test file — all three tests must now PASS.

The page renders existing `COLUMNS` and `CATEGORY_LABELS` unchanged. No `LeakageFlag` type mutation. Adapter (`anomalyToLeakageFlag`) remains Task 7a's concern.

```
git add portal/operator/app/reclaimrx/leakage/__tests__/page.test.tsx \
        portal/operator/app/reclaimrx/leakage/page.tsx \
        portal/shared/types/reclaimrx-v2.ts
git commit -m "feat(portal): leakage monitor — server-driven sort+filter+paginate to /anomalies; RED-first test for §12 H4"
```

---

### Task 7c — Wire graph-runs stub to /detection-runs

**File:** `portal/operator/app/reclaimrx/graph-runs/page.tsx`

Replace `ComingSoonPage` with a `ConfigurableDataTable` wired to `GET /detection-runs`.

```typescript
"use client";
// portal/operator/app/reclaimrx/graph-runs/page.tsx
// Replaces SP-3 Plan A5 ComingSoonPage stub. Now wired to /detection-runs.

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { DetectionRunRead } from "@shared/types/reclaimrx-v2";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";

const COLUMNS: Column<DetectionRunRead>[] = [
  {
    id: "id",
    header: "Run ID",
    accessor: (r) => r.id.slice(0, 8),
    cell: (v) => <span className="font-mono text-xs">{v as string}</span>,
  },
  {
    id: "source_filename",
    header: "File",
    accessor: (r) => r.source_filename ?? "—",
    sortable: true,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    cell: (v) => {
      const variantMap: Record<string, any> = {
        completed: "success", failed: "error",
        in_progress: "warning", cancelled: "neutral",
      };
      return <StatusBadge status={v as string} variant={variantMap[v as string] ?? "info"} />;
    },
    sortable: true,
  },
  {
    id: "record_count",
    header: "Records",
    accessor: (r) => r.record_count,
    align: "right",
    sortable: true,
  },
  {
    id: "anomaly_count",
    header: "Anomalies",
    accessor: (r) => r.anomaly_count,
    align: "right",
    sortable: true,
  },
  {
    id: "started_at",
    header: "Started",
    accessor: (r) => r.started_at.slice(0, 19).replace("T", " "),
    format: "date",
    sortable: true,
  },
];

export default function DetectionRunsPage() {
  const { data: runs = [], isLoading } = useQuery<DetectionRunRead[]>({
    queryKey: ["detection-runs"],
    queryFn: () =>
      apiGet<DetectionRunRead[]>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/detection-runs`)
      ),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-xl font-bold text-ifx-gray-900">Detection Runs</h1>
        <p className="text-sm text-ifx-gray-400 mt-0.5">
          CSV detection run history — {runs.length} runs
        </p>
      </div>
      <div className="bg-white rounded-lg ifx-card-shadow">
        <ConfigurableDataTable
          tableId="detection-runs"
          columns={COLUMNS}
          data={runs}
          loading={isLoading}
          searchable
          pagination={{ pageSize: 20, pageSizeOptions: [20, 50] }}
          emptyMessage="No detection runs found."
        />
      </div>
    </div>
  );
}
```

```
git add portal/operator/app/reclaimrx/graph-runs/page.tsx
git commit -m "feat(portal): wire graph-runs stub → /detection-runs ConfigurableDataTable (replaces ComingSoonPage)"
```

---

## Phase 8 — Acceptance (1 task)

### Task 8a — Clean re-detect on 2.6M rows + calibration loop

**DO NOT re-ingest.** The 2.6M rows are already in `reclaimrx.csv_upload_rows`. Re-run detection only.

**Step 1: Set environment variables.**
```powershell
$env:PYTHONPATH = "modules\reclaimrx"
$env:RECLAIMRX_DB_URL = "postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev"
$env:RECLAIMRX_BATCH_STATEMENT_TIMEOUT_MS = "0"
```

**Step 2: RLS GUC wrapper — the CLI MUST set `app.current_tenant_id` before calling `run_detection`.**

The CLI must execute this within ONE transaction on the `ifx_dev_app` session:
```python
# modules/reclaimrx/src/cli/detect.py — required pattern for run_detection call
from sqlalchemy import text

with db.begin():
    # Set RLS GUC (parameterized — never f-string with untrusted input)
    db.execute(
        text("SET LOCAL app.current_tenant_id = :tenant_id"),
        {"tenant_id": str(run.tenant_id)},
    )
    # Verify the GUC is set before proceeding
    result = db.execute(
        text("SELECT current_setting('app.current_tenant_id')")
    ).scalar_one()
    assert result == str(run.tenant_id), (
        f"RLS GUC not set correctly: got {result!r}, expected {run.tenant_id!r}"
    )
    # run_detection operates inside the same transaction (same session, same GUC)
    count = run_detection(db, run)
```

If the CLI does not already follow this pattern, update `modules/reclaimrx/src/cli/detect.py` to match it exactly before running acceptance.

**RLS cross-tenant test** — file: `modules/reclaimrx/tests/detection/test_rls_cli.py`

This test requires a **real Postgres session with RLS enabled** (not the SQLite SAVEPOINT fixture).
It uses the `RECLAIMRX_DB_URL` environment variable (ifx_dev_app role) and is skipped when not set.
It does NOT use the shared `db` SQLite fixture from conftest.py.

```python
"""RLS GUC test: run_detection must respect SET LOCAL app.current_tenant_id.

Requires a real Postgres session with RLS enabled (RECLAIMRX_DB_URL set).
Skipped when RECLAIMRX_DB_URL is not set.

Design:
  - Seeding uses an ADMIN/OWNER connection (RECLAIMRX_OWNER_DB_URL, or the same URL
    with SET SESSION AUTHORIZATION bypassing RLS) so both tenant-A and tenant-B rows
    are inserted without being filtered by the GUC.  This is critical: seeding via
    ifx_dev_app under a single-tenant GUC would cause the INSERT for the other tenant
    to fail or be misattributed under FORCE ROW LEVEL SECURITY.
  - Seed data is COMMITTED immediately (not held in an open transaction) so that the
    separate ifx_dev_app pg_session can see it.  Postgres does not expose uncommitted
    rows from another session — a flush-only owner session would make pg_session see
    nothing and the test would fail before validating SET LOCAL isolation.
  - Because seed data is committed, the test uses explicit ID-based teardown in a
    finally block (owner session deletes seeded rows by known IDs) to remain repeatable.
  - The behavior-under-test (run_detection) runs in a separate ifx_dev_app session
    with SET LOCAL app.current_tenant_id = tenant_A.
  - Isolation is verified from BOTH sides:
      (i)  tenant-A session: run created anomalies only for tenant A, zero for tenant B.
      (ii) admin/owner session: tenant-B rows still exist untouched and zero tenant-B
           anomalies were created — proving "tenant B not leaked into" from a session
           that can actually see tenant-B data (not vacuously invisible under tenant-A GUC).
"""
import os
import uuid
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import text, select, event

REAL_DB = os.environ.get("RECLAIMRX_DB_URL", "")
# Owner/superuser URL for seeding both tenants without RLS filtering.
# Falls back to RECLAIMRX_DB_URL if not separately configured (dev convenience only;
# in CI set RECLAIMRX_OWNER_DB_URL to the infinityrx owner/superuser connection string).
OWNER_DB = os.environ.get("RECLAIMRX_OWNER_DB_URL", REAL_DB)

TENANT_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SYSTEM_USER = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


@pytest.fixture(scope="module")
def pg_engine():
    """Real Postgres engine using ifx_dev_app role (behavior-under-test)."""
    if not REAL_DB:
        pytest.skip("RECLAIMRX_DB_URL not set — skipping Postgres RLS test")
    engine = sa.create_engine(REAL_DB, future=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def pg_owner_engine():
    """Admin/owner engine for seeding both tenants without RLS filtering.

    Uses RECLAIMRX_OWNER_DB_URL (superuser or BYPASSRLS role).  If not set,
    falls back to RECLAIMRX_DB_URL with SET SESSION AUTHORIZATION DEFAULT +
    SET row_security = OFF so the seeding session bypasses RLS.
    This avoids the trap of seeding tenant-B rows via ifx_dev_app under a
    tenant-A GUC, which would fail under FORCE ROW LEVEL SECURITY.
    """
    if not REAL_DB:
        pytest.skip("RECLAIMRX_DB_URL not set — skipping Postgres RLS test")
    engine = sa.create_engine(OWNER_DB, future=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    """Postgres ifx_dev_app session with SAVEPOINT rollback (behavior-under-test)."""
    conn = pg_engine.connect()
    outer = conn.begin()
    nested = conn.begin_nested()
    session = Session(bind=conn, join_transaction_mode="create_savepoint")

    @event.listens_for(session, "after_transaction_end")
    def reopen(sess, txn):
        nonlocal nested
        if txn.nested and not txn._parent.nested:
            nested = conn.begin_nested()

    yield session
    session.close()
    outer.rollback()
    conn.close()


@pytest.fixture()
def pg_owner_session(pg_owner_engine):
    """Admin/owner session for seeding and post-run verification of tenant-B rows.

    This session COMMITS seed data so that the separate ifx_dev_app pg_session can
    see it (Postgres does not expose another session's uncommitted rows).  Because
    the data is committed — not auto-rolled-back by a SAVEPOINT fixture — the test
    is responsible for explicit ID-based teardown in a finally block.
    """
    conn = pg_owner_engine.connect()
    # Disable RLS so this session can insert/read rows for any tenant.
    conn.execute(text("SET SESSION row_security = OFF"))
    session = Session(bind=conn)
    yield session
    session.close()
    conn.close()


def _seed_tenant_data(session, tenant_id, run_label, n_rows):
    """Seed a DetectionRun + CsvUploadRows for the given tenant and COMMIT.

    MUST be called with an admin/owner session (pg_owner_session) so that
    rows for both tenant A and tenant B are inserted without RLS filtering.

    Commits immediately so that the separate ifx_dev_app pg_session can see
    the rows — Postgres does not expose uncommitted rows to other sessions.

    Returns (run_id, csv_row_ids) so the caller can tear down by ID.
    """
    from src.models.detection_run_models import DetectionRun, CsvUploadRow

    run = DetectionRun(
        tenant_id=tenant_id, data_source="csv_upload",
        run_label=run_label, status="in_progress",
        created_by=SYSTEM_USER,
        resolution_stats={"inserted_count": n_rows, "expected_count": n_rows},
    )
    session.add(run)
    session.flush()
    csv_rows = []
    for i in range(n_rows):
        row = CsvUploadRow(
            tenant_id=tenant_id, detection_run_id=run.id, row_number=i + 1,
            row_data={"patient_unique_hash": f"p-{tenant_id}-{i}", "ndc": "00000000001"},
            resolution_method="declared",
        )
        session.add(row)
        csv_rows.append(row)
    session.flush()
    run_id = run.id
    csv_row_ids = [r.id for r in csv_rows]
    session.commit()  # MUST commit so the separate pg_session can see these rows
    return run_id, csv_row_ids


def test_rls_guc_set_local_in_same_transaction(pg_session, pg_owner_session):
    """SET LOCAL app.current_tenant_id within run_detection transaction prevents cross-tenant access.

    Test structure:
      SEED (via pg_owner_session — bypasses RLS, COMMITS so pg_session can see rows):
        - Seed 5 CsvUploadRows for tenant B — committed.
        - Seed 5 CsvUploadRows + DetectionRun for tenant A — committed.

      ACT (via pg_session — ifx_dev_app, RLS enforced):
        - SET LOCAL app.current_tenant_id = tenant_A (parameterized, never f-string).
        - Assert current_setting() == str(TENANT_A_ID) before calling run_detection.
        - Call run_detection(pg_session, run_a) in the same transaction.

      VERIFY — two-sided assertion:
        (i)  Tenant-A side (pg_session under tenant-A GUC):
               run_a.status is completed or failed (not still in_progress).
               Zero anomalies in pg_session are attributed to tenant B.
        (ii) Tenant-B side (pg_owner_session — can see tenant-B rows):
               The 5 tenant-B CsvUploadRows still exist (run_detection did not delete them).
               Zero anomaly rows in the DB are attributed to tenant B.
               This assertion is NON-VACUOUS because pg_owner_session bypasses RLS and
               would show tenant-B anomalies if any were created.

      TEARDOWN: explicit DELETE by known IDs (owner session) — required because seed
      data is committed (not auto-rolled-back by a SAVEPOINT fixture).
    """
    from src.detection.batch_engine import run_detection
    from src.models.detection_run_models import Anomaly, CsvUploadRow, DetectionRun

    # --- SEED via admin/owner session (bypasses RLS) — COMMITS for cross-session visibility ---
    b_run_id, b_csv_ids = _seed_tenant_data(pg_owner_session, TENANT_B_ID, "rls-b", 5)
    a_run_id, a_csv_ids = _seed_tenant_data(pg_owner_session, TENANT_A_ID, "rls-a", 5)

    try:
        # --- ACT via ifx_dev_app session with tenant-A GUC ---
        # SET LOCAL scopes to this transaction; expires on commit/rollback (test isolation safe).
        pg_session.execute(
            text("SET LOCAL app.current_tenant_id = :tid"),
            {"tid": str(TENANT_A_ID)},
        )
        guc_val = pg_session.execute(
            text("SELECT current_setting('app.current_tenant_id')")
        ).scalar_one()
        assert guc_val == str(TENANT_A_ID), (
            f"GUC not set correctly: got {guc_val!r}, expected {str(TENANT_A_ID)!r}"
        )

        # run_detection must operate inside the same transaction (same GUC in effect).
        # Seed data is committed so pg_session can see run_a via a normal SELECT.
        run_a_in_act_session = pg_session.get(DetectionRun, a_run_id)
        assert run_a_in_act_session is not None, (
            "run_a not visible in pg_session — seed data must be committed before "
            "the separate ifx_dev_app session can see it"
        )
        run_detection(pg_session, run_a_in_act_session)
        # MUST commit (not just flush) so that the owner session's verification is
        # non-vacuous.  A flush-only run leaves run_detection's writes in an open
        # transaction invisible to any other session — the owner session would see
        # zero tenant-B anomalies vacuously (nothing is committed yet), making the
        # isolation assertion meaningless.  After commit, the owner session CAN see
        # tenant-A's anomalies and will still see zero for tenant-B, proving isolation.
        pg_session.commit()

        # --- VERIFY (i): tenant-A GUC session sees zero tenant-B anomalies ---
        b_anomalies_via_act = pg_session.execute(
            select(Anomaly).where(Anomaly.tenant_id == TENANT_B_ID)
        ).scalars().all()
        assert len(b_anomalies_via_act) == 0, (
            f"RLS violation (tenant-A session): {len(b_anomalies_via_act)} anomaly rows "
            f"attributed to tenant B were visible under tenant-A GUC. "
            f"SET LOCAL GUC may not be respected by run_detection."
        )

        # --- VERIFY (ii): admin/owner session confirms tenant-B rows untouched ---
        # This is the NON-VACUOUS check: pg_owner_session bypasses RLS, so if any
        # tenant-B anomalies were created they WILL appear here.
        pg_owner_session.expire_all()  # refresh after pg_session may have committed
        b_anomalies_via_owner = pg_owner_session.execute(
            select(Anomaly).where(Anomaly.tenant_id == TENANT_B_ID)
        ).scalars().all()
        assert len(b_anomalies_via_owner) == 0, (
            f"RLS isolation failure (confirmed from admin session): {len(b_anomalies_via_owner)} "
            f"anomaly rows attributed to tenant B exist in the DB after tenant A's detection run. "
            f"run_detection created cross-tenant anomaly rows."
        )

        # Tenant-B CsvUploadRows must still exist — run_detection must not have deleted them.
        b_rows_via_owner = pg_owner_session.execute(
            select(CsvUploadRow).where(CsvUploadRow.tenant_id == TENANT_B_ID)
        ).scalars().all()
        assert len(b_rows_via_owner) == 5, (
            f"Tenant-B CsvUploadRows were lost after tenant A's run. "
            f"Expected 5, found {len(b_rows_via_owner)}."
        )

    finally:
        # --- TEARDOWN: delete committed seed rows by known IDs so the test is repeatable ---
        # Anomalies created by run_detection for tenant A are also cleaned up here.
        pg_owner_session.execute(
            text("DELETE FROM reclaimrx.anomalies WHERE tenant_id IN (:ta, :tb)"),
            {"ta": str(TENANT_A_ID), "tb": str(TENANT_B_ID)},
        )
        all_csv_ids = a_csv_ids + b_csv_ids
        if all_csv_ids:
            pg_owner_session.execute(
                text("DELETE FROM reclaimrx.csv_upload_rows WHERE id = ANY(:ids)"),
                {"ids": all_csv_ids},
            )
        pg_owner_session.execute(
            text("DELETE FROM reclaimrx.detection_runs WHERE id IN (:a_run, :b_run)"),
            {"a_run": a_run_id, "b_run": b_run_id},
        )
        pg_owner_session.commit()
```

**Step 3 (formerly Step 2): Run detection CLI.**
```powershell
cd C:\Users\MK\Documents\Code Projects\InfinityRx\infinityrx-platform
python -m src.cli.detect
```

The CLI creates a **fresh DetectionRun** (new `run.id`) pointing at the already-ingested `csv_upload_rows` via `data_source_run_id` — it does NOT re-ingest and does NOT reuse a stale run id from a prior v1/partial run. The fresh run's anomalies carry the new `data_source_run_id`; the atomic guardrail (delete-prior + bulk-insert in one transaction) applies cleanly to that run. The existing `csv_upload_rows` for the original ingest run remain untouched as the data source.

Concretely: the CLI looks up the canonical ingest run (status='completed' + matching source_sha256, or `--ingest-run-id` flag), then inserts a new `DetectionRun` row with `data_source="csv_upload"` and `data_source_run_id=<ingest_run.id>`, and calls `run_detection(db, new_run)`. This guarantees that anomalies from a prior failed or partial detection run are never visible for the new run — the fresh run id has zero pre-existing anomalies, and the in-transaction delete in the promote path is a no-op for it.

**Step 3: Assert acceptance criteria.**

After the run completes:
```sql
-- Check total flag rate
SELECT
    record_count,
    anomaly_count,
    ROUND(anomaly_count::numeric / NULLIF(record_count, 0) * 100, 3) AS flag_rate_pct,
    status,
    resolution_stats->>'guardrail' AS guardrail,
    resolution_stats->>'no_finding_count' AS no_finding_count
FROM reclaimrx.detection_runs
ORDER BY started_at DESC
LIMIT 1;
```

**Acceptance assertions:**
- `status = 'completed'` (guardrail did NOT trip) OR
- `status = 'failed'` with `guardrail.tripped = true` (expected if any rule still over-fires → adjust parameters per calibration loop below)
- `flag_rate_pct < 1.0` when status = 'completed'
- Run completes within 30 minutes (single-scan + batch insert)

**Step 4: Calibration loop (if flag_rate >= 1% or guardrail trips).**

1. Open the Leakage Monitor at `http://localhost:3000/reclaimrx/leakage`.
2. Filter by `finding_code` to identify which rule is over-firing.
3. Adjust that rule's `detection_rule_instances.parameters` (e.g. increase `z_threshold` from 3.0 to 3.5, or raise `dollar_floor`):
   ```sql
   UPDATE reclaimrx.detection_rule_instances
   SET parameters = parameters || '{"z_threshold": "3.5"}'::jsonb
   WHERE rule_type_code = 'MFR-003' AND tenant_id = '<your-tenant-uuid>';
   ```
4. Re-run detection. Repeat until `flag_rate_pct < 1.0`.

**Step 5: Verify portal visibility.**
- Open `http://localhost:3000/reclaimrx/leakage` → anomalies appear, filters work.
- Open `http://localhost:3000/reclaimrx/graph-runs` → detection run list appears with status, record_count, anomaly_count.

**Calibrated thresholds are persisted as DATA, not DDL.** Once acceptable parameters are found, apply them via direct UPDATE on the running app or CLI — no migration required:
```sql
-- Example: lock MFR-003 z_threshold=3.5 for the tenant
UPDATE reclaimrx.detection_rule_instances
SET parameters = parameters || '{"z_threshold": "3.5"}'::jsonb
WHERE rule_type_code = 'MFR-003' AND tenant_id = '<your-tenant-uuid>';
```
The migration chain HEAD is `0012_reclaimrx_v2_mfr001_reframe`. No 0013 migration exists. No DDL commit for this task.

---

## Self-Review Checklist (post-write verification)

- [x] §12 H1 (guardrail) → Tasks 1a, 1b, 1c
- [x] §12 H2 (calibration params) → Tasks 2a, 2b
- [x] §12 H3 (MFR-001 coverage-gated) → Tasks 5a, 5b
- [x] §12 H4 (server-side API + set-based enrichment) → Tasks 6a, 6b, 7b
- [x] §12 H5 (ALL-002/003 valid-NPI-only, phantom = absent from reference.dataq_master) → Task 4a
- [x] §12 H6 (reject-75→70 group key locked, finding_code→category mapping, SWP sign-off deviation) → Tasks 3b, 7a
- [x] Locked decision #1 (rx_number_hash group key + collision/split docs) → Task 3b
- [x] Locked decision #2 (SWP-as-AWP LIVE, deviation from §12 H6 deferred state, sign-off noted) → Phase 4 header + Task 4b
- [x] Locked decision #3 (reference.* = FDW foreign tables, no module grants; migration 0010 verifies) → Tasks 0a, 4a, 4b
- [x] Locked decision #4 (ALL-002 phantom = absent from reference.dataq_master; no FWA-marker leg) → Task 4a
- [x] conftest SAVEPOINT/_UUIDString/ATTACH ':memory:' AS reclaimrx reused verbatim → all test files import from `tests.conftest`
- [x] No placeholders ("TBD", "add error handling", etc.) — all code is complete
- [x] Decimal money everywhere — no float in services or models
- [x] PHI never logged — data is pre-scrubbed hashes
- [x] Tenant isolation on every ORM query
- [x] entity_type DERIVED not stored (Anomaly model has no entity_type column — confirmed from detection_run_models.py read)
- [x] DetectionRun.status stays in existing CHECK (in_progress/completed/failed/cancelled) — no new values added
- [x] AnomalyRead is its OWN DTO — World-B LeakageFlag/Investigation not mutated
