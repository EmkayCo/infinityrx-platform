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

## Phase 0 — Migration drift reconcile

### Task 0.1: Restore migration `0005`

**Files:** Create `modules/reclaimrx/alembic/versions/0005_eval_log_runwide_skips.py`

- [ ] **Step 1: Write the migration (exact recovered content)**

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

from alembic import op

revision = "0005_eval_log_runwide_skips"
down_revision = "0004_baseline_cache"
branch_labels = None
depends_on = None

_CK = "ck_reclaimrx_eval_log_per_claim_columns"


def upgrade() -> None:
    op.alter_column("detection_rule_evaluation_log", "source_table",
                    existing_type=__import__("sqlalchemy").String(64),
                    nullable=True, schema="reclaimrx")
    op.alter_column("detection_rule_evaluation_log", "source_row_id",
                    existing_type=__import__("sqlalchemy").dialects.postgresql.UUID(as_uuid=True),
                    nullable=True, schema="reclaimrx")
    op.drop_constraint(_CK, "detection_rule_evaluation_log", schema="reclaimrx", type_="check")
    op.create_check_constraint(
        _CK, "detection_rule_evaluation_log",
        "(evaluation_result = 'skipped_inapplicable') OR "
        "(source_table IS NOT NULL AND source_row_id IS NOT NULL)",
        schema="reclaimrx",
    )


def downgrade() -> None:
    op.drop_constraint(_CK, "detection_rule_evaluation_log", schema="reclaimrx", type_="check")
    op.create_check_constraint(
        _CK, "detection_rule_evaluation_log",
        "source_table IS NOT NULL AND source_row_id IS NOT NULL",
        schema="reclaimrx",
    )
    op.alter_column("detection_rule_evaluation_log", "source_row_id",
                    existing_type=__import__("sqlalchemy").dialects.postgresql.UUID(as_uuid=True),
                    nullable=False, schema="reclaimrx")
    op.alter_column("detection_rule_evaluation_log", "source_table",
                    existing_type=__import__("sqlalchemy").String(64),
                    nullable=False, schema="reclaimrx")
```
*(Clean up the inline `__import__` to top-level `import sqlalchemy as sa` / `from sqlalchemy.dialects import postgresql` imports — shown inline only to keep the constraint definitions unambiguous.)*

- [ ] **Step 2: Verify chain integrity**

Run: `cd modules/reclaimrx && python -m alembic history` and `python -m alembic heads`
Expected: linear history through `0008_sp3_extensions`; **single head**; `0006` `down_revision` resolves to `0005`.

- [ ] **Step 3: Commit**

```bash
git add modules/reclaimrx/alembic/versions/0005_eval_log_runwide_skips.py
git commit -m "fix(reclaimrx): restore missing migration 0005 (eval-log run-wide skips)"
```

### Task 0.2: Schema-diff scratch vs live + reconcile fork

**Files:** Create `modules/reclaimrx/scripts/verify_schema_parity.sql` (diff queries) + a short report `docs/audit/reclaimrx-schema-parity-2026-05-29.md`

- [ ] **Step 1: Build a clean scratch DB and upgrade**

Run:
```bash
docker exec infinityrx-postgres psql -U infinityrx -c "CREATE DATABASE reclaimrx_scratch;"
cd modules/reclaimrx && DATABASE_URL_SYNC="postgresql://infinityrx:infinityrx_bootstrap@localhost:5432/reclaimrx_scratch" python -m alembic upgrade head
```
Expected: green `upgrade head`.

- [ ] **Step 2: Diff tables/columns/constraints/indexes/RLS/grants**

Run a diff over `information_schema.columns`, `pg_constraint` (CHECK defs), `pg_indexes`, `pg_policies`, and role grants between `reclaimrx_scratch.reclaimrx` and `infinityrx_dev.reclaimrx`. Capture deltas in the report.
Expected: **zero undocumented deltas** (the only known intentional difference is the `alembic_version` stamp).

- [ ] **Step 3: Reconcile the stamp fork**

If schema parity holds, stamp dev to repo head (the dev stamp `0008_ml_detector_seed` is a renamed lineage):
```bash
DATABASE_URL_SYNC="postgresql://ifx_dev_app:dev_password@localhost:5432/infinityrx_dev" python -m alembic -c modules/reclaimrx/alembic.ini stamp 0008_sp3_extensions
```
Only run this AFTER Step 2 shows parity. If a real delta exists, author a corrective migration instead and document it.

- [ ] **Step 4: Verify upgrade from the dev stamp + one-step downgrade on a copy**

Clone dev schema to a scratch, confirm `upgrade head` is a no-op and `downgrade -1`/`upgrade +1` round-trips cleanly.

- [ ] **Step 5: Commit**

```bash
git add modules/reclaimrx/scripts/verify_schema_parity.sql docs/audit/reclaimrx-schema-parity-2026-05-29.md
git commit -m "chore(reclaimrx): verify World-A schema parity + reconcile alembic stamp"
```

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
        assert orm_cols <= cols, f"{model.__tablename__}: ORM has columns not in DB: {orm_cols - cols}"
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

### Task 1.3: Instantiate applicable rule instances + ML placeholders

**Files:** Modify `rule_type_registry.py` (add `register_rule_instances`, `register_ml_placeholders`); Test extend `test_rule_type_registry.py`

- [ ] **Step 1: Failing test** — given a tenant + available-columns set, instances created only for rules whose `required_data_columns ⊆ available` and not deferred; ML placeholders have `is_placeholder=True`.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `register_rule_instances(db, tenant_id, available_columns)` and `register_ml_placeholders(db)` (rows `pharmacy_behavioral_baseline`, `claim_risk_xgb` with `is_placeholder=True`, no artifact).
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): create applicable rule instances + ML placeholder registry"`

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

**Files:** Create migration `modules/reclaimrx/alembic/versions/0009_detection_run_sha_unique.py`; add `create_or_resume_run` to `csv_ingest.py`; Test `tests/detection/test_run_idempotency.py`

- [ ] **Step 1: Failing test** — two `create_or_resume_run` calls with same `(tenant, sha256)` for a completed run → second aborts; a non-terminal run blocks unless `resume=True`; advisory lock serializes concurrent creators.
- [ ] **Step 2: Run fail.**
- [ ] **Step 3a: Migration** — partial unique index:

```python
def upgrade() -> None:
    op.create_index("uq_detection_runs_tenant_sha_active", "detection_runs",
        ["tenant_id", "source_sha256"], unique=True, schema="reclaimrx",
        postgresql_where=sa.text("status IN ('in_progress','completed') AND source_sha256 IS NOT NULL"))
```

- [ ] **Step 3b: Implement** `create_or_resume_run(db, tenant_id, path)`: `pg_advisory_xact_lock(hashtext(tenant||sha))`, then query existing run, branch on status, insert `detection_run` with `expected_record_count` stored in `resolution_stats`.
- [ ] **Step 4: Run pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(reclaimrx): idempotent detection-run creation (advisory lock + partial unique index)"`

### Task 2.4: Streaming chunked loader + full-coverage gate

**Files:** add `load_csv` to `csv_ingest.py`; Test `tests/detection/test_csv_load.py` + fixture `tests/detection/fixtures/sample_claims.csv`

- [ ] **Step 1: Create the ~50-row fixture CSV** with the real 75-column header and planted: 3 duplicates (same patient/ndc/dos, diff auth), 1 reversal pair (B1+B2), 1 NQ-inflation row (icp/extended_wac>1.10), 2 null-NDC rows, 1 garbage-DOS row, multi-state prescriber set.
- [ ] **Step 2: Failing test**

```python
def test_load_csv_full_coverage(db, tmp_tenant):
    from src.detection.csv_ingest import create_or_resume_run, load_csv
    run = create_or_resume_run(db, tmp_tenant, "tests/detection/fixtures/sample_claims.csv")
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

- [ ] **Step 1: Failing test** — `compute_baseline(db, run, kind="prescriber_peer_volume")` writes `baseline_cache` rows where each entity's mean/stddev **excludes its own rows** (peer-group), enforces `min_sample_count` (no row / no-fire below it), and records provenance in `extra` (`exclusion="leave_entity_out"`, `peer_count`, `included_current_run=True`).
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** SQL window aggregations over `csv_upload_rows` per `baseline_kind` (pharmacy_ndc_volume, pharmacy_price_history, prescriber_peer_volume, member_cost, pharmacy_weekday_volume) with entity-excluded peer stats; upsert `baseline_cache` keyed `(tenant, kind, scope_key, window_days, data_source)`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): population-separated baseline_cache (peer-exclusion + min sample count)"`

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
- [ ] **Step 3: Implement** `run_detection(db, run)`: Pass 1 baselines (Task 3.3) for applicable baseline rules; Pass 2 — single-row rules via batched scan computing `derive_fields`, grouping rules via GROUP BY (explicit status/code/sign/ordering filters), statistical rules vs `baseline_cache`. Insert `anomalies` (Reference B columns: `finding_code`, `finding_summary`, `finding_details`, snapshot fields, `detection_kind='rule'`, `detection_id`=instance). Log `finding_raised`+`error` per row only; aggregate `no_finding` counts. Update `detection_runs.anomaly_count`/`record_count`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): two-pass detection + lifecycle-aware grouping + anomaly persistence"`

---

## Phase 4 — CLI + summary

### Task 4.1: Run summary

**Files:** Create `modules/reclaimrx/src/detection/run_summary.py`; Test `tests/detection/test_run_summary.py`

- [ ] **Step 1: Failing test** — `build_summary(db, run)` returns counts: rows in/declared/unmapped, rules applied vs deferred, anomalies by code/family/severity, top pharmacies/prescribers, total `$ at risk` (`Decimal`).
- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** aggregation queries; finalize run `status='completed'`, `completed_at`, `resolution_stats`.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): detection-run summary report"`

### Task 4.2: CLI entrypoint with RLS-enforced session

**Files:** Create `modules/reclaimrx/src/cli/detect.py`; Test `tests/detection/test_cli_and_isolation.py`

- [ ] **Step 1: Failing tests** —
  - **End-to-end:** `run_detect(file, tenant)` on the fixture → run completed, expected anomaly counts, summary printed.
  - **Isolation (codex L1 #5):** session connects as `ifx_dev_app` (non-BYPASSRLS), executes `SET LOCAL app.current_tenant_id`; seed tenant A, run as A, assert tenant B + unset-context see zero `anomalies`/`csv_upload_rows`.

```python
def test_cli_tenant_isolation(app_role_engine):
    # app_role_engine connects as ifx_dev_app, NOT infinityrx
    run_detect("tests/detection/fixtures/sample_claims.csv", TENANT_A, engine=app_role_engine)
    with app_role_engine.connect() as c:
        c.execute(text("SET LOCAL app.current_tenant_id = :t"), {"t": str(TENANT_B)})
        assert c.execute(text("SELECT count(*) FROM reclaimrx.anomalies")).scalar() == 0
```

- [ ] **Step 2: Run fail.**
- [ ] **Step 3: Implement** `detect.py`: argparse `--file --tenant [--resume] [--force]`; build a sync session on the app role; wrap each transaction with `SET LOCAL app.current_tenant_id` + `current_tenant_id` contextvar; orchestrate Phase 1 register → Phase 2 load → Phase 3 detect → Phase 4 summary; structured errors, mark `failed` on exception.
- [ ] **Step 4: Run pass; Commit** — `git commit -m "feat(reclaimrx): detect CLI with RLS-enforced app-role session + isolation test"`

### Task 4.3: Full-file dry-run validation (manual gate, not a unit test)

- [ ] **Step 1:** Run `python -m reclaimrx.detect --file "data/ReclaimRx/allDataMinusPHI 1.csv" --tenant a0000000-0000-0000-0000-000000000001` against dev DB.
- [ ] **Step 2:** Confirm: run completes, ~2.6M `csv_upload_rows`, anomalies populated, summary sane (duplicates/reversals/inflation counts plausible vs the 209k Duplicate / 448k Reversed profile), wall-time recorded. Document results in `docs/audit/reclaimrx-first-run-2026-05-29.md`.
- [ ] **Step 3: Commit** the run report.

---

## Self-Review

**Spec coverage:** D1 (Phase 1), D2 (Phase 0), D3 (4.2), D4 (2.2), D5 (1.2/3.4), D6 (3.3/3.5), D7 (1.3), D8 (4.1), D9 (2.4/3.5), D10 (4.2), D11 (0.1/3.4), D12 (2.3), D13 (3.3) — all mapped. §7 financial gate → resolved in Reference A + Task 3.1 golden tests. Codex L1 #1–9 → Tasks 0.1/0.2, 2.2, 3.1, 3.3, 4.2, 3.4, 2.3, 3.5, 2.4.

**Placeholder scan:** financial formulas concrete (Reference A); ORM mirrors Reference B; no "TBD". The ORM column list defers to Reference B/live DDL rather than retyping 15 tables — acceptable (DDL is source of truth, reflection test enforces match).

**Type consistency:** `RuleResult`, `derive_fields` keys (`nq_to_wac_ratio`, `dv_to_awp_ratio`), `create_or_resume_run`, `load_csv`, `gate_rules`, `run_detection`, `build_summary`, `run_detect` — names consistent across tasks.

## Out of scope (v1)
Portal UI · recoup-case workflow · ML scoring/training · graph analysis · ~31–33 deferred rules · event-bus ingestion · multi-tenant ingest.
