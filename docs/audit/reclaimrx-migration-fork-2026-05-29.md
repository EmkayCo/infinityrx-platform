# ReclaimRx Migration Fork — Tech-Debt Document

**Date:** 2026-05-29  
**Branch:** feat/reclaimrx-csv-detection  
**Severity:** Medium (blocks automated CI migration; does not block dev runtime)

## Background

The reclaimrx module was built in Wave 42–44b with its own Alembic migration chain
(`modules/reclaimrx/alembic/`), but was never included in
`infrastructure/scripts/run_migrations.sh`. The runner script discovers modules by
looking for `alembic.ini` at the module root (`modules/{name}/alembic.ini`). The
reclaimrx ini was intentionally placed one level deeper at
`modules/reclaimrx/alembic/alembic.ini` to prevent the runner from attempting a bare
`upgrade head` — which would fail because there are two heads.

As a result, reclaimrx migrations were applied to `infinityrx_dev` ad-hoc by hand
rather than through the standard runner, and the module is absent from
`tests/integration/conftest.py`'s `_MIGRATION_MODULES` list.

## The Fork

The migration chain has two 0008-series leaves, both with `down_revision = 0007_flagged_npis`:

```
0001 → 0002 → 0003 → 0004 → 0005 → 0006 → 0007 ─┬→ 0008_ml_detector_seed   (World-A / dev)
                                                   └→ 0008_sp3_extensions      (World-B / SP-3)
```

### World-A: 0008_ml_detector_seed
- Seeds 5 placeholder rows into `reclaimrx.ml_detector_registry`.
- No DDL changes. Pure DML seed.
- Applied to `infinityrx_dev`. This is the live dev state.
- What the CSV detection pipeline (Task 0.2+) runs against.

### World-B: 0008_sp3_extensions
- Creates 6 new SP-3 tables in the `public` schema with `reclaimrx_*` prefix:
  `reclaimrx_graph_runs`, `reclaimrx_fraud_rings`, `reclaimrx_accumulator_anomalies`,
  `reclaimrx_threshold_configs`, `reclaimrx_threshold_config_audits`, `reclaimrx_outbox_events`.
- ALTERs `reclaimrx_investigations` (adds 12 columns + 3 CHECK constraints + 3 indexes).
- ALTERs `reclaimrx_payment_holds` (adds status column + CHECK + index).
- These tables (`reclaimrx_investigations`, `reclaimrx_payment_holds`) are ORM models
  in `modules/reclaimrx/src/models/tables.py` but do NOT exist in the `reclaimrx` schema —
  they are in the `public` schema with the prefixed naming convention. They were created
  outside the Alembic migration chain (possibly by a prior manual DDL session).
- Cannot be applied to `infinityrx_dev` without the public-schema tables existing.

## Why This Cannot Self-Heal

`alembic upgrade head` fails when there are multiple heads — Alembic requires a merge
revision or an explicit named target. The two 0008 migrations cannot both apply to the
same DB (they both try to follow from 0007) without a merge migration that combines
them into a single linear chain.

## Deferred Work (ordered)

1. **Linearize heads.** Create a merge migration `0009_merge_world_a_b` with
   `down_revision = ('0008_ml_detector_seed', '0008_sp3_extensions')` and an empty
   upgrade/downgrade body. This makes the chain linear again and unblocks `upgrade head`.

2. **Make 0008_sp3_extensions portable.** The SP-3 migration ALTERs tables
   (`reclaimrx_investigations`, `reclaimrx_payment_holds`) that must already exist.
   Add `CREATE TABLE IF NOT EXISTS` guards or a prerequisite migration that creates the
   public-schema tables if they do not exist, so the migration is idempotent and
   self-contained.

3. **Re-include reclaimrx in run_migrations.sh.** Move `alembic.ini` back to the module
   root `modules/reclaimrx/alembic.ini` (or add reclaimrx explicitly to the runner with
   a named revision arg) after step 1 makes bare `upgrade head` safe.

4. **Add reclaimrx to _MIGRATION_MODULES.** In `tests/integration/conftest.py`, add
   `"reclaimrx"` to the list so integration tests run the full migration chain in CI
   and catch future regressions.

5. **Stamp dev DB.** After the merge migration is applied to dev, the alembic_version
   should reflect the merge revision. Until then, dev remains at `0008_ml_detector_seed`
   and the runner stays bypassed. Do NOT stamp dev to a revision it has not actually
   applied.

## No Action Required on Dev

Dev is healthy at `0008_ml_detector_seed`. The parity report (reclaimrx-schema-parity-2026-05-29.md)
confirms the migration chain exactly reproduces dev's schema and catalog data. No schema
changes to dev are needed or should be made as part of this tech-debt resolution.

## Files Involved

- `modules/reclaimrx/alembic/alembic.ini` — ini placement note
- `modules/reclaimrx/alembic/env.py` — exclusion comment
- `modules/reclaimrx/alembic/versions/0008_ml_detector_seed.py` — World-A head
- `modules/reclaimrx/alembic/versions/0008_sp3_extensions.py` — World-B head
- `infrastructure/scripts/run_migrations.sh` — reclaimrx absent
- `tests/integration/conftest.py` — `_MIGRATION_MODULES` missing reclaimrx
