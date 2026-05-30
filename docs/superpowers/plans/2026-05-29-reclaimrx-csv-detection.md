# ReclaimRx CSV Detection-Run Backfill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the 2.6M-row PHI-scrubbed historical claims CSV into the migrated-but-unimplemented World-A `reclaimrx` schema and run the FWA detection rules the data supports, producing `anomalies`, via a backend CLI.

**Architecture:** Finish the World-A schema (ORM + rule-type catalog), load the CSV once into `csv_upload_rows` (single read, chunked, idempotent), then run set-based two-pass detection (population-separated `baseline_cache` → per-row/group rule evaluation) porting World-B rule logic. CLI-triggered, single tenant, RLS-enforced via the app DB role.

**Tech Stack:** Python 3.13 · SQLAlchemy (sync, for the batch CLI) · Alembic · PostgreSQL 17 (`reclaimrx` schema) · `Decimal` money · pytest (SAVEPOINT + `_UUIDString` fixtures).

**Spec:** `docs/superpowers/specs/2026-05-29-reclaimrx-csv-detection-design.md` (spec-locked, codex L1 PASS).

---

## Reference A — Signed field-semantics table (RESOLVED by row-level reconciliation)

> Reconciliation evidence in commit history; verified on 8 real `Paid` rows. **These are the locked formulas. All money is `Decimal(str(raw))`.**

| Concept | Source column(s) | Basis | Notes |
|---|---|---|---|
| `quantity` | `quantity_dispensed` | — | |
| `extended_wac` (WAC×qty) | `extended_wac` | **TOTAL** | already extended; do NOT divide by qty |
| `drug_awp` (AWP×qty) | `drug_awp` | **TOTAL** | already extended; `ingredient_cost_submitted == drug_awp` in AWP-submitted rows |
| `nq` (net qty cost, total) | `ingredient_cost_paid` | TOTAL | program-paid ingredient cost |
| `dv` (dispensing value) | `dispensing_fee_paid` | TOTAL | |
| `amount_billed` | `ingredient_cost_submitted` | TOTAL | submitted (≈ AWP) |
| `amount_paid` | `total_paid_amt` (== `plan_total_paid_amt`) | TOTAL | program net pay |
| patient copay | `patient_paid_amt` | TOTAL | |
| gross identity | `ingredient_cost_paid + dispensing_fee_paid + sales_tax_paid` | = `plan_total_paid_amt + patient_paid_amt + other_payer_amount` | reconciliation invariant |
| **`nq_to_wac_ratio`** | `(dv + nq) / extended_wac` | ratio | MFR-001 PRD form ((DV+NQ) vs WAC×qty); `None` if `extended_wac == 0` |
| **`dv_to_awp_ratio`** | `dv / drug_awp` | ratio | `None` if `drug_awp == 0` |
| reversal sign | `transaction_code` (B1 bill / B2 reversal), `reversed_check`, `transaction_status` | — | B2 rows carry negative amounts; normalize with `abs()` for ratios, pair B1/B2 for BRR |

**Golden test rows** (Task 3.x asserts these exact ratios):
- ndc=68308066245 qty=45: extended_wac=171.50, icp=186.5, df=0.0 → nq_to_wac=(0+186.5)/171.50=**1.0875** (no flag at 1.10).
- ndc=51862056060 qty=60: extended_wac=1086.62, icp=1101.62, df=0.0 → nq_to_wac=**1.0138** (no flag).
- ndc=51862025801 qty=28: extended_wac=186.19, icp=215.17, df=1.5 → nq_to_wac=(1.5+215.17)/186.19=**1.1637** (FLAG > 1.10).

## Reference B — Live schema facts (do not re-derive)

- Schema `reclaimrx`; tenant `a0000000-0000-0000-0000-000000000001`; CLI DB role `ifx_dev_app` (`rolbypassrls=f`). Never use `infinityrx` (superuser, bypasses RLS).
- `csv_upload_rows.resolved_pharmacy_npi`/`resolved_ndc` = varchar (passthrough); `resolved_client_id`/`resolved_program_id` = UUID (set NULL v1).
- `detection_rule_evaluation_log`: `source_table`/`source_row_id` nullable (per recovered `0005`); CHECK `ck_reclaimrx_eval_log_per_claim_columns = (evaluation_result = 'skipped_inapplicable') OR (source_table IS NOT NULL AND source_row_id IS NOT NULL)`; result enum `{no_finding, finding_raised, error, skipped_inapplicable}`.
- `anomalies` columns: `data_source, data_source_run_id, client_id, program_id, pharmacy_npi, ndc, claim_id, source_table, source_row_id, detection_kind, detection_id, severity, confidence, date_of_service, rx_number, prescriber_npi, days_supply, quantity, amount_paid, amount_billed, finding_code, finding_summary, finding_details(jsonb), status, ...`.
- `detection_rule_types` columns incl. `code, family(A1-A6), requires_baseline, requires_history, deferred_data_feed, deferred_reason, required_data_columns(ARRAY), default_parameters(jsonb), default_severity, default_confidence`.

## File Structure

```
modules/reclaimrx/
  alembic/versions/0005_eval_log_runwide_skips.py        # RESTORE (Phase 0)
  src/models/detection_run_models.py                     # NEW — World-A ORM (Phase 1)
  src/detection/rule_type_registry.py                    # NEW — register_rule_type + 46 catalog (Phase 1)
  src/detection/csv_ingest.py                            # NEW — streaming loader + resolution + idempotency (Phase 2)
  src/detection/batch_engine.py                          # NEW — applicability gate + two-pass eval (Phase 3)
  src/detection/baselines.py                             # NEW — population-separated baseline_cache (Phase 3)
  src/detection/rule_evaluators.py                       # NEW — ported World-B rule logic (Phase 3)
  src/detection/run_summary.py                           # NEW — summary report (Phase 4)
  src/cli/detect.py                                      # NEW — `python -m reclaimrx.detect` (Phase 2/4)
  tests/detection/                                       # NEW — unit + integration + golden + isolation
  tests/detection/fixtures/sample_claims.csv            # NEW — ~50 planted rows
```

---

## Phase 0 — Migration drift reconcile (SURGICAL — World-A branch only)

> **Decision (codex L2 HIGH-001/002/003):** reclaimrx has **no alembic env** → `run_migrations.sh`
> SKIPS it → migrations were applied ad-hoc → dev sits on the **World-A branch** head
> `0008_ml_detector_seed`. The repo head `0008_sp3_extensions` is a **divergent sibling** off
> `0007` that ALTERs World-B public tables (`reclaimrx_investigations` etc.) which **do not exist
> in dev** — so it CANNOT apply to dev. Two missing sources exist as `.pyc` only: `0005` and
> `0008_seed_ml_detector_placeholders` (revision `0008_ml_detector_seed`).
>
> **Surgical scope:** make the repo faithfully represent dev's World-A branch (recover both
> sources), add a reclaimrx alembic env so the World-A chain is runnable/testable on a scratch
> DB, and chain the feature migration off `0008_ml_detector_seed`. **Do NOT stamp dev** (already
> at the correct head). **Do NOT touch `0008_sp3_extensions`** — record the two-head fork + the
> ad-hoc-migration gap as separate tracked tech-debt (`docs/audit/reclaimrx-migration-fork-2026-05-29.md`).
> Feature migrations are applied to dev via the scratch-verified `alembic upgrade` against the
> **World-A head explicitly** (not `head`, which is ambiguous with two heads).

### Task 0.0: Add a reclaimrx alembic env — WITHOUT triggering the global runner

> **Critical (codex L2 HIGH-002/008):** `infrastructure/scripts/run_migrations.sh` discovers a
> module by checking **`$module_dir/alembic.ini`** (i.e. `modules/reclaimrx/alembic.ini`) and runs
> `alembic upgrade head`. With the intentional two-head fork, `upgrade head` is ambiguous and
> would **break the all-modules migration run**. So we must NOT place the config at the module
> root. Put it **inside the alembic dir** (`modules/reclaimrx/alembic/alembic.ini`) where the
> runner's glob does NOT match → reclaimrx stays skipped (status quo, zero regression). The env
> is invoked **explicitly** with `-c modules/reclaimrx/alembic/alembic.ini` for tests + manual
> feature-migration apply, always targeting a **named revision** (never `head`).

**Files:** Create `modules/reclaimrx/alembic/alembic.ini` (NOT module root), `modules/reclaimrx/alembic/env.py`, `modules/reclaimrx/alembic/script.py.mako`

- [ ] **Step 1:** Confirm the runner check: `grep -n 'alembic.ini' infrastructure/scripts/run_migrations.sh` shows `ini="$module_dir/alembic.ini"` (module-root). Our config at `alembic/alembic.ini` is deliberately not discovered.
- [ ] **Step 2:** Copy the env pattern from `modules/billing/alembic/env.py` (same `engine_from_config` offline/online). Set `version_table_schema="reclaimrx"`, `version_table="alembic_version"`, `script_location` = the alembic dir, `target_metadata=None` (upgrade-only for now). Env header documents: "reclaimrx is intentionally excluded from run_migrations.sh until the two-head fork is merged (tech-debt); invoke explicitly with -c and a named revision."
- [ ] **Step 3: Verify it loads** — Run: `python -m alembic -c modules/reclaimrx/alembic/alembic.ini history` → prints the chain without error.
- [ ] **Step 4: Reconcile the second runner (codex L2 round-2 MED):** `tests/integration/conftest.py`
  has its OWN `_MIGRATION_MODULES` list that includes `reclaimrx` (line ~96) and **raises** if a
  member lacks a module-root `alembic.ini` (line ~30), then runs `alembic upgrade head`. This
  fixture is **already non-functional for reclaimrx** (no module-root ini today) and is dormant
  (CI `backend-ci.yml` runs per-module tests, not this root fixture). Remove `reclaimrx` from
  `_MIGRATION_MODULES` with a comment pointing to the migration-fork tech-debt note (it cannot be
  migrated via the standard module-root `upgrade head` pattern until the two heads are merged).
  Do NOT add a module-root `alembic.ini`.
- [ ] **Step 5: Commit** — `git commit -m "chore(reclaimrx): add non-discovered alembic env; exclude reclaimrx from integration migration fixture (fork deferred)"`

### Task 0.1: Restore migration `0005` (fresh-chain-safe)

**Files:** Create `modules/reclaimrx/alembic/versions/0005_eval_log_runwide_skips.py`

- [ ] **Step 1: Write the migration** (recovered from `.pyc`; `0003` does NOT create the CHECK, so use `DROP ... IF EXISTS` so it is safe on both a fresh chain and the already-migrated dev DB)

```python
"""reclaimrx eval log: allow run-wide rows for skipped_inapplicable.

Wave 43 ships skipped_inapplicable as a once-per-run log signal (not per
claim). Relax source_table/source_row_id to NULL and add a CHECK so per-claim
results still fail loudly without those.

Revision ID: 0005_eval_log_runwide_skips
Revises: 0004_baseline_cache
Create Date: 2026-04-27
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = "0005_eval_log_runwide_skips"
down_revision = "0004_baseline_cache"
branch_labels = None
depends_on = None

_TBL = "detection_rule_evaluation_log"
_CK = "ck_reclaimrx_eval_log_per_claim_columns"


def upgrade() -> None:
    op.alter_column(_TBL, "source_table", existing_type=sa.String(64),
                    nullable=True, schema="reclaimrx")
    op.alter_column(_TBL, "source_row_id", existing_type=postgresql.UUID(as_uuid=True),
                    nullable=True, schema="reclaimrx")
    # 0003 did not create this CHECK; IF EXISTS keeps the migration safe on a
    # fresh chain AND idempotent on the already-migrated dev DB.
    op.execute(f"ALTER TABLE reclaimrx.{_TBL} DROP CONSTRAINT IF EXISTS {_CK}")
    op.create_check_constraint(
        _CK, _TBL,
        "(evaluation_result = 'skipped_inapplicable') OR "
        "(source_table IS NOT NULL AND source_row_id IS NOT NULL)",
        schema="reclaimrx",
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE reclaimrx.{_TBL} DROP CONSTRAINT IF EXISTS {_CK}")
    op.alter_column(_TBL, "source_row_id", existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False, schema="reclaimrx")
    op.alter_column(_TBL, "source_table", existing_type=sa.String(64),
                    nullable=False, schema="reclaimrx")
```

- [ ] **Step 2: Commit** — `git commit -m "fix(reclaimrx): restore missing migration 0005 (eval-log run-wide skips)"`

### Task 0.1b: Restore migration `0008_ml_detector_seed`

**Files:** Create `modules/reclaimrx/alembic/versions/0008_seed_ml_detector_placeholders.py`

- [ ] **Step 1: Write the migration** (recovered from `.pyc`; seeds the 5 Wave-44b placeholder detectors that dev already has — needed so a fresh World-A chain reproduces dev exactly)

```python
"""Seed ML detector placeholder rows for Wave 44b detectors.

Revision ID: 0008_ml_detector_seed
Revises: 0007_flagged_npis
Create Date: 2026-04-30
"""
from __future__ import annotations
from alembic import op

revision = "0008_ml_detector_seed"
down_revision = "0007_flagged_npis"
branch_labels = None
depends_on = None

# (detector_name, feature_schema_class, notes) — exact values from dev.
_DETECTORS = [
    ("pharmacy_behavioral_baseline", "reclaimrx.detection.ml.sklearn_detector.PharmacyFeatures",
     "Pharmacy behavioral drift detector (Wave 44b BEHAV-001). Isolation Forest on pharmacy fill-volume, reversal-rate, NDC-mix metrics. Train via POST /admin/reclaimrx/ml/train."),
    ("member_cohort_outlier", "reclaimrx.detection.ml.sklearn_detector.MemberFeatures",
     "Member cohort outlier detector (Wave 44b BEHAV-002). Isolation Forest on member doctor-shopping, quantity-trajectory and drug-mix within cohort. Train via POST /admin/reclaimrx/ml/train."),
    ("prescriber_baseline", "reclaimrx.detection.ml.sklearn_detector.PrescriberFeatures",
     "Prescriber behavioral baseline detector (Wave 44b BEHAV-003). Isolation Forest on prescriber volume, drug-mix and member-count relative to specialty baseline. Train via POST /admin/reclaimrx/ml/train."),
    ("nq_target_clustering", "reclaimrx.detection.ml.sklearn_detector.NqClusterFeatures",
     "NQ target-cluster ML detector (Wave 44b NQ-008). XGBoost classifier identifying claims whose NQ pattern matches a learned maximizer cluster signature. Train via POST /admin/reclaimrx/ml/train."),
    ("reject_resubmit_pattern", "reclaimrx.detection.ml.sklearn_detector.RejectResubmitFeatures",
     "Reject-resubmit pattern ML detector (Wave 44b REJ-003). XGBoost classifier on pharmacy reject-code cycling sequences to identify artificial override attempts. Train via POST /admin/reclaimrx/ml/train."),
]


def upgrade() -> None:
    for name, fclass, notes in _DETECTORS:
        op.execute(
            "INSERT INTO reclaimrx.ml_detector_registry "
            "(detector_name, detector_version, model_artifact_path, feature_schema_class, "
            " is_placeholder, training_metadata, registered_at, updated_at, notes) "
            f"VALUES ('{name}', '0', NULL, '{fclass}', TRUE, '{{}}', now(), now(), "
            f"'{notes.replace(chr(39), chr(39)+chr(39))}') "
            "ON CONFLICT (detector_name) DO NOTHING"
        )


def downgrade() -> None:
    for name, _f, _n in _DETECTORS:
        op.execute(
            f"DELETE FROM reclaimrx.ml_detector_registry WHERE detector_name = '{name}' "
            "AND is_placeholder = TRUE AND model_artifact_path IS NULL"
        )
```

- [ ] **Step 2: Verify two-head reality** — Run: `python -m alembic -c modules/reclaimrx/alembic/alembic.ini heads`
Expected: **TWO heads** — `0008_ml_detector_seed` (World-A, dev's branch) and `0008_sp3_extensions` (World-B, do-not-apply-to-dev). This is the documented fork.

- [ ] **Step 3: Commit** — `git commit -m "fix(reclaimrx): restore missing migration 0008_ml_detector_seed (5 placeholder detectors)"`

### Task 0.2: Verify World-A chain on scratch + data/schema parity vs dev (NO stamp)

**Files:** Create `modules/reclaimrx/scripts/verify_schema_parity.sql`; reports `docs/audit/reclaimrx-schema-parity-2026-05-29.md` + `docs/audit/reclaimrx-migration-fork-2026-05-29.md`

- [ ] **Step 1: Build a clean scratch DB, upgrade to the World-A head explicitly**

```bash
docker exec infinityrx-postgres psql -U infinityrx -c "CREATE DATABASE reclaimrx_scratch;"
DATABASE_URL_SYNC="postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/reclaimrx_scratch" \
  python -m alembic -c modules/reclaimrx/alembic/alembic.ini upgrade 0008_ml_detector_seed   # NOT `head` (two heads); World-A branch only
```
Expected: green upgrade; `reclaimrx` schema present incl. the 5 seeded `ml_detector_registry` rows.

- [ ] **Step 2: Diff scratch vs dev — structure AND catalog data** — over `information_schema.columns`, `pg_constraint` (CHECK defs), `pg_indexes`, `pg_policies`, role grants, AND data rows of `reclaimrx.ml_detector_registry` (expect the same 5) + `reclaimrx.detection_rule_types` (expect 0 in both). Capture deltas in the parity report.
Expected: **zero undocumented deltas**; both at revision `0008_ml_detector_seed`.

- [ ] **Step 3: Document the fork as tech-debt** in `reclaimrx-migration-fork-2026-05-29.md`: the two divergent `0008` heads, the missing alembic env (module skipped by `run_migrations.sh`), the World-B SP-3 branch's incompatibility with dev, and the deferred merge/linearization + runner-inclusion work. **No `alembic stamp` on dev** — it is already at `0008_ml_detector_seed`.

- [ ] **Step 4: Commit** — `git commit -m "chore(reclaimrx): verify World-A schema/data parity; document migration fork as tech-debt"`

---

## Phase 1 — ORM models + rule-type catalog

### Task 1.1: World-A ORM models

**Files:** Create `modules/reclaimrx/src/models/detection_run_models.py`; Test `modules/reclaimrx/tests/detection/test_models_reflect.py`

- [ ] **Step 1: Write failing reflection test**

```python
def test_detection_run_models_match_db(reclaimrx_engine):
    """Every World-A ORM table reflects clean against the migrated schema."""
    from src.models.detection_run_models import DetectionRun, CsvUploadRow, Anomaly, \
        DetectionRuleType, DetectionRuleInstance, DetectionRuleEvaluationLog, BaselineCache
    from sqlalchemy import inspect
    insp = inspect(reclaimrx_engine)
    for model in (DetectionRun, CsvUploadRow, Anomaly, DetectionRuleType,
                  DetectionRuleInstance, DetectionRuleEvaluationLog, BaselineCache):
        cols = {c["name"] for c in insp.get_columns(model.__tablename__, schema="reclaimrx")}
        orm_cols = {c.name for c in model.__table__.columns}
        # Equality (MED-001): catch BOTH ORM-extra columns AND missing-from-ORM columns
        # for owned tables we fully model. (If a server-managed col is intentionally
        # omitted, add it to an explicit per-model allowlist — not a blanket <=.)
        assert orm_cols == cols, f"{model.__tablename__}: ORM≠DB. missing={cols-orm_cols} extra={orm_cols-cols}"
```

- [ ] **Step 2: Run, verify it fails** — Run: `pytest modules/reclaimrx/tests/detection/test_models_reflect.py -v` → FAIL (import error).

- [ ] **Step 3: Implement the ORM classes** mirroring the live DDL in Reference B and the columns captured in the spec. Tenant-owned tables (`DetectionRun`, `CsvUploadRow`, `Anomaly`, `DetectionRuleInstance`, `DetectionRuleEvaluationLog`, `BaselineCache`, `MlTrainingRun`, `FlaggedNpi`, `RecoupCase`, `CaseAssignment`, `CaseAnomalyLink`, `CaseNumberSequence`, `AnomalyAuditLog`) inherit `TenantScopedMixin`; globals (`DetectionRuleType`, `MlDetectorRegistry`) do not. Money columns `sa.Numeric(12,2)`/`Numeric(20,8)`. UUID PKs. `__table_args__ = {"schema": "reclaimrx"}`.

- [ ] **Step 4: Run, verify pass** — Expected: PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): World-A ORM models for detection-run schema"`

### Task 1.2: Rule-type registry + 46-rule catalog with `required_data_columns`

**Files:** Create `modules/reclaimrx/src/detection/rule_type_registry.py`; Test `tests/detection/test_rule_type_registry.py`

- [ ] **Step 1: Write failing test for the catalog + gating metadata**

```python
def test_catalog_seeds_all_rules_with_gating(db):
    from src.detection.rule_type_registry import register_rule_types, RULE_TYPE_CATALOG
    n = register_rule_types(db)
    assert n == len(RULE_TYPE_CATALOG) >= 46
    by_code = {r["code"]: r for r in RULE_TYPE_CATALOG}
    # Bucket A/B run on CSV columns
    assert by_code["MFR-001"]["deferred_data_feed"] is False
    assert "extended_wac" in by_code["MFR-001"]["required_data_columns"]
    assert "ingredient_cost_paid" in by_code["MFR-001"]["required_data_columns"]
    # Bucket C deferred with a reason
    assert by_code["ALL-002"]["deferred_data_feed"] is True
    assert by_code["ALL-002"]["deferred_reason"]
    # family mapped to A1-A6
    assert by_code["MFR-001"]["family"] in {"A1","A2","A3","A4","A5","A6"}
    # idempotent
    assert register_rule_types(db) == 0
```

- [ ] **Step 2: Run, verify fail** — `pytest tests/detection/test_rule_type_registry.py -v` → FAIL.

- [ ] **Step 3: Implement `RULE_TYPE_CATALOG`** — port all 46 from `src/services/detection_rule_seeder.py:PRE_BUILT_RULES`, adding per rule: `family` (map: pricing_integrity→A1, billing_pattern→A2, utilization→A3, eligibility→A4, controlled_substance→A5, network_compliance/340b/workers_comp/duplicate/accumulator→A6 — document the mapping), `required_data_columns` (CSV column names the rule reads — see spec §8 buckets), `deferred_data_feed`+`deferred_reason` for Bucket C, `requires_baseline` true for HP-005/HP-008/MFR-003/MFR-004/ALL-006. `register_rule_types(db)` upserts idempotently into `reclaimrx.detection_rule_types`.

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): rule-type registry + 46-rule catalog with required_data_columns gating"`

### Task 1.3: Instantiate applicable rule instances

**Files:** Modify `rule_type_registry.py` (add `register_rule_instances`); Test extend `test_rule_type_registry.py`

> **ML placeholders are NOT created here (codex L2 HIGH-005):** the 5 detector rows already
> exist in dev (seeded by `0008_ml_detector_seed`, Task 0.1b), and `ml_detector_registry` grants
> the app role `ifx_dev_app` **SELECT only** — an app-role INSERT would fail. No app-role mutation
> of the global detector registry. v1 reads placeholders; it never writes them.

- [ ] **Step 1: Failing test** — given a tenant + available-columns set, `register_rule_instances` creates one `detection_rule_instance` only for rules whose `required_data_columns ⊆ available` AND not `deferred_data_feed`; idempotent on re-run; deferred/inapplicable rules get NO instance.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `register_rule_instances(db, tenant_id, available_columns)` only. (Confirm the 5 ML placeholders are present via a read-only assertion, but do not insert.)
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): create applicable rule instances (ML placeholders pre-seeded via migration)"`

---

## Phase 2 — CSV ingest + entity resolution (single read, idempotent, resumable)

### Task 2.1: Money/date parsing helpers

**Files:** Create `modules/reclaimrx/src/detection/parsing.py`; Test `tests/detection/test_parsing.py`

- [ ] **Step 1: Failing test**

```python
from decimal import Decimal
from datetime import date
def test_parse_money_and_date():
    from src.detection.parsing import parse_money, parse_dos
    assert parse_money("809.80") == Decimal("809.80")
    assert parse_money("") is None
    assert parse_money("-50.0") == Decimal("-50.0")
    assert parse_dos("2024-12-31") == date(2024,12,31)
    assert parse_dos("9999-09-09") is None      # garbage sentinel rejected
    assert parse_dos("") is None
```

- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `parse_money` (`Decimal(str(v))`, None on empty/invalid) and `parse_dos` (valid only within `[date(1990,1,1), date.today()]`, else None).
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): CSV money/date parsing helpers"`

### Task 2.2: Row resolution

**Files:** Create `modules/reclaimrx/src/detection/csv_ingest.py` (add `resolve_row`); Test `tests/detection/test_resolution.py`

- [ ] **Step 1: Failing test**

```python
def test_resolve_row_declared_and_unmapped():
    from src.detection.csv_ingest import resolve_row
    ok = resolve_row({"pharmacy_npi":"1497848832","ndc":"71403000330","client_id":"32"})
    assert ok.resolved_pharmacy_npi == "1497848832"
    assert ok.resolved_ndc == "71403000330"
    assert ok.resolved_client_id is None          # UUID col, no map in v1
    assert ok.resolution_method == "declared"
    bad = resolve_row({"pharmacy_npi":"","ndc":"","client_id":"32"})
    assert bad.resolution_method == "unmapped"
```

- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `resolve_row` returning a dataclass; `declared` when `pharmacy_npi` present, else `unmapped`; `resolved_client_id`/`program_id` always None (raw kept in `row_data`).
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): CSV row entity resolution (declared/unmapped)"`

### Task 2.3: Idempotent run creation (advisory lock + partial unique index)

**Files:** Create migration `modules/reclaimrx/alembic/versions/0009_detection_run_sha_unique.py` (**`down_revision = "0008_ml_detector_seed"`** — the World-A head, NOT sp3); add `create_or_resume_run` to `csv_ingest.py`; Test `tests/detection/test_run_idempotency.py`

- [ ] **Step 1: Failing test** — two `create_or_resume_run` calls with same `(tenant, sha256)` for a completed run → second aborts; a non-terminal run blocks unless `resume=True`; advisory lock serializes concurrent creators. The insert succeeds with required NOT NULL `run_label` + `created_by` populated.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3a: Migration** (chains off the World-A head; apply to dev via `python -m alembic -c modules/reclaimrx/alembic/alembic.ini upgrade 0009_detection_run_sha_unique`)

```python
revision = "0009_detection_run_sha_unique"
down_revision = "0008_ml_detector_seed"   # World-A branch head (NOT 0008_sp3_extensions)

def upgrade() -> None:
    op.create_index("uq_detection_runs_tenant_sha_active", "detection_runs",
        ["tenant_id", "source_sha256"], unique=True, schema="reclaimrx",
        postgresql_where=sa.text("status IN ('in_progress','completed') AND source_sha256 IS NOT NULL"))
```

- [ ] **Step 3b: Implement** `create_or_resume_run(db, *, tenant_id, path, created_by, resume=False, force=False)` — **signature includes `created_by` (HIGH-004:** `detection_runs.run_label` and `created_by` are NOT NULL): compute `source_sha256` + `expected_record_count` (hashing pass); `pg_advisory_xact_lock(hashtext(str(tenant_id)||sha))`; query existing run by `(tenant_id, source_sha256)`; branch on status (completed→abort unless force; in_progress→block unless resume; failed→purge rows then reuse); insert `DetectionRun` with **`run_label`** (deterministic, e.g. `f"{Path(path).name}:{sha[:12]}"`) and **`created_by`** (caller-supplied system/admin UUID); store `expected_record_count` in `resolution_stats`.
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): idempotent detection-run creation (advisory lock + partial unique index)"`

### Task 2.4: Streaming chunked loader + full-coverage gate

**Files:** add `load_csv` to `csv_ingest.py`; Test `tests/detection/test_csv_load.py` + fixture `tests/detection/fixtures/sample_claims.csv`

- [ ] **Step 1: Create the ~50-row fixture CSV** with the real 75-column header and planted: 3 duplicates (same patient/ndc/dos, diff auth), 1 reversal pair (B1+B2), 1 NQ-inflation row (icp/extended_wac>1.10), 2 null-NDC rows, 1 garbage-DOS row, multi-state prescriber set.
- [ ] **Step 2: Failing test**

```python
def test_load_csv_full_coverage(db, tmp_tenant):
    from src.detection.csv_ingest import create_or_resume_run, load_csv
    run = create_or_resume_run(db, tenant_id=tmp_tenant, path="tests/detection/fixtures/sample_claims.csv", created_by=SYS_UID)
    n = load_csv(db, run, chunk_size=10)
    assert n == run.resolution_stats["expected_count"]      # coverage == expected
    assert db.query(CsvUploadRow).filter_by(detection_run_id=run.id).count() == n
    stats = run.resolution_stats
    assert stats["declared"] + stats["unmapped"] == n
```

- [ ] **Step 3: Run fail.**
- [ ] **Step 4: Implement** `load_csv`: stream `csv.DictReader`, 10k chunks, bulk-insert `csv_upload_rows` (`row_number`, `row_data`, resolved cols), aggregate `resolution_stats`; set `inserted_count`; raise if a chunk fails (mark run `failed` in a separate session). Detection callers assert `inserted_count == expected_count`.
- [ ] **Step 5: Run pass; Commit** — `git commit -m "feat(reclaimrx): streaming chunked CSV loader with full-coverage gate"`

---

## Phase 3 — Detection engine (two-pass, set-based)

### Task 3.1: Derived-field computations (the locked financial formulas)

**Files:** Create `modules/reclaimrx/src/detection/rule_evaluators.py` (add `derive_fields`); Test `tests/detection/test_derived_fields.py`

- [ ] **Step 1: Failing test with the golden rows (Reference A)**

```python
from decimal import Decimal
def test_nq_to_wac_golden_rows():
    from src.detection.rule_evaluators import derive_fields
    r = derive_fields({"extended_wac":"186.19","ingredient_cost_paid":"215.17",
                       "dispensing_fee_paid":"1.5","drug_awp":"256.16","quantity_dispensed":"28"})
    assert round(r["nq_to_wac_ratio"], 4) == Decimal("1.1637")     # (1.5+215.17)/186.19
    r2 = derive_fields({"extended_wac":"171.50","ingredient_cost_paid":"186.5",
                        "dispensing_fee_paid":"0.0","drug_awp":"658.36","quantity_dispensed":"45"})
    assert round(r2["nq_to_wac_ratio"], 4) == Decimal("1.0875")
def test_zero_basis_is_none():
    from src.detection.rule_evaluators import derive_fields
    assert derive_fields({"extended_wac":"0","ingredient_cost_paid":"5","dispensing_fee_paid":"0",
                          "drug_awp":"0","quantity_dispensed":"1"})["nq_to_wac_ratio"] is None
```

- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `derive_fields`: `nq=Decimal(icp)`, `dv=Decimal(df)`, `nq_to_wac_ratio=(dv+nq)/extended_wac` (None if extended_wac==0), `dv_to_awp_ratio=dv/drug_awp` (None if 0). Use `abs()` on amounts when `transaction_code=='B2'`. All `Decimal`, `ROUND_HALF_UP` when quantizing.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): derived financial fields with locked WAC/AWP-total semantics"`

### Task 3.2: Ported rule evaluators (threshold/pattern/statistical/comparison/composite)

**Files:** add evaluator fns to `rule_evaluators.py`; Test `tests/detection/test_rule_evaluators.py`

- [ ] **Step 1: Failing tests** for each eval type using `RULE_TYPE_CATALOG` params (threshold MFR-001 flags >1.10; composite ALL-008 OR-fires; statistical compares to a passed baseline value). Mirror World-B `rule_engine.py` semantics + severity bands (`>75 critical, >50 high, >25 medium`).
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `evaluate_threshold/_pattern/_statistical/_comparison/_composite(row_fields, rule_logic, baseline=None)` → `RuleResult(fired, risk_score, severity, confidence, evidence)`. Port `_compare`, `_compute_confidence`, `_confidence_to_risk_score`, `_risk_score_to_severity` from World-B.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): port World-B rule evaluators to batch engine"`

### Task 3.3: Population-separated baselines

**Files:** Create `modules/reclaimrx/src/detection/baselines.py`; Test `tests/detection/test_baselines.py`

**Two distinct separation modes (codex L2 HIGH-007):**
- **Peer-exclusion** (entity vs its peers, excluding itself): `prescriber_peer_volume` (HP-005), `member_cost` percentile (HP-008), `pharmacy_ndc_volume` (MFR-004 — pharmacy vs other pharmacies for that NDC), `pharmacy_weekday_volume` (ALL-006).
- **Own prior-period** (entity vs its OWN history, excluding the current claim/window): **`pharmacy_own_rate_history` (MFR-003** — "pharmacy rate deviates from *their own* historical baseline", NOT a peer comparison).

- [ ] **Step 1: Failing tests** —
  - `compute_baseline(db, run, kind="prescriber_peer_volume")` → each entity's mean/stddev **excludes its own rows**; `extra.exclusion=="leave_entity_out"`, `peer_count`, `min_sample_count` enforced (below it → no baseline row → rule does not fire).
  - `compute_baseline(db, run, kind="pharmacy_own_rate_history")` → MFR-003 baseline is the pharmacy's OWN historical rate **excluding the scored claim/current window** (`extra.exclusion=="own_prior_period"`), NOT peer stats.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** baselines via **aggregate-subtraction, never O(n²) correlated subqueries (MED-003):** first compute per-group totals (`SUM`, `SUM(x^2)`, `COUNT`) with a single GROUP BY; derive each entity's leave-one-out peer mean/stddev by **subtracting the entity's own aggregates from the group totals** (peer_mean = (group_sum − entity_sum)/(group_n − entity_n); peer_var via the sum-of-squares identity). For `pharmacy_own_rate_history`, window by prior period per `(pharmacy_npi, ndc)`. Require indexes on `(detection_run_id, resolved_pharmacy_npi, resolved_ndc)` and DOS. Upsert `baseline_cache` keyed `(tenant, kind, scope_key, window_days, data_source)` with provenance in `extra`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): population-separated baselines (peer-exclusion + own-prior-period, aggregate-subtraction)"`

### Task 3.4: Applicability gate + run-wide skip logging

**Files:** Create `modules/reclaimrx/src/detection/batch_engine.py` (add `gate_rules`); Test `tests/detection/test_applicability_gate.py`

- [ ] **Step 1: Failing test** — given available CSV columns, `gate_rules` returns applicable instances and writes one `detection_rule_evaluation_log` row per deferred/inapplicable rule with `evaluation_result='skipped_inapplicable'`, `source_table=None`, `source_row_id=None`; asserts the CHECK accepts it.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `gate_rules(db, run, available_columns)`: for each enabled instance, applicable iff `required_data_columns ⊆ available` and not `deferred_data_feed`; else log run-wide skip.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): rule applicability gate + run-wide skip log"`

### Task 3.5: Detection passes + anomaly persistence (incl. lifecycle-aware grouping)

**Files:** add `run_detection` to `batch_engine.py`; Test `tests/detection/test_detection_passes.py`

- [ ] **Step 1: Failing tests** (use the fixture): ALL-001 flags the 3 planted duplicates but **not** the legitimate reversal pair; MFR-002 flags the higher-NQ rebill only; MFR-001 flags the inflation row; deferred rules produce zero anomalies; `anomaly_count` updated. Lifecycle filter: exclude `transaction_status='Reversed'`/`'Duplicate'` rows from being counted as the *primary* anomaly except where the rule targets them.
- [ ] **Step 2: Run fail.**
**Exact grouping keys + lifecycle filters (codex L2 MED-002):**
- **ALL-001 Duplicate:** group key = `(resolved_client_id_raw, patient_unique_hash, resolved_ndc, date_of_service)`; consider only **paid billing** rows (`transaction_code='B1'` AND `transaction_status='Paid'`); flag when ≥2 **distinct `auth_no_hash`** in a group. Do NOT count rows already tagged `transaction_status='Duplicate'` or `'Reversed'` as the primary anomaly (they are lifecycle artifacts, not the finding).
- **MFR-002 Bill-Reverse-Rebill:** group key = `(patient_unique_hash, resolved_pharmacy_npi, resolved_ndc)`; order rows by `date_added_timestamp`; detect a `B1`(paid) → `B2`(reversal, `reversed_check='Yes'`) → `B1`(paid) sequence within 14 days where the rebill `nq` (abs) > the original `nq` (abs). Sign-normalize B2 amounts with `abs()`. Flag only the higher-NQ **rebill** row.
- General: amounts compared on the locked `nq`/`extended_wac` basis (Reference A); reversed rows use `abs()`.

- [ ] **Step 3: Implement** `run_detection(db, run)`: Pass 1 baselines (Task 3.3) for applicable baseline rules; Pass 2 — single-row rules via batched scan computing `derive_fields`; grouping rules via the GROUP BY/window queries with the **exact keys + lifecycle filters above**; statistical rules vs `baseline_cache`. Insert `anomalies` (Reference B columns: `finding_code`, `finding_summary`, `finding_details`, snapshot fields, `detection_kind='rule'`, `detection_id`=instance, `data_source_run_id`=run). Log `finding_raised`+`error` per row only; aggregate `no_finding` counts. Update `detection_runs.anomaly_count`/`record_count`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): two-pass detection + lifecycle-aware grouping + anomaly persistence"`

---

## Phase 4 — CLI + summary

### Task 4.1: Run summary

**Files:** Create `modules/reclaimrx/src/detection/run_summary.py`; Test `tests/detection/test_run_summary.py`

- [ ] **Step 1: Failing test** — `build_summary(db, run)` returns counts: rows in/declared/unmapped, rules applied vs deferred, anomalies by code/family/severity, top pharmacies/prescribers, total `$ at risk` (`Decimal`).
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** aggregation queries; finalize run `status='completed'`, `completed_at`, `resolution_stats`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): detection-run summary report"`

### Task 4.2: CLI entrypoint with its own RLS-enforced sync session

**Files:** Create `modules/reclaimrx/src/cli/__init__.py` + `modules/reclaimrx/src/cli/detect.py`; Test `tests/detection/test_cli_and_isolation.py`

> **Package + invocation (codex L2 HIGH-006):** the module's package root is `src` (no
> `reclaimrx/` package). Invoke as **`python -m src.cli.detect`** with
> `PYTHONPATH=modules/reclaimrx` (the same pattern `start-all-services.ps1` uses). NOT
> `python -m reclaimrx.detect`.
>
> **Session (codex L2 #8 / L1 #5):** shared `shared/db/session.py` is **async-only** and its
> `install_tenant_loader` filters at the **ORM layer via the `infinityrx_current_tenant_id`
> ContextVar** — it does NOT set the Postgres GUC, and it does NOT cover the raw SQL this batch
> job uses. So the CLI builds its **own sync `create_engine`** on the `ifx_dev_app` role and is
> responsible for ALL of:
>   1. `SET LOCAL app.current_tenant_id = '<tenant>'` at the start of **every transaction** (the
>      GUC the `0002` RLS policy reads: `tenant_id = NULLIF(current_setting('app.current_tenant_id', true),'')::uuid`). Without it, RLS returns/permits **zero rows** for the non-BYPASSRLS role.
>   2. set the `current_tenant_id` ContextVar (belt-and-suspenders for any ORM op).
>   3. set `tenant_id` **explicitly on every INSERT** (no ORM loader auto-fills it on the sync path).

- [ ] **Step 1: Failing tests** —
  - **End-to-end:** `run_detect(file, tenant, created_by)` on the fixture → run completed, expected anomaly counts, summary printed.
  - **Isolation:** a sync engine on `ifx_dev_app` (non-BYPASSRLS). Seed tenant A via the CLI, then with `SET LOCAL app.current_tenant_id = TENANT_B` assert zero rows; with the GUC unset assert zero rows (RLS denies).

```python
def test_cli_tenant_isolation(app_role_engine):  # app_role_engine = ifx_dev_app, NOT infinityrx
    run_detect("tests/detection/fixtures/sample_claims.csv", tenant=TENANT_A, created_by=SYS_UID, engine=app_role_engine)
    with app_role_engine.begin() as c:
        c.execute(text("SET LOCAL app.current_tenant_id = :t"), {"t": str(TENANT_B)})
        assert c.execute(text("SELECT count(*) FROM reclaimrx.anomalies")).scalar() == 0
    with app_role_engine.begin() as c:  # GUC unset → RLS denies
        assert c.execute(text("SELECT count(*) FROM reclaimrx.anomalies")).scalar() == 0
```

- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `detect.py`: argparse `--file --tenant [--created-by] [--resume] [--force]`; build the sync `create_engine` on `ifx_dev_app`; a `tenant_txn(engine, tenant_id)` context manager that opens a transaction, runs `SET LOCAL app.current_tenant_id`, sets the ContextVar; orchestrate Phase 1 `register_rule_types`+`register_rule_instances` → Phase 2 `create_or_resume_run`+`load_csv` (full-coverage gate) → Phase 3 `gate_rules`+`run_detection` → Phase 4 `build_summary`; structured errors; mark run `failed` (separate txn) on exception.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): detect CLI (own sync RLS session) + isolation test"`

### Task 4.3: Full-file dry-run validation (manual gate, not a unit test)

- [ ] **Step 1:** Apply the `0009` migration to dev first: `python -m alembic -c modules/reclaimrx/alembic/alembic.ini upgrade 0009_detection_run_sha_unique`. Then run `set PYTHONPATH=modules\reclaimrx && python -m src.cli.detect --file "data/ReclaimRx/allDataMinusPHI 1.csv" --tenant a0000000-0000-0000-0000-000000000001 --created-by <system-uuid>` against dev DB.
- [ ] **Step 2:** Confirm: run completes, ~2.6M `csv_upload_rows`, anomalies populated, summary sane (duplicates/reversals/inflation counts plausible vs the 209k Duplicate / 448k Reversed profile), wall-time recorded. Document results in `docs/audit/reclaimrx-first-run-2026-05-29.md`.
- [ ] **Step 3: Commit** the run report.

---

## Self-Review

**Spec coverage:** D1 (Phase 1), D2 (Phase 0.0–0.2), D3 (4.2), D4 (2.2), D5 (1.2/3.4), D6 (3.3/3.5), D7 (ML pre-seeded via 0.1b; not app-written), D8 (4.1), D9 (2.4/3.5), D10 (4.2), D11 (0.1/3.4), D12 (2.3), D13 (3.3) — all mapped. §7 financial gate → resolved in Reference A + Task 3.1 golden tests. Codex L1 #1–9 → Tasks 0.1/0.2, 2.2, 3.1, 3.3, 4.2, 3.4, 2.3, 3.5, 2.4.

**Codex L2 coverage:** HIGH-001 (0.1 fresh-chain-safe DROP IF EXISTS), HIGH-002 (0.0 alembic env), HIGH-003 (0.1b recover seed + 0.2 data-diff, no stamp), HIGH-004 (2.3 `created_by`+`run_label`), HIGH-005 (1.3 ML not app-written; 0.1b seeds via migration), HIGH-006 (4.2 `python -m src.cli.detect` + own sync engine), HIGH-007 (3.3 own-prior-period MFR-003 vs peer-exclusion), MED-001 (1.1 `==`), MED-002 (3.5 exact keys), MED-003 (3.3 aggregate-subtraction). LOW-001 golden ratios confirmed correct.

**Placeholder scan:** financial formulas concrete (Reference A); ORM mirrors Reference B; no "TBD". The ORM column list defers to Reference B/live DDL rather than retyping 15 tables — acceptable (DDL is source of truth, reflection test enforces match).

**Type consistency:** `RuleResult`, `derive_fields` keys (`nq_to_wac_ratio`, `dv_to_awp_ratio`), `create_or_resume_run`, `load_csv`, `gate_rules`, `run_detection`, `build_summary`, `run_detect` — names consistent across tasks.

## Out of scope (v1)
Portal UI · recoup-case workflow · ML scoring/training · graph analysis · ~31–33 deferred rules · event-bus ingestion · multi-tenant ingest.
