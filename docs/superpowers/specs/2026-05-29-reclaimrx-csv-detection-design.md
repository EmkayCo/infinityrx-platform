# ReclaimRx CSV Detection-Run Backfill — Design Spec (v1)

**Date:** 2026-05-29
**Status:** Draft → pending spec-lock (codex L1)
**Author:** Mike K + Claude
**Module:** `modules/reclaimrx`

---

## 1. Problem

A 1.7 GB PHI-scrubbed historical claims CSV (`data/ReclaimRx/allDataMinusPHI 1.csv`,
**2,611,415 rows**, 75 columns) needs to be ingested into ReclaimRx and run through
the FWA detection rules. ReclaimRx today has **no file-ingestion path** — claims are
designed to enter via the event bus only. A full CSV/detection-run data model was
*designed and migrated* (the "World A" schema in the `reclaimrx` Postgres schema) but
**zero application code implements it**. A second, older "World B" event-driven model
(`reclaimrx_*` prefixed tables) has working rule logic but its tables are not migrated
into the dev DB and its shape is event-based, not file-based.

This spec finishes World A and ports World B's rule logic into it, so the historical
file can be ingested and scored via a backend CLI command.

## 2. Goals

1. Ingest the 2.6M-row CSV into the World-A `detection_runs` / `csv_upload_rows` model.
2. Run the FWA detection rules that the data supports; produce `anomalies`.
3. Register the full 46-rule catalog; rules whose required data is absent are marked
   `deferred_data_feed` and skipped (recorded), not failed — so future data feeds light
   them up with no code change (configuration over code).
4. Reconcile the migration drift so the alembic chain is trustworthy.
5. Backend-only: a CLI command. Results viewable via a printed summary + SQL.

## 3. Non-goals (v1)

Portal UI · recoup-case creation · ML training/scoring (placeholders only) · graph
analysis · the ~33 rules whose inputs the CSV lacks · the event-bus ingestion path ·
multi-tenant ingest (single tenant this round).

## 4. Locked decisions

| # | Decision |
|---|---|
| D1 | Build on **World A** (`reclaimrx` schema); port World-B rule logic into it. |
| D2 | **Reconcile migration drift first** as Phase 0, before feature code. |
| D3 | Trigger = **CLI / management command**. No HTTP endpoint in v1. |
| D4 | Tenant attribution = **single tenant** (`InfinityRx`, `a0000000-0000-0000-0000-000000000001`). Entity resolution: `resolved_pharmacy_npi`←`pharmacy_npi`, `resolved_ndc`←`ndc` (both varchar, `resolution_method='declared'`). **`resolved_client_id`/`resolved_program_id` are UUID columns → set NULL in v1** (no source-code→UUID mapping); raw `client_id`/`group_id`/`bin`/`pcn` retained in `row_data`. Rows missing `pharmacy_npi` or with invalid DOS → `resolution_method='unmapped'`. *(Revised per codex L1 #2 — UUID type mismatch.)* |
| D5 | **All 46 rules registered** as `detection_rule_types`; engine evaluates those whose `required_data_columns` are satisfied by the run's source, defers the rest. |
| D6 | **Two-pass** detection using `baseline_cache` for statistical rules, with **population separation** (D13). |
| D7 | ML detectors registered as **placeholders** (`is_placeholder=true`), not run. |
| D8 | Results = **CLI summary + SQL-queryable** `detection_runs`/`anomalies`. |
| D9 | Engine approach = **load-then-SQL**: read file once into `csv_upload_rows`, then set-based SQL for baselines + grouping detections. |
| D10 | **RLS enforcement (codex L1 #5):** CLI connects as the non-`BYPASSRLS` app role (`ifx_dev_app`), never the `infinityrx` superuser. Every transaction runs `SET LOCAL app.current_tenant_id = '<tenant>'` (the Postgres GUC the RLS policies read — Python `current_tenant_id` alone does not enforce RLS). Isolation proven by a live test executed as the actual CLI DB role. |
| D11 | **Run-wide deferral (codex L1 #6):** deferred/inapplicable rules log to `detection_rule_evaluation_log` with the **existing** `evaluation_result='skipped_inapplicable'` and `source_table=NULL`/`source_row_id=NULL` — matching the live CHECK `ck_reclaimrx_eval_log_per_claim_columns` (recovered from migration `0005`). **No new `'skipped_runwide'` value.** |
| D12 | **Idempotency (codex L1 #7):** partial unique index on `(tenant_id, source_sha256)` covering non-terminal + completed runs; a Postgres advisory lock keyed `tenant+sha` around run creation; explicit retry policy — resume same run, purge a `failed` run's rows, or supersede before creating a new run. |
| D13 | **Baseline population separation (codex L1 #4):** statistical rules (HP-005, HP-008, MFR-003, MFR-004, ALL-006) must NOT score an entity against a baseline that includes its own contribution. Use peer-group-excluding-entity or prior-period baselines, enforce a minimum `sample_count`, and persist baseline provenance (`baseline_kind`, window, exclusion rule, sample counts, whether current-run rows included) in `baseline_cache.extra`. |

## 5. CSV profile (measured)

- 2,611,415 rows; all money fields parse clean (0 errors).
- `date_of_service` range `2000-01-01 .. 9999-09-09` → **garbage sentinel dates present**.
- Null rates: `pharmacy_npi` 0.00% (101), `prescriber_npi` 0.95%, `ndc` 3.10% (81k),
  `client_id` 0.53%, `bin` 0.00%.
- Cardinality: 28,270 pharmacies · 82,406 prescribers · **990 NDCs** · 803,588 patients ·
  2,600,000 distinct `auth_no_hash`.
- `transaction_status`: Paid 1,480,854 · Rejected 472,599 · **Reversed 448,339** ·
  **Duplicate 209,279**. `reversed_check=Yes` ≈ 17%.
- `client_id`: 16 small ints, "32" = 81% of rows. `bin`: 3 values, "025706" = 99%.
- `pcn`: dirty (123 variants incl. `IFX`/`IFX.`/`1FX`/`FX`/`IFC`).

## 6. Architecture — 5 phases

### Phase 0 — Migration drift reconcile (prerequisite)

**Observed drift:**
- Dev DB `reclaimrx.alembic_version = 0008_ml_detector_seed` — a revision **not present in
  the repo** (repo head = `0008_sp3_extensions`; chain `0001`→`0007`→`0008_sp3`).
- Migration `0005_eval_log_runwide_skips` **source `.py` is missing** (only `__pycache__/.pyc`).
- Repo migrations `0001`–`0007` create the World-A tables; dev DB has those tables.

**`0005` recovered** (from `.pyc`, exact content): `revision='0005_eval_log_runwide_skips'`,
`down_revision='0004_baseline_cache'`, Create Date 2026-04-27 (Wave 43). **upgrade:** make
`detection_rule_evaluation_log.source_table` + `source_row_id` nullable; drop the prior
per-claim check; add `ck_reclaimrx_eval_log_per_claim_columns` =
`(evaluation_result = 'skipped_inapplicable') OR (source_table IS NOT NULL AND source_row_id IS NOT NULL)`.
**downgrade:** reverse. The live dev schema already reflects this — confirming `0005` is the
missing bridge, not a phantom.

**Phantom stamp:** dev `alembic_version='0008_ml_detector_seed'` is a revision name absent
from the repo (repo has `0006_ml_detector_registry` + head `0008_sp3_extensions`). This is a
**lineage fork**, not just a stamp typo — must be bridged explicitly, never blind-stamped
(codex L1 #1).

**Steps:**
1. Restore `0005_eval_log_runwide_skips.py` to `alembic/versions/` with the exact recovered
   content above (revision/down_revision/upgrade/downgrade). Verify `alembic history` is
   linear and `alembic heads` returns a single head.
2. Stand up a **scratch DB**, run `alembic upgrade head` from clean. Must be green.
3. **Full schema-diff** scratch vs live `reclaimrx` schema — not just columns: tables,
   columns, types, **CHECK constraints (by definition), partial/unique indexes, RLS policies
   + FORCE RLS, GRANTs/role privileges, ownership, sequences, seed/data rows**. Document every delta.
4. **Reconcile the fork:** map `0008_ml_detector_seed` → the repo revision(s) that produced
   the equivalent live schema. If the live schema == scratch schema, author a one-line
   **reconciliation/bridge migration** (or an explicit `alembic stamp` *only after* the diff
   proves byte-equivalence of constraints/policies/grants) so future `upgrade`/`downgrade`
   from the current dev stamp is valid. If a real delta exists, author a corrective migration.
5. **Verify live-path upgrade:** simulate `upgrade` from the current dev stamp (not just from
   clean) on a copy, and verify `downgrade` one step works.
6. **Blast-radius check:** confirm the alembic env is reclaimrx-scoped and the stamp/bridge
   does not touch other modules' `alembic_version` tables (each module owns its schema +
   version table — verify, codex L1 #1).
7. Exit criteria: single head; green `upgrade head` from clean AND from the dev stamp; zero
   undocumented schema-diff deltas; ORM (Phase 1) reflects-clean against the result.

### Phase 1 — ORM models + rule-type catalog

- New `modules/reclaimrx/src/models/detection_run_models.py` — ORM classes for the
  World-A tables (none exist today), matching migrated DDL **exactly**. Tenant-owned
  tables inherit `TenantScopedMixin`. Tables:
  `DetectionRun`, `CsvUploadRow`, `Anomaly`, `AnomalyAuditLog`, `DetectionRuleType`
  (global, no tenant), `DetectionRuleInstance`, `DetectionRuleEvaluationLog`,
  `BaselineCache`, `MlDetectorRegistry` (global), `MlTrainingRun`, `FlaggedNpi`,
  `RecoupCase`, `CaseAssignment`, `CaseAnomalyLink`, `CaseNumberSequence`.
  *(Models defined for the schema; only the subset needed by v1 is exercised.)*
- `register_rule_type` registry (PRD intended, never built): port all 46 rules from
  `src/services/detection_rule_seeder.py` into `detection_rule_types` rows with:
  - `code`, `name`, `description`, `family` (map `category`→A1–A6, documented in the registry),
  - `default_severity`, `default_confidence`, `default_parameters` (from `rule_logic`/`confidence_scoring`),
  - `requires_baseline`, `requires_history`,
  - **`required_data_columns`** (the gating list — see §8),
  - `deferred_data_feed`+`deferred_reason` for Bucket-C rules (§8).
  Idempotent upsert at CLI startup (and reusable at app startup later).
- Create one `detection_rule_instance` (default params) per **applicable** rule for the
  target tenant.

### Phase 2 — CSV ingest + entity resolution (single file read)

- **Run creation under a lock (D12, codex L1 #7):** acquire a Postgres advisory lock keyed
  `hash(tenant_id, source_sha256)`. Inside it: if a **completed** run with the same hash
  exists → abort (or `--force`). If a **non-terminal** run exists → refuse (concurrent run)
  unless `--resume`. A partial unique index on `(tenant_id, source_sha256)` over
  non-terminal+completed runs enforces this at the DB even under races. Then create the
  `detection_run`: `data_source='csv_upload'`, `source_path`, `source_filename`,
  `source_sha256` (streamed hash), `expected_record_count` (counted during hashing pass),
  `status='in_progress'`, `started_at`, `created_by`. *(If `detection_runs` lacks
  `expected_record_count`, store it in `resolution_stats` — no schema change.)*
- Stream `csv.DictReader` (10k-row chunks; never load the file). Per chunk, bulk-insert
  `csv_upload_rows`: `row_number` (monotonic, for restart), `row_data` (full row jsonb),
  and resolved columns:
  - `resolved_pharmacy_npi` ← `pharmacy_npi`, `resolved_ndc` ← `ndc` (varchar passthrough,
    `resolution_method='declared'`).
  - **`resolved_client_id`/`resolved_program_id` = NULL** (UUID columns; no source→UUID map
    in v1 — D4/codex L1 #2). Raw `client_id`/`group_id`/`bin`/`pcn` live in `row_data`.
  - Rows missing `pharmacy_npi`, or invalid DOS, or null `ndc` (where a target rule needs
    it) → `resolution_method='unmapped'` + `resolution_notes`.
- **Data hygiene:** DOS outside `[1990-01-01, today]` (e.g. `9999-09-09`) → invalid; row
  flagged unmapped for date-dependent rules. Money parsed `Decimal(str(...))`.
- **Resumability contract (codex L1 #9):** chunk inserts committed with checkpoints;
  `detection_runs` tracks `expected_record_count` vs inserted count. **Detection (Phase 3)
  may only start when inserted count == expected_record_count** (full coverage). On failure,
  mark the run `failed` (with `failure_reason`) in a **separate transaction**; `--resume`
  restarts from `max(row_number)+1`; `--force` purges the failed run's `csv_upload_rows`
  before reload. No detection ever runs on partial rows.
- Aggregate `resolution_stats` jsonb on the run: `{declared, unmapped, by_reason{...},
  expected_count, inserted_count}`.
- **Storage note:** 2.6M × 75-col jsonb ≈ multi-GB `csv_upload_rows`. Accepted for a
  backfill (provenance is the table's purpose). Flagged as a disk consideration; not
  optimized in v1.

### Phase 3 — Detection engine (two-pass, set-based)

- **Applicability gate (D11):** compute the set of columns present in the run's source (CSV
  header). For each enabled rule instance, if its type's `required_data_columns` ⊄
  available columns OR `deferred_data_feed=true` → record one **run-wide skip** in
  `detection_rule_evaluation_log` with `evaluation_result='skipped_inapplicable'`,
  `source_table=NULL`, `source_row_id=NULL` (matches live CHECK; the existing value, not a
  new one). Expected on this CSV: **14 rules run (Buckets A+B), ~33 deferred (Bucket C)**.
- **Pass 1 — baselines** (`baseline_cache`, with population separation per D13/codex L1 #4):
  SQL aggregations over `csv_upload_rows` for the statistical rules:
  - `pharmacy_ndc_volume` (MFR-004), `pharmacy_price_history` (MFR-003),
    `prescriber_peer_volume` (HP-005), `member_cost` percentile (HP-008),
    `pharmacy_weekday_volume` (ALL-006).
  - Each row keyed `(tenant_id, baseline_kind, scope_key, window_days, data_source)` with
    `mean`/`stddev`/`sample_count`/`extra`.
  - **Population separation:** the scored entity must be excluded from its own baseline —
    peer-group baseline (e.g. all *other* pharmacies for that NDC) or prior-period baseline.
    Enforce a **minimum `sample_count`** (configurable per rule, default in plan) below which
    the rule does not fire (avoids unstable small-peer false positives). Persist provenance
    in `extra`: exclusion rule, peer count, window, whether current-run rows were included.
- **Pass 2 — evaluate:** port World-B `RuleEvaluator` logic (threshold / pattern /
  statistical / comparison / composite) and `ClaimContext` derived fields into a batch
  engine operating on rule instances:
  - **Single-row rules** (e.g. MFR-001 NQ inflation): batched SQL scan computing derived
    fields (§7) per row. *Note:* MFR-001 per PRD is **(DV+NQ) vs WAC×qty** — port must include
    `dv`, not the World-B `nq`-only shortcut (codex L1 #3).
  - **Grouping rules** (ALL-001 duplicate, MFR-002 BRR, ALL-005 early-refill, HP-010,
    TH-002, TH-005): GROUP BY / window queries over `csv_upload_rows`. **Claim-lifecycle
    semantics (codex L1 #8):** define explicit inclusion/exclusion by `transaction_status`
    (Paid/Reversed/Rejected/Duplicate) and `transaction_code` (B1/B2), sign normalization on
    reversals, and original→reversal→rebill ordering. ALL-001 must NOT flag legitimate
    reversal/duplicate **lifecycle** rows (209k `Duplicate`, 448k `Reversed` already tagged)
    as fraud; MFR-002 must distinguish a true higher-NQ rebill from a normal reversal pair.
    Exact group keys + filters specified in the plan; covered by planted-sequence tests.
  - **Statistical rules:** compare entity value to its **separated** `baseline_cache` row.
  - Emit `anomalies`: `data_source='csv_upload'`, `data_source_run_id`, `source_table='csv_upload_rows'`,
    `source_row_id`, `detection_kind='rule'`, `detection_id`=rule instance id,
    `finding_code`=rule code, `finding_summary`, `finding_details` (evidence jsonb),
    `severity`, `confidence`, snapshot fields (`date_of_service`, `pharmacy_npi`,
    `prescriber_npi`, `ndc`, `quantity`, `amount_paid`, `amount_billed`), `status='open'`.
  - Per-evaluation rows in `detection_rule_evaluation_log` use the live enum
    (`finding_raised` / `no_finding` / `error`; `anomaly_id` set iff `finding_raised`).
    **To avoid 2.6M×14 ≈ 36M rows (codex L1 #5):** log `finding_raised` + `error` per row
    only; do NOT write a `no_finding` row per (row×rule) — record per-rule no_finding as an
    aggregate count on the run. Run-wide deferrals = one `skipped_inapplicable` row per rule.
- Port severity/risk bands + thresholds (hold 70 / investigation 80 / ML 75 constants).
- `ml_detector_registry`: upsert placeholder rows (`is_placeholder=true`, no artifact);
  **not invoked**.

### Phase 4 — Summary + verification

- Finalize run: `status='completed'`, `completed_at`, `record_count`, `anomaly_count`,
  `resolution_stats`. On failure: `status='failed'`, `failure_reason`.
- CLI prints: rows in / resolved / unmapped; rules applied vs deferred (with reasons);
  anomaly counts by rule code / family / severity; top flagged pharmacies + prescribers;
  total `$ at risk`.
- Results queryable in `reclaimrx.detection_runs` and `reclaimrx.anomalies`.

## 7. CSV → ClaimContext field mapping (PROVISIONAL — see gate below)

> **⚠ codex L1 #3 — gated.** The table below is a **provisional hypothesis**, NOT locked.
> Any cost-ratio rule (MFR-001/003/004/009) becomes garbage if a field's per-unit-vs-extended
> semantics or sign handling is wrong. **Before plan-lock (L2)** the plan MUST produce a
> *signed field-semantics table* and prove it by **row-level reconciliation** on real
> anonymized rows (e.g. verify `extended_wac ?= unit_wac × quantity_dispensed`;
> reconcile `total_paid_amt` against `ingredient_cost_paid + dispensing_fee_paid + sales_tax
> − pos_adjustment − patient_paid_amt − other_payer_amount`). Golden tests with expected
> ratios from hand-checked rows are an acceptance criterion.

| ClaimContext / derived | Provisional source | Open question |
|---|---|---|
| `pharmacy_npi` / `prescriber_npi` / `ndc` | same-named columns | — |
| `date_of_service` | `date_of_service` (validated) | — |
| `quantity` | `quantity_dispensed` | — |
| `days_supply` | `day_supply` | — |
| `billed_amount` | `ingredient_cost_submitted` (+ submitted fees) | which fees? |
| `paid_amount` / `amount_paid` | `total_paid_amt` | plan vs total vs patient split |
| `wac_per_unit` | `extended_wac` ÷ `quantity_dispensed` | **is `extended_wac` already extended (total)?** If so this is unit; do NOT re-multiply blindly |
| `awp_per_unit` | `drug_awp` ÷ `quantity_dispensed` | is `drug_awp` per-unit or total? same unit basis as WAC? |
| `nq` (net qty cost) | `ingredient_cost_paid` − `pos_adjustment` | sign of `pos_adjustment`; reversal negation |
| `dv` (dispensing value) | `dispensing_fee_paid` | — |
| `member_id` | `patient_unique_hash` | — |
| `nq_to_wac_ratio` | `nq / (wac_per_unit × quantity)` | circular if `extended_wac` already total |
| `dv_to_awp_ratio` | `dv / (awp_per_unit × quantity)` | unit basis must match |
| **MFR-001** | **`(dv + nq)` vs `wac_per_unit × quantity`** (PRD), not nq-only | World-B code omits `dv` — port must add it |
| reversal flags | `reversed_check`, `transaction_code` (B1/B2), `transaction_status` | sign normalization for B2 |

## 8. Rule catalog — buckets & gating

Each rule_type carries `required_data_columns`. The engine runs a rule only if the run's
source satisfies them. v1 expected outcome on this CSV:

**Bucket A — runs, CSV-native (single-row / grouping):**
ALL-001 (duplicate), MFR-001 (NQ inflation), MFR-002 (bill-reverse-rebill),
ALL-005 (early refill), HP-010 (refill pattern), TH-005 (prescriber→pharmacy affinity),
TH-002 (geographic dispersion), MFR-008 (statement credit).

**Bucket B — runs, needs `baseline_cache`:**
MFR-004 (volume spike), MFR-003 (rate deviation), HP-005 (prescriber outlier),
HP-008 (high-cost claimant), ALL-006 (weekend/holiday spike), MFR-009 (U&C gaming).

**Bucket C — registered, `deferred_data_feed=true` (CSV lacks inputs):**
ALL-002/003 (phantom pharmacy/prescriber — need NCPDP/OIG/DEA),
ALL-007 (geo distance — home address scrubbed), ALL-008 (network cluster — graph),
ALL-009/010 (operational/ML), MFR-005/006/007 (voucher/enrollment/copay-assist),
HP-001/002/003/004/007/009 (network/formulary/dx/MME/qty-limit),
TPA-001..004, 340B-001..005, WC-001..004, TH-001/003/004. (~33 rules.)

*Note:* the `telehealth` rules TH-002/TH-005 run as prescriber-behavior rules (the file
has no telehealth flag; documented as an approximation in `deferred_reason`/notes — they
fire on all prescribers, not just telehealth, in v1).

**Bonus signals (new rule types, optional in plan):** reject-code pattern analysis
(`reject_code`/`reject_message`, 472k rejected) and per-pharmacy reversal-rate.

## 9. Cross-cutting requirements

- **Tenant isolation (D10, codex L1 #5):** CLI connects as the **non-`BYPASSRLS` app role**
  (`ifx_dev_app`) — never `infinityrx` (superuser, bypasses RLS). Every transaction sets the
  Postgres GUC `SET LOCAL app.current_tenant_id = '<tenant>'` (RLS policies read the GUC, not
  the Python contextvar); the shared tenant-context layer must propagate it to the session.
  Every write sets `tenant_id`. Verified by a live isolation test run **as the CLI DB role**
  (seed tenant A, run CLI, assert tenant B + unset-context see zero rows).
- **Financial precision:** `Decimal` only, `ROUND_HALF_UP` on every `quantize`,
  `Decimal(str(x))` from CSV, `Numeric` columns, aggregates wrapped `Decimal(str(...))`.
- **PHI:** the file is pre-scrubbed (hashes, zip3, birth_year) — no `EncryptedString`
  required. Hash/identity fields (`patient_unique_hash`, `*_hash`) never logged.
- **Idempotency (D12):** advisory lock + partial unique index on `(tenant_id, source_sha256)`;
  detection re-runnable from persisted rows (full-coverage gate) without re-reading the file;
  explicit `--resume` / `--force` semantics.
- **Performance:** target ≈ PRD's 1M claims / 30 min → ≈78 min for 2.6M acceptable for a
  one-time backfill. Chunked inserts; consider `COPY` if ingest is the bottleneck;
  indexed aggregation columns.
- **No silent failures:** structured errors; run marked `failed` with `failure_reason`.

## 10. Testing

- Fixtures per LESSON-001 (SAVEPOINT) and LESSON-007 (`_UUIDString` for UUID columns).
- **Unit:** each rule eval type; derived-field formulas; Decimal/penny correctness;
  resolution logic (declared vs unmapped, NULL UUID handling); applicability gate.
- **Golden financial tests (codex L1 #3):** hand-checked anonymized rows with expected
  `nq`/`dv`/`nq_to_wac_ratio`/`dv_to_awp_ratio` + the field-semantics reconciliation
  (`extended_wac` unit-vs-extended). Gate for plan-lock.
- **Lifecycle tests (codex L1 #8):** planted Paid/Reversed/Rejected/Duplicate/rebill
  sequences → assert ALL-001/MFR-002 fire on true anomalies and NOT on normal lifecycle rows.
- **Baseline-separation tests (codex L1 #4):** a single dominant entity must not suppress its
  own detection (peer-exclusion) and small peer groups must not false-fire (min sample_count).
- **Integration:** fixture CSV (~50 rows, planted duplicates / reversals / NQ-inflation /
  nulls / garbage DOS) → full CLI run → assert `detection_run` completed, full-coverage gate,
  `anomalies` counts by rule, `resolution_stats`, one `skipped_inapplicable` row per deferred rule.
- **Isolation (codex L1 #5):** run **as the CLI DB role** (`ifx_dev_app`, non-BYPASSRLS),
  two tenants, verify zero cross-tenant rows + unset-context sees nothing.
- **Idempotency (codex L1 #7):** concurrent-invocation race (advisory lock), failed-partial +
  `--resume`/`--force`, dedup on identical sha.
- **Migration (codex L1 #1/#6):** fresh `upgrade head` green; restored `0005` produces the
  live eval-log CHECK; upgrade from the current dev stamp valid.
- Coverage: 100% on financial + tenant paths; 95%+ elsewhere on new code.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Phase 0 lineage fork (dev stamp `0008_ml_detector_seed` absent from repo) | `0005` recovered; full schema-diff incl. constraints/RLS/grants; explicit bridge, no blind-stamp; verify upgrade from dev stamp + blast-radius scoped to reclaimrx (codex L1 #1). |
| Wrong financial field semantics → garbage anomalies | Provisional §7; signed semantics table + row-level reconciliation + golden tests gate plan-lock (codex L1 #3). |
| `resolved_client_id` UUID vs int code | NULL in v1, raw kept in `row_data`; no fake UUIDs (codex L1 #2). |
| Statistical self-reference suppresses/false-fires | Peer-exclusion/prior-period baselines + min sample_count + provenance (codex L1 #4, D13). |
| CLI bypasses RLS via superuser role | App role `ifx_dev_app` + `SET LOCAL app.current_tenant_id` + live as-role isolation test (codex L1 #5). |
| Idempotency race / partial-run duplication | Advisory lock + partial unique index + full-coverage gate + resume/force (codex L1 #7,#9). |
| Eval-log explosion (2.6M×14) | `finding_raised`+`error` per row only; no_finding aggregated; deferrals one row/rule (codex L1 #5). |
| Duplicate/BRR flag normal lifecycle | Explicit status/code filters + sign normalization + ordering + planted-sequence tests (codex L1 #8). |
| `csv_upload_rows` disk footprint (multi-GB) | Accepted for backfill; documented; column projection deferred. |
| Grouping rules slow at 2.6M | Set-based SQL + indexes; measure; `COPY` fallback. |
| Telehealth rules over-fire (no TH flag) | Documented approximation; `deferred_reason` notes; revisit when a telehealth signal exists. |

## 12. Out of scope (v1)

Portal UI · recoup-case workflow · ML training/scoring · graph analysis · ~33 deferred
rules · event-bus ingestion · multi-tenant ingest.
