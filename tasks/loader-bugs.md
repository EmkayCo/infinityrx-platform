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
- **Status**: **partial fix** (commit `b6de01c`) — primary FK bug resolved,
  residual `ndc_11` dedup issue tracked as LOADER-BUG-01a below
- **Priority**: P1
- **Module**: drug-database
- **Loader**: `scripts/load_fda_ndc.py`
- **Symptom (original)**: Loader reports `status=completed records_inserted=25,000
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
- **Fix applied** (commit `b6de01c`): per-batch `self._db.commit()` inside
  both `_upsert_drug_batch` and `_insert_packages` in
  `modules/drug-database/src/services/ndc_ingestion.py`. A failure in
  batch N now only rolls back that batch — prior batches are durable.
- **Result**: drugs went from 0 → 25,050. drug_packages 0 → 34,000.
  drug_active_ingredients 0 → 35,117. drug_pharm_classes 0 → 61,673.
  FK integrity 100% (0 orphan drug_packages). The original FK bug is
  fixed.

### LOADER-BUG-01a — residual `ndc_11` unique constraint violations
- **Status**: **fixed** (commit `d2d7eea`) — drugs went from 25K → 99,038.
  Some legitimate duplicates by `ndc_11` are still evicted by the
  last-seen dedup; full count is ~99K vs FDA-published ~130K. Acceptable.
- **Priority**: was P1 — RESOLVED
- **Symptom**: After BUG-01 fix, the loader still reports
  `records_errored = 267,264`. Spot-check of the error log shows the
  pattern is `Key (ndc_11)=(00009000309) already exists` —
  UniqueViolation on `uq_drugs_ndc_11`.
- **Root cause**: The FDA NDC source file legitimately contains multiple
  `product_id` values that share the same `ndc_11` (relabeled or
  reformulated products). The loader's
  `pg_insert(Drug.__table__).on_conflict_do_update(index_elements=["product_id"])`
  resolves conflicts on `product_id` only — when two different
  `product_id`s collide on `ndc_11`, the UNIQUE index `uq_drugs_ndc_11`
  fires and the batch fails.
- **Suggested fix**: per-batch dedup by `ndc_11` BEFORE insertion (keep
  the row with the latest `start_marketing_date`, fall back to last-seen
  on ties). The dedup pattern already exists in
  `modules/pharmacy-directory/src/services/ncpdp_ingestion.py`
  `_insert_packages` for the same reason.
- **Repro**:
  ```bash
  source infrastructure/scripts/switch_env.sh dev
  python scripts/load_fda_ndc.py 2>&1 | grep "already exists" | wc -l
  ```

---

## LOADER-BUG-02 — `scripts/load_ncpdp.py` main table empty after success
- **Status**: **fixed** (commit `548e782`) — same single-transaction-rollback
  pattern as BUG-01/03/05. Per-batch `self._db.commit()` added inside
  both `_upsert_batch` and `_delete_insert_batch`. Result:
  ncpdp_pharmacies 0 → 81,693, plus all 11 other child tables now
  populated.
- **Priority**: was P1 — RESOLVED

### LOADER-BUG-02a — `ncpdp_pharmacy_medicaid` still empty after BUG-02 fix
- **Status**: open
- **Priority**: P2
- **Symptom**: After the BUG-02 fix, 12 of 13 NCPDP child tables
  populate. The exception is `pharmacy_dir.ncpdp_pharmacy_medicaid`:
  the parser yields multiple rows for the same `(ncpdp_provider_id, state)`
  tuple, and the table has a unique constraint
  `uq_ncpdp_md_ncpdp_state` on those columns. Every batch fails with
  `psycopg2.errors.UniqueViolation: duplicate key value violates unique
  constraint "uq_ncpdp_md_ncpdp_state" Key (ncpdp_provider_id, state)=(5938797, TX) already exists.`
- **Suggested fix**: per-batch dedup by `(ncpdp_provider_id, state)`
  before insert in `_delete_insert_batch` (the medicaid table is in
  `_DELETE_INSERT_TABLES`, not the upsert path). Same dedup pattern as
  the FDA NDC `ndc_11` fix from LOADER-BUG-01a.

## LOADER-BUG-02-LEGACY-BODY (kept for reference)
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

## LOADER-BUG-03 — `scripts/load_cms_nadac.py` `StringDataRightTruncation`
- **Status**: **fixed** (commit `b562e58`)
- **Priority**: P1 (was)
- **Module**: drug-database
- **Loader**: `scripts/load_cms_nadac.py`
- **Original tracking note**: "missing ON CONFLICT" — this was wrong.
  The loader already used `pg_insert().on_conflict_do_update()`. The
  ACTUAL bug was a schema-vs-data mismatch.
- **Real root cause**: `drug_nadac_pricing.pharmacy_type_indicator` and
  `drug_nadac_pricing.otc` were declared `VARCHAR(1)`, but the CMS NADAC
  source file publishes multi-character values for
  `pharmacy_type_indicator` (notably `C/I` meaning "Chain/Independent
  combined", which is 3 characters). Every batch hit
  `psycopg2.errors.StringDataRightTruncation: value too long for type
  character varying(1)`. The service's `rollback()` retried on a fresh
  transaction and repeated the same error — 474 MB of SQLAlchemy error
  dumps in 4 minutes.
- **Fix applied**:
  1. New migration
     `modules/drug-database/alembic/versions/0006_widen_nadac_indicators.py`
     widens both `pharmacy_type_indicator` and `otc` to `VARCHAR(5)` on
     `drug_nadac_pricing` AND `drug_nadac_pricing_history`.
  2. Per-batch `self._db.commit()` added inside `_upsert_batch` in
     `modules/drug-database/src/services/pricing_ingestion.py` (same
     pattern as the BUG-01 fix to `ndc_ingestion.py`).
- **Result**: 0 rows → 26,044 inserted + 338,487 updated. Log no longer
  explodes. Duration 550s for the full file.

### LOADER-BUG-03a — residual 478K errored NADAC rows
- **Status**: **diagnosed** — root cause known, fix not yet applied
- **Priority**: P2
- **Symptom**: `records_errored = 478,354` in the post-fix run. Source
  has ~2M rows; ~17% are erroring.
- **Root cause** (identified in session 2026-04-15 review):
  `modules/drug-database/src/services/pricing_ingestion.py:185`
  `_validate_nadac_row()` calls
  `nadac_per_unit = _require_decimal(raw.get("nadac_per_unit"), "nadac_per_unit")`
  which raises `ValueError` on any row where `nadac_per_unit` is null,
  empty, or non-decimal. The CMS NADAC source legitimately publishes
  rows with NULL prices for drugs that are discontinued or temporarily
  unavailable.
  The DB schema reinforces the rejection:
  `drug_database.drug_nadac_pricing.nadac_per_unit numeric(18,6) NOT NULL`.
- **Required fix** (schema + code, both needed):
  1. Alembic migration to drop `NOT NULL` from
     `drug_database.drug_nadac_pricing.nadac_per_unit` AND
     `drug_nadac_pricing_history.nadac_per_unit`.
  2. Change `_require_decimal` call site to a soft `_parse_decimal`
     that returns `None` on missing/invalid input.
  3. Re-run loader. Expected new error count: < 50K (other validation
     issues like invalid `ndc_11` patterns).
- **Architectural decision needed**: storing NULL-price NADAC rows is
  the right call for analytics (you want to know the drug exists in
  NADAC even when the price is temporarily gone), but it changes the
  meaning of the table — downstream queries that join on
  `nadac_per_unit IS NOT NULL` will need to be checked.
- **Repro**: validated by reading the loader code path. Did not need a
  full 9-minute re-run because the validation logic is deterministic.

---

## LOADER-BUG-04 — `scripts/load_new_sources.py rxnorm` uncontrolled download / partial commit
- **Status**: **partial fix** (commit `53a21d1`) — `--sample N` flag now
  works for any ingester, not just rxnorm. Verified `--sample 10000`
  loads 9,995 rxnorm_relationships in 17.5s. Still pending: download
  caching, resume capability, concept ordering, and the new
  LOADER-BUG-04a parser-alignment bug found while testing.
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

### LOADER-BUG-04a — RxNorm parser column alignment bug
- **Status**: open
- **Priority**: P1 for rxnorm load (concepts table is the FK target for
  the other rxnorm tables — without it, the relationships are orphaned)
- **Discovered**: while testing the `--sample 10000` fix from
  LOADER-BUG-04 above. The loader processed 10K records but
  `rxnorm_concepts` stayed at 0 due to
  `psycopg2.errors.StringDataRightTruncation: value too long for type
  character varying(1)` on every concept INSERT.
- **Root cause**: the parameter values in the failing INSERT show field
  misalignment. Examples from the actual SQL parameters:
  - `srl_m1: 'Paracetamol'` — `srl` column (Source Restriction Level)
    is `VARCHAR(1)` and should be a code like `'N'`, but the parser is
    putting drug names there
  - `code_m1: 'Acetaminophen 325 MG Oral Tablet'` — `code` should be a
    short identifier, not a full name
  - `tty_m1: 'ATC'` and `sab_m1: None` — these look swapped relative to
    the canonical RXNCONSO column order
- **Located in**: `shared/data_ingestion/sources/rxnorm.py` — the
  RXNCONSO RRF reader. The RxNorm RRF format has a specific column
  order; the parser is reading them in the wrong sequence somewhere.
- **Suggested fix**: check the RxNorm RRF spec
  (https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html)
  against the parser's column index map. Likely a one-line off-by-one
  or a swap of two adjacent fields.
- **Repro**:
  ```bash
  source infrastructure/scripts/switch_env.sh dev
  python scripts/load_new_sources.py rxnorm --sample 100
  psql ... -c "SELECT COUNT(*) FROM drug_database.rxnorm_concepts;"  # → 0
  ```

---

## LOADER-BUG-05 — `scripts/load_orange_book.py` silent failure
- **Status**: **fixed** (commit `4d31d9a`) — same single-transaction-
  rollback pattern as BUG-01/02/03. Per-batch `self._db.commit()` added
  to `_upsert_product_batch`, `_replace_patents`, and `_replace_exclusivity`.
  Result: drug_orange_book 0 → 44,083, drug_patents 0 → 7,858,
  drug_exclusivity 0 → 1,000.
- **Priority**: was P1 — RESOLVED

### LOADER-BUG-05a — drug_exclusivity only loads 1K of expected ~10K
- **Status**: open
- **Priority**: P3
- **Symptom**: After BUG-05 fix, drug_exclusivity gets 1,000 rows but
  the FDA Orange Book exclusivity file should have ~10K rows. The
  loader log shows `records_errored=18,054` — the missing exclusivity
  rows are being rejected. Same likely cause as LOADER-BUG-01a: the
  source has duplicate `(appl_type, appl_no, product_no, exclusivity_code,
  exclusivity_date)` tuples that need per-batch dedup.
- **Suggested fix**: dedup `enriched` list in `_replace_exclusivity`
  by the unique-constraint key tuple before insert.

## LOADER-BUG-05-LEGACY-BODY (kept for reference)
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
- **Status**: **fixed and verified** (xlrd added in `ec48e9d`,
  end-to-end run committed in `3666d1c`)
- **Priority**: P3
- **Module**: drug-database
- **Loader**: `scripts/load_cms_asp.py`
- **Symptom**: Loader exits in <1s with `xlrd is required to parse .xls
  files. Install it with: pip install xlrd`.
- **Fix applied**: `uv add xlrd` — added to `pyproject.toml` dependencies.
- **Verification** (commit `3666d1c`): full run against dev produced
  `records_inserted = 885`, `records_errored = 0`,
  `drug_database.drug_asp_pricing = 885 rows`. CLOSED.

---

## MISSING-MIGRATIONS-01 — modules/billing/ has no alembic history
- **Status**: **fixed** (commit `7807b8e`)
- **Priority**: was P1 — RESOLVED. Feature work can now touch billing
  schema safely.
- **Resolution**: created
  `modules/billing/alembic.ini`, `alembic/env.py`,
  `alembic/script.py.mako`, and
  `alembic/versions/0001_billing_baseline.py` (723 lines, 25 tables in FK
  dependency order with ondelete policies). Applied to dev (fresh
  upgrade), mock (alembic stamp because `_bootstrap_billing.py` had
  already created the rows and we needed to preserve the 100K demo
  claim_records), and prod (fresh upgrade). Removed
  `infrastructure/scripts/_bootstrap_billing.py`. Removed dead
  `modules/billing/migrations/` legacy stub.
- **Historical context** (kept for reference): **P1** — must have been
  resolved before any feature work touches
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
- **Status**: **fixed** (commit `7807b8e`)
- **Priority**: was P2 — RESOLVED.
- **Resolution**: created
  `modules/payment-processing/alembic.ini`, `alembic/env.py`,
  `alembic/script.py.mako`, and
  `alembic/versions/0001_payment_processing_baseline.py` (280 lines, 8
  tables: vendor_adapters, ach_return_codes, ofac_sdn, submissions,
  settlements, vendor_health_log, ofac_alerts, payee_enrollments).
  Applied cleanly to dev/mock/prod. Both OFAC tables now exist — when
  the OFAC SDN loader is built (still tracked separately), it has
  somewhere to write. Added `payment-processing` to
  `infrastructure/scripts/run_migrations.sh` MODULES list.
- **Historical context** (kept for reference): P2 (same blast radius as billing but the OFAC path is not
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
- **Status**: **wrapper written** (commit `ecd411d`), blocked on
  `SAM_API_KEY` env var
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
- **Wrapper status** (`scripts/load_sam.py`, commit `ecd411d`):
  CLI wrapper exists, mirrors `scripts/load_oig_leie.py` shape, calls
  `SamExclusionsIngester(db_session=session).run(run_type="manual_trigger")`.
  Verified that the wrapper raises a clear error when `SAM_API_KEY` is
  unset:
  `_SamApiKeyMissingError: SAM_API_KEY environment variable not configured.
  Register at sam.gov/api to obtain a key.`
- **Remaining blocker**: register at sam.gov/api → free API key → set
  `SAM_API_KEY=...` in `.env.dev/.env.mock/.env.prod` → run loader.
  Expected row count after key obtained: 120,000–160,000 active
  exclusions as of 2026-01.

---

## MISSING-LOADER-08 — `shared.government_program_bins` has no state Medicaid loader
- **Status**: **wrapper written and working** (commit `ecd411d`); 43 of
  56 states covered; 51 row-validation errors to clean up
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
- **Wrapper status** (`scripts/load_medicaid_bins.py`, commit `ecd411d`):
  CLI wrapper exists, iterates over the 5 regional CSVs under
  `data/reference/medicaid/` (midwest, northeast, south_central,
  southeast, west) and calls `StateMedicaidBinLoader.load_csv()` per
  region.
- **Prerequisite migration** (commit `ecd411d`):
  `modules/core-platform/alembic/versions/0011_gpb_id_to_uuid.py`
  fixes a schema drift between migration 0009 (created `id` as
  `VARCHAR(36)`) and the ORM model (declared `PG_UUID(as_uuid=True)`).
  Without this, ORM upserts through the model failed with `operator
  does not exist: character varying = uuid`.
- **Result** (against dev, mock, prod — all three now identical):
  - rows_upserted: 219
  - states covered: 43 / 56
  - states missing: AS, AZ, CO, CT, GU, ID, ME, MP, NH, PR, VI, VT, WY
  - validation errors: 51 (specific source-CSV row issues —
    LOADER-BUG-08a below)
- **The `seed_reference_shim.py` 10-state seed is now superseded** by
  this loader for any environment with the regional CSVs present. The
  shim's 10 rows still exist and the loader's ON CONFLICT DO UPDATE
  refreshes them.

### LOADER-BUG-08a — 51 row validation errors in regional Medicaid CSVs
- **Status**: open
- **Priority**: P3 (clean-up, not a blocker)
- **Symptom**: `_validate_row()` rejects 51 rows across the 5 regional
  CSVs. Northeast: 10 errors, south_central: 16, west: 23, midwest: 2.
  Cause is per-row data-quality issues in the source CSVs themselves
  (missing required fields, malformed BIN values, etc.).
- **Suggested fix**: dump the rejected rows + their error reasons,
  audit each one against the original source URL in the row's `source`
  column, fix the CSV. This is data-curation work, not loader work.

### LOADER-BUG-08b — 13 states/territories with no Medicaid coverage
- **Status**: open
- **Priority**: P2 (claim routing for these states is silently broken)
- **Missing**: AS, AZ, CO, CT, GU, ID, ME, MP, NH, PR, VI, VT, WY
- **Suggested fix**: research each state's Medicaid PBM / FFS BIN/PCN
  configuration from the state pharmacy provider portal, add rows to
  the appropriate regional CSV under `data/reference/medicaid/`. Most
  of the missing list is small/territorial; the noteworthy gaps are
  AZ (large state) and CT/CO (mid-size).

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
