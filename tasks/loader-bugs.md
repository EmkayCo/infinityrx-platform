# Loader Bugs — Tracking

Discovered during the 2026-04-15 environment-setup session. Each entry is a
real bug in a federal reference-data loader that prevents main reference
tables from populating. None of these block the demo (the
`seed_reference_shim.py` workaround provides 50 drugs / 50 pharmacies /
100 prescribers with 100% join hit-rate against scrambled mock claims),
but every one is a production blocker before any environment can ingest
real federal data.

Convention:
- **Status**: open / in-progress / fixed
- **Priority**: P1 (blocks any real reference data) / P2 (broken but
  alternative path exists) / P3 (cosmetic / log noise)

---

## LOADER-BUG-01 — `scripts/load_fda_ndc.py` foreign-key violation
- **Status**: open
- **Priority**: P1
- **Module**: drug-database
- **Loader**: `scripts/load_fda_ndc.py`
- **Symptom**: Loader reports `status=completed records_inserted=25,000
  records_errored=301,264 duration_seconds=46.8s`. After the run,
  `drug_database.drugs` has **0 rows** and the log is full of
  `psycopg2.errors.ForeignKeyViolation: insert or update on table
  "drug_packages" violates foreign key constraint
  "drug_packages_product_id_fkey"`.
- **Root cause** (best guess): the loader inserts `drugs` and `drug_packages`
  rows in the same flush. Within a flush, `drug_packages.product_id` rows
  reference `drugs.product_id` rows that are still in the same pending
  transaction. When any single `drug_package` references a `drug` that did
  NOT make it into the same flush (because the parser yielded the package
  in a different batch from its parent drug), the FK fails and the entire
  batch transaction rolls back — including all the drug rows. Subsequent
  batches' drug inserts then re-collide, etc.
- **Suggested fix**: split the loader into two passes — first ingest ALL
  drugs (commit), then ingest drug_packages (commit), then drug_active_
  ingredients, then drug_pharm_classes. The dependency order is:
  drugs → drug_packages → {drug_active_ingredients, drug_pharm_classes}.
  Alternatively, set the FK constraints to DEFERRABLE INITIALLY DEFERRED
  and commit at the end of the entire run.
- **Repro**:
  ```bash
  source infrastructure/scripts/switch_env.sh dev
  python scripts/load_fda_ndc.py
  psql ... -c "SELECT COUNT(*) FROM drug_database.drugs;"  # → 0
  ```

---

## LOADER-BUG-02 — `scripts/load_ncpdp.py` main table empty after success
- **Status**: open
- **Priority**: P1
- **Module**: pharmacy-directory
- **Loader**: `scripts/load_ncpdp.py` →
  `modules/pharmacy-directory/src/services/ncpdp_ingestion.py`
- **Symptom**: Loader reports `status=completed processed=1,083,879
  inserted=1,012,924 errored=70,955 duration=246s`. After the run,
  `pharmacy_dir.ncpdp_pharmacies` has **0 rows**. Some sub-tables
  (`ncpdp_pharmacy_fwa_actions`, `ncpdp_pharmacy_coordinates`,
  `ncpdp_pharmacy_patient_care`, `ncpdp_pharmacy_additional_info`) have
  small non-zero counts (~400–800 rows each), suggesting the rollback is
  not total but is selective.
- **Root cause** (best guess): the upsert path in `_upsert_batch()` looks
  syntactically correct (`INSERT ... ON CONFLICT DO UPDATE` via
  `sqlalchemy.dialects.postgresql.insert`). Two suspects:
  1. The `_get_unique_col` map declares `ncpdp_provider_id` as the unique
     constraint for the main table, but there may be a different actual
     unique constraint on the live schema, causing the ON CONFLICT to
     match nothing and the inserts to silently no-op.
  2. The base ingester's run wrapper calls `db.commit()` only at the very
     end, AFTER a final flush. If any in-flight upsert raises during the
     final flush, the entire run gets rolled back — but earlier batches
     that called `_db.flush()` during the run wouldn't be in the rollback
     window if they used sub-savepoints. Needs a debugger trace.
- **Suggested fix**: add a `cur.execute("SELECT count(*) ...")` at the end
  of the loader and ASSERT the row count matches `records_inserted`. Also
  unwrap the upsert and add an explicit `RETURNING id` to confirm the
  conflict resolution actually inserts.
- **Repro**: `python scripts/load_ncpdp.py` → check
  `pharmacy_dir.ncpdp_pharmacies` row count.

---

## LOADER-BUG-03 — `scripts/load_cms_nadac.py` missing ON CONFLICT, infinite retry loop
- **Status**: open
- **Priority**: P1
- **Module**: drug-database
- **Loader**: `scripts/load_cms_nadac.py`
- **Symptom**: After ~30 seconds of progress the log starts emitting
  `psycopg2.errors.UniqueViolation: duplicate key value violates unique
  constraint`. SQLAlchemy dumps every parameter from the failing batch
  (~14,000 params per dump) — the log file grows by ~80 MB/minute. After
  4 minutes the log was 474 MB and the loader was still running. Killed
  manually.
- **Root cause**: the loader is doing plain `INSERT` instead of
  `INSERT ... ON CONFLICT DO UPDATE`. NADAC publishes a daily file with
  the same NDCs each day; on the second run (or after a partial first
  run), the unique constraint on `(ndc_11, effective_date)` collides.
- **Suggested fix**: rewrite `_flush_buffer` (or wherever the insert
  happens) to use the postgres dialect's
  `insert(...).on_conflict_do_update(...)`. Same pattern as the NCPDP
  upsert path. Also: cap the SQLAlchemy error log truncation so a single
  failed batch doesn't dump 80 MB.
- **Repro**: `python scripts/load_cms_nadac.py` → wait ~30s → tail the
  log file and watch it explode.

---

## LOADER-BUG-04 — `scripts/load_new_sources.py rxnorm` uncontrolled download / partial commit
- **Status**: open
- **Priority**: P2 (rxnorm is supplementary; not a P1 reference dataset)
- **Module**: drug-database
- **Loader**: `scripts/load_new_sources.py rxnorm` →
  `shared/data_ingestion/sources/rxnorm.py`
- **Symptom**: Downloads the full RxNorm release from UMLS (~250 MB ZIP)
  on every run. Parsing alone takes 10+ minutes. When killed mid-run,
  `drug_database.rxnorm_relationships` had 455,000 rows committed but
  `drug_database.rxnorm_concepts` had 0 — the relationships are orphaned
  without their concepts.
- **Root cause**: the loader commits `rxnorm_relationships` per-batch
  before all `rxnorm_concepts` are loaded. There's no transactional
  guarantee that concepts are committed first. Also, the loader has no
  `--sample` mode to limit the row count for dev/CI use.
- **Suggested fix**:
  1. Add a `--sample N` flag that loads only the first N rows of each
     RxNorm RRF file — useful for CI and dev.
  2. Reorder the load to commit `rxnorm_concepts` before any
     `rxnorm_relationships` are committed.
  3. Cache the downloaded ZIP to a known path under
     `data/reference/rxnorm/` so subsequent runs are fast.
- **Repro**: `python scripts/load_new_sources.py rxnorm` → check
  `drug_database.rxnorm_concepts` (0) vs `rxnorm_relationships` (455K).

---

## LOADER-BUG-05 — `scripts/load_orange_book.py` silent failure
- **Status**: open
- **Priority**: P1
- **Module**: drug-database
- **Loader**: `scripts/load_orange_book.py`
- **Symptom**: Loader runs to completion in ~14 seconds, log shows no
  errors, the run-summary section says "completed". After the run,
  `drug_database.drug_orange_book` has **0 rows**.
- **Root cause** (unknown — needs investigation): no errors visible. May
  be a missing `db.commit()`, may be a stale parser yielding 0 rows, may
  be a foreign-key dependency on `drug_database.drugs` that fails
  silently because drugs is empty (LOADER-BUG-01).
- **Suggested fix**: add a row-count assertion at the end of the loader.
  Trace the parser output to confirm it's yielding rows. Verify
  `db.commit()` is called.
- **Repro**: `python scripts/load_orange_book.py` → check
  `drug_database.drug_orange_book` row count.

---

## LOADER-BUG-06 — `scripts/load_cms_asp.py` missing xlrd dep
- **Status**: **fixed** (in `pyproject.toml` commit `ec48e9d`)
- **Priority**: P3
- **Module**: drug-database
- **Loader**: `scripts/load_cms_asp.py`
- **Symptom**: Loader exits in <1s with `xlrd is required to parse .xls
  files. Install it with: pip install xlrd`.
- **Fix applied**: `uv add xlrd` — added to `pyproject.toml` dependencies.
- **Verification**: not yet re-run end-to-end. Should now reach the parse
  step. Whether the parsed data actually commits to
  `drug_database.drug_asp_pricing` is a separate question.

---

## MISSING-MIGRATIONS-01 — modules/billing/ has no alembic history
- **Status**: open (worked around)
- **Priority**: **P1** — must be resolved before any feature work touches
  the billing schema. The `_bootstrap_billing.py` workaround is acceptable
  for environment scaffolding but NOT for ongoing development:
    * `metadata.create_all()` cannot evolve the schema — every column
      addition has to be hand-applied to dev, mock, and prod
    * No rollback path
    * No version stamping → can't tell which environments are at which
      schema state
    * Feature branches that touch billing models will silently diverge
- **Gate**: any PR that adds, removes, or modifies a column in
  `modules/billing/src/models/tables.py` MUST be blocked until a proper
  `0001_billing_baseline.py` exists.
- **Module**: billing
- **Symptom**: `modules/billing/src/models/tables.py` defines ~30 ORM
  models (ClaimRecord, RoutingRule, PaymentBatch, Payment, Invoice,
  ARRecord, JournalEntry, etc.) but `modules/billing/` has no
  `alembic.ini` and no `alembic/versions/` directory at all. Running any
  query against `billing.*` fails with `relation does not exist` until
  someone calls `BillingBase.metadata.create_all()`.
- **Workaround in place**:
  `infrastructure/scripts/_bootstrap_billing.py` calls `create_all()` on
  the BillingBase metadata. Same pattern as the prescriber-directory
  bootstrap that was needed before its baseline migration was written.
- **Required fix**: create `modules/billing/alembic.ini` (use the
  `script_location = alembic` convention from the other modules), an
  `alembic/env.py` that loads `BillingBase.metadata`, and an
  `alembic/versions/0001_billing_baseline.py` that mirrors every table
  in `src/models/tables.py`. Same approach as
  `modules/prescriber-directory/alembic/versions/0000_prescriber_baseline.py`
  (~250 lines for the prescriber baseline; billing is bigger — probably
  600+ lines and 30 `op.create_table` calls). After landing the baseline,
  add `billing` to the `MODULES` list in
  `infrastructure/scripts/run_migrations.sh` and remove
  `infrastructure/scripts/_bootstrap_billing.py`.
- **Likely sibling bugs**: every other module that has `src/models/tables.py`
  but no `alembic/`. Spot check needed for: payment-processing (see
  MISSING-MIGRATIONS-02 below — confirmed), reclaimrx, reporting, ai-nlp,
  dataiq, member-management, edi-compliance, medical-claims. Same root
  cause pattern — these will need MISSING-MIGRATIONS-03..09 entries when
  each is touched by feature work.

---

## MISSING-MIGRATIONS-02 — modules/payment-processing/ has no alembic history (OFAC tables)
- **Status**: open
- **Priority**: P2 (same blast radius as billing but the OFAC path is not
  on the demo critical path)
- **Module**: payment-processing
- **Symptom**: `modules/payment-processing/src/models/tables.py` defines
  `PaymentProcOfacSdn` (table `payment_proc_ofac_sdn`) and
  `PaymentProcOfacAlerts` (table `payment_proc_ofac_alerts`), plus other
  tables for payment vendor integration. The `payment_proc` schema exists
  (created by `init-multi-db.sql`) but has ZERO tables in any environment
  (dev/mock/prod). `modules/payment-processing/` has no `alembic.ini` and
  no `alembic/versions/` directory.
- **Impact**:
    * OFAC SDN screening at pay-to-entity resolution time cannot run
    * `payment_processing.ofac_screening.py` service has nothing to query
      against and will fail at first call
    * No OFAC alerts can be persisted
- **Workaround available**: write an
  `infrastructure/scripts/_bootstrap_payment_processing.py` analog to
  `_bootstrap_billing.py` — one-liner calling
  `PaymentProcBase.metadata.create_all()`. Not implemented yet because
  OFAC is not on the demo critical path.
- **Required fix**: same pattern as MISSING-MIGRATIONS-01. Create
  `modules/payment-processing/alembic.ini`, `alembic/env.py`, and
  `alembic/versions/0001_payment_processing_baseline.py` mirroring every
  table in `src/models/tables.py`. Add `payment-processing` to
  `infrastructure/scripts/run_migrations.sh`.
- **Gate**: any PR that adds, removes, or modifies a column in
  `modules/payment-processing/src/models/tables.py` MUST be blocked until
  the baseline migration exists.

---

## MISSING-LOADER-07 — `shared.sam_exclusions` has no loader script
- **Status**: open
- **Priority**: P1 prod (SAM is half of the federal exclusion-screening
  pair — OIG catches healthcare-specific exclusions, SAM catches
  debarments across all federal programs. You can't ship prod without
  both.)
- **Module**: core-platform / shared.data_ingestion
- **Schema**: `shared.sam_exclusions` — exists, created by
  `modules/core-platform/alembic/versions/0008_compliance_reference_tables.py`
- **Ingester**: `shared/data_ingestion/sources/sam_exclusions.py` exists
- **Missing**: `scripts/load_sam.py` wrapper (or a `sam` target in
  `scripts/load_new_sources.py`)
- **Symptom**: Row count in all three DBs is **0**. No way to trigger the
  ingester from the CLI. `load_new_sources.py` does not include `sam` in
  its `_ingester_for()` dispatcher.
- **Data source**: `api.sam.gov` has a public API (requires a free SAM.gov
  API key stored in the `SAM_API_KEY` env var — already declared in
  `shared/config.py` Settings). CSV dumps also available via
  sam.gov/data-services/Exclusions/Public.
- **Suggested fix**: copy `scripts/load_oig_leie.py` as a template, swap
  in `SamExclusionsIngester` from the existing source file, and add a
  `sam` target to `load_new_sources.py` for consistency. Expected row
  count: 120,000–160,000 active exclusions as of 2026-01.
- **Repro**:
  ```bash
  grep -rn "SamExclusions" shared/data_ingestion/sources/
  ls scripts/load_*sam*  # → empty
  ```

---

## MISSING-LOADER-08 — `shared.government_program_bins` has no state Medicaid loader
- **Status**: open (partial shim workaround in place)
- **Priority**: P1 prod (Medicaid claim routing cannot function without
  the full BIN/PCN table — every Medicaid claim has to be matched to the
  correct state program before adjudication)
- **Module**: core-platform / shared.data_ingestion
- **Schema**: `shared.government_program_bins` — exists, created by
  `modules/core-platform/alembic/versions/0009_government_program_bins.py`
- **Ingester**: `shared/data_ingestion/sources/state_medicaid_bins.py`
  exists with full logic for **50 states + DC + 5 US territories (56
  total)** — confirmed by reading the `VALID_STATES` constant in the
  source file.
- **Missing**: `scripts/load_medicaid_bins.py` wrapper
- **Symptom**: Row count in all three DBs is **0**, but as of the
  2026-04-15 shim-update commit, 10 representative state Medicaid entries
  (CA/TX/NY/FL/PA/IL/OH/GA/NC/MI) are seeded via
  `infrastructure/scripts/seed_reference_shim.py` so the demo can show
  Medicaid routing for the largest states.
- **Data source**: each state Medicaid agency publishes BIN/PCN/Group
  information on its pharmacy provider portal. The ingester source
  supports CSV upload via the
  `shared.data_ingestion.sources.gov_exclusion.load_state_medicaid_csv_from_bytes`
  function. The admin API route
  `modules/core-platform/src/government_programs/api.py` already wires
  the upload path.
- **Suggested fix**: write `scripts/load_medicaid_bins.py` that
  instantiates `StateMedicaidBinLoader`, passes the curated CSV under
  `data/reference/medicaid/`, and reports coverage
  (`summary.states_covered` / `summary.states_missing`).
- **Repro**:
  ```bash
  ls scripts/load_*medicaid*  # → empty
  ls data/reference/medicaid/  # → check for source CSVs
  ```

---

## MISSING-LOADER-09 — `prescriber_dir.dea_registrations` has no loader script
- **Status**: open
- **Priority**: P2 (needed for controlled-substance prescribing validation
  — not on the demo critical path but required for any DEA-2 through
  DEA-5 claim adjudication)
- **Module**: prescriber-directory / shared.data_ingestion
- **Schema**: `prescriber_dir.dea_registrations` — exists, created by
  `modules/prescriber-directory/alembic/versions/0003_dea_compliance_tables.py`
- **Ingester**: `shared/data_ingestion/sources/dea_registrations.py`
  exists
- **Missing**: `scripts/load_dea.py` wrapper
- **Symptom**: Row count in all three DBs is **0**.
- **Data source**: DEA Controlled Substance Act registrant list — the
  public ARCOS / CSA registrant file. Access is gated behind a DEA data
  request process; the ingester likely expects a CSV dropped in
  `data/reference/dea/`.
- **Suggested fix**: copy `scripts/load_oig_leie.py` as a template, swap
  in the `DeaRegistrationsIngester`, and document the source CSV path in
  the script docstring. Also add a `dea` target to `load_new_sources.py`
  for consistency with the other simple loaders.
- **Repro**:
  ```bash
  ls scripts/load_*dea*  # → empty
  ```

---

## MISSING-LOADER-10 — `core.exclusion_list` unified crosswalk has no aggregator
- **Status**: open
- **Priority**: P1 prod (this is the table the claim adjudication engine
  queries to block excluded entities — without it, every claim has to hit
  OIG and SAM separately)
- **Module**: core-platform
- **Schema**: `core.exclusion_list` + `core.exclusion_matches` — both
  exist, created by
  `modules/core-platform/alembic/versions/0008_compliance_reference_tables.py`.
  Physically present in all three DBs.
- **Constraint on `core.exclusion_list.source`**:
  `CHECK (source IN ('OIG', 'SAM'))` — the table is scoped to unified
  OIG + SAM aggregation only. OFAC SDN and state exclusion lists are NOT
  supported by this schema; they would need either a schema change or
  a separate unified table.
- **Missing**: an aggregator job that reads from
  `shared.oig_leie_exclusions` and `shared.sam_exclusions` and populates
  `core.exclusion_list` with a normalized row per distinct entity, plus
  a matcher that writes `core.exclusion_matches` when a claim's
  pharmacy/prescriber/member resolves to an entry.
- **Symptom**: Row count in all three DBs is **0** for both tables.
  `shared.oig_leie_exclusions` has 82,896 rows but those rows never flow
  into `core.exclusion_list`.
- **Suggested fix** (two-part):
    1. `scripts/build_exclusion_crosswalk.py` — batch job that
       SELECTs from `shared.oig_leie_exclusions` + `shared.sam_exclusions`
       and INSERTs normalized rows into `core.exclusion_list`, keyed on
       `(source, npi)` or `(source, last_name, first_name, state)` when
       NPI is absent. Upsert semantics so re-running refreshes without
       duplication.
    2. A runtime matcher service (probably in
       `modules/core-platform/src/exclusions/`) that on each claim ingest
       event queries `core.exclusion_list` by pharmacy_npi / prescriber_npi
       and writes a `core.exclusion_matches` row if a hit is found, with
       confidence level and status `pending`.
- **Also needed**: schema extension to support OFAC and state lists. The
  CHECK constraint will block any attempt to insert a row with
  `source='OFAC'` or `source='CA_MEDICAID_BLOCKED'`. Either drop the
  constraint or replace it with a more permissive regex.
- **Repro**:
  ```bash
  psql ... -c "SELECT COUNT(*) FROM core.exclusion_list;"  # → 0
  psql ... -c "SELECT COUNT(*) FROM shared.oig_leie_exclusions;"  # → 82896
  ```
