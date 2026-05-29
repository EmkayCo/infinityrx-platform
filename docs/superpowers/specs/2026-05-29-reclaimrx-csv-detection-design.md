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
| D4 | Tenant attribution = **single tenant** (`InfinityRx`, `a0000000-0000-0000-0000-000000000001`); CSV `client_id` stored as `resolved_client_id` via `resolution_method='declared'`. |
| D5 | **All 46 rules registered** as `detection_rule_types`; engine evaluates those whose `required_data_columns` are satisfied by the run's source, defers the rest. |
| D6 | **Two-pass** detection using `baseline_cache` for statistical rules. |
| D7 | ML detectors registered as **placeholders** (`is_placeholder=true`), not run. |
| D8 | Results = **CLI summary + SQL-queryable** `detection_runs`/`anomalies`. |
| D9 | Engine approach = **load-then-SQL**: read file once into `csv_upload_rows`, then set-based SQL for baselines + grouping detections. |

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

**Steps:**
1. Recover `0005` source: decompile the `.pyc`, or rewrite from its known effect
   (run-wide skip support on `detection_rule_evaluation_log` — the live table already has
   `detection_run_id` + nullable `source_row_id`, consistent with run-wide skip rows).
2. Apply repo chain `0001 → head` to a scratch database.
3. **Schema-diff** scratch vs the live `reclaimrx` schema; document any deltas.
4. Resolve the version-stamp mismatch: once schema parity is proven, `alembic stamp` the
   dev DB to the repo head (or add a reconciling migration if a real delta exists).
5. Exit criterion: `alembic upgrade head` is green on a fresh DB and produces a schema
   matching dev's `reclaimrx` schema.

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

- CLI creates a `detection_run`: `data_source='csv_upload'`, `source_path`,
  `source_filename`, `source_sha256` (streamed hash), `status='in_progress'`,
  `started_at`, `created_by`. `source_sha256` dedup → warn + abort (or `--force` new run)
  if a completed run with the same hash exists.
- Stream `csv.DictReader` (10k-row chunks; never load the file). Per chunk, bulk-insert
  `csv_upload_rows`: `row_number`, `row_data` (full row jsonb), and resolved columns:
  - `resolved_client_id` ← `client_id` (passthrough, `resolution_method='declared'`),
  - `resolved_pharmacy_npi` ← `pharmacy_npi`, `resolved_ndc` ← `ndc`.
  - Rows missing a required key (null `pharmacy_npi`, or garbage DOS, or null `ndc`
    where the rule needs it) → `resolution_method='unmapped'` + `resolution_notes`.
- **Data hygiene:** DOS outside `[1990-01-01, today]` (e.g. `9999-09-09`) → treated as
  invalid, row marked unmapped for date-dependent rules. Money parsed `Decimal(str(...))`.
- Aggregate `resolution_stats` jsonb on the run: `{declared, unmapped, by_reason{...}}`.
- **Storage note:** 2.6M × 75-col jsonb ≈ multi-GB `csv_upload_rows`. Accepted for a
  backfill (provenance is the table's purpose). Flagged as a disk consideration; not
  optimized in v1.

### Phase 3 — Detection engine (two-pass, set-based)

- **Applicability gate:** compute the set of columns present in the run's source (CSV
  header). For each enabled rule instance, if its type's `required_data_columns` ⊄
  available columns OR `deferred_data_feed=true` → record a **run-wide skip** in
  `detection_rule_evaluation_log` (`evaluation_result='skipped_runwide'`,
  `source_row_id=NULL`, reason) and do not evaluate. (This is migration `0005`'s purpose.)
  Expected on this CSV: **14 rules run (Buckets A+B), ~33 deferred (Bucket C)**.
- **Pass 1 — baselines** (`baseline_cache`): SQL aggregations over `csv_upload_rows` for
  the statistical rules:
  - `pharmacy_ndc_volume` (MFR-004), `pharmacy_price_history` (MFR-003),
    `prescriber_peer_volume` (HP-005), `member_cost` percentile (HP-008),
    `pharmacy_weekday_volume` (ALL-006).
  - Each row keyed `(tenant_id, baseline_kind, scope_key, window_days, data_source)` with
    `mean`/`stddev`/`sample_count`/`extra`.
- **Pass 2 — evaluate:** port World-B `RuleEvaluator` logic (threshold / pattern /
  statistical / comparison / composite) and `ClaimContext` derived fields into a batch
  engine operating on rule instances:
  - **Single-row rules** (e.g. MFR-001 NQ inflation): batched SQL scan computing derived
    fields (§7) per row.
  - **Grouping rules** (ALL-001 duplicate, MFR-002 BRR, ALL-005 early-refill, HP-010,
    TH-002, TH-005): GROUP BY / window queries over `csv_upload_rows`.
  - **Statistical rules:** compare row/entity value to `baseline_cache`.
  - Emit `anomalies`: `data_source='csv_upload'`, `data_source_run_id`, `source_table='csv_upload_rows'`,
    `source_row_id`, `detection_kind='rule'`, `detection_id`=rule instance id,
    `finding_code`=rule code, `finding_summary`, `finding_details` (evidence jsonb),
    `severity`, `confidence`, snapshot fields (`date_of_service`, `pharmacy_npi`,
    `prescriber_npi`, `ndc`, `quantity`, `amount_paid`, `amount_billed`), `status='open'`.
  - Per-evaluation rows in `detection_rule_evaluation_log` (`fired`/`not_fired`/`error`,
    `elapsed_ms`, `anomaly_id`) — sampled or aggregated to avoid 2.6M×N log explosion
    (decision in plan: log fired + errors per row, skips run-wide).
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

## 7. CSV → ClaimContext field mapping (port target)

| ClaimContext / derived | Source |
|---|---|
| `pharmacy_npi` | `pharmacy_npi` |
| `prescriber_npi` | `prescriber_npi` |
| `ndc` | `ndc` |
| `date_of_service` | `date_of_service` (validated) |
| `quantity` | `quantity_dispensed` |
| `days_supply` | `day_supply` |
| `billed_amount` | `ingredient_cost_submitted` (+ submitted fees) |
| `paid_amount` / `amount_paid` | `total_paid_amt` |
| `wac_per_unit` | `extended_wac` ÷ `quantity_dispensed` |
| `awp_per_unit` | `drug_awp` ÷ `quantity_dispensed` |
| `nq` (net qty cost) | `ingredient_cost_paid` (net of `pos_adjustment`) |
| `dv` (dispensing value) | `dispensing_fee_paid` |
| `member_id` | `patient_unique_hash` |
| `nq_to_wac_ratio` | `nq / (wac_per_unit × quantity)` |
| `dv_to_awp_ratio` | `dv / (awp_per_unit × quantity)` |
| reversal flags | `reversed_check`, `transaction_code` (B1/B2), `transaction_status` |

*(Exact fee composition for `billed_amount`/`nq`/`dv` finalized in the plan against the
NCPDP field semantics; the file carries all needed components.)*

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

- **Tenant isolation:** every write sets `tenant_id` = target tenant; `current_tenant_id`
  context set for the run; RLS active on tenant-owned tables. Cross-tenant isolation test.
- **Financial precision:** `Decimal` only, `ROUND_HALF_UP` on every `quantize`,
  `Decimal(str(x))` from CSV, `Numeric` columns, aggregates wrapped `Decimal(str(...))`.
- **PHI:** the file is pre-scrubbed (hashes, zip3, birth_year) — no `EncryptedString`
  required. Hash/identity fields (`patient_unique_hash`, `*_hash`) never logged.
- **Idempotency:** `source_sha256` dedup; detection re-runnable from persisted rows
  without re-reading the file.
- **Performance:** target ≈ PRD's 1M claims / 30 min → ≈78 min for 2.6M acceptable for a
  one-time backfill. Chunked inserts; consider `COPY` if ingest is the bottleneck;
  indexed aggregation columns.
- **No silent failures:** structured errors; run marked `failed` with `failure_reason`.

## 10. Testing

- Fixtures per LESSON-001 (SAVEPOINT) and LESSON-007 (`_UUIDString` for UUID columns).
- **Unit:** each rule eval type; derived-field formulas; Decimal/penny correctness;
  resolution logic (declared vs unmapped); applicability gate.
- **Integration:** small fixture CSV (~50 rows with planted duplicates / reversals /
  NQ-inflation / nulls / garbage DOS) → full CLI run → assert `detection_run` completed,
  `anomalies` counts by rule, `resolution_stats`, run-wide skip log for deferred rules.
- **Isolation:** two tenants, run as one, verify zero cross-tenant rows.
- Coverage: 100% on financial + tenant paths; 95%+ elsewhere on new code.

## 11. Risks

| Risk | Mitigation |
|---|---|
| Phase 0 reveals real schema delta (dev ≠ repo) | Schema-diff is an explicit step; add a reconciling migration if needed before any feature code. |
| `0005` `.pyc` undecompilable | Rewrite migration from its documented effect (run-wide skip cols); verify against live table. |
| `csv_upload_rows` disk footprint (multi-GB) | Accepted for backfill; documented; option to project columns deferred. |
| Grouping rules slow at 2.6M | Set-based SQL + indexes; measure; `COPY` fallback. |
| Telehealth rules over-fire (no TH flag) | Documented approximation; `deferred_reason` notes; revisit when a telehealth signal exists. |
| Eval-log row explosion | Log fired + errors per-row, skips run-wide; no row for not-fired. |

## 12. Out of scope (v1)

Portal UI · recoup-case workflow · ML training/scoring · graph analysis · ~33 deferred
rules · event-bus ingestion · multi-tenant ingest.
