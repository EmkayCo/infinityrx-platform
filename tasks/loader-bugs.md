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
  but no `alembic/`. Spot check needed for: payment-processing, reclaimrx,
  reporting, ai-nlp, dataiq, member-management, edi-compliance,
  medical-claims. Same root cause pattern — these will need MISSING-
  MIGRATIONS-02..09 entries when each is touched by feature work.
