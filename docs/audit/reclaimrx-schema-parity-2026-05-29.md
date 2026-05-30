# ReclaimRx Schema Parity Report — 2026-05-29

**Task:** Phase 0 verification gate (Task 0.2), feat/reclaimrx-csv-detection  
**Branch:** feat/reclaimrx-csv-detection  
**Compared:** `reclaimrx_scratch` (fresh migration) vs `infinityrx_dev.reclaimrx` (dev DB)  
**Both at revision:** `0008_ml_detector_seed`

## Migration Chain Execution

Scratch DB created from `template0` (bypassing collation-version mismatch on template1).  
Schema `reclaimrx` pre-created before alembic ran (alembic needs the schema to exist before writing `alembic_version`; migration 0001 also runs `CREATE SCHEMA IF NOT EXISTS`, making the pre-create a no-op at that step).

Alembic output (all 8 steps green):

```
INFO Running upgrade  -> 0001_reclaimrx_baseline
INFO Running upgrade 0001_reclaimrx_baseline -> 0002_reclaimrx_rls
INFO Running upgrade 0002_reclaimrx_rls -> 0003_detection_rule_framework
INFO Running upgrade 0003_detection_rule_framework -> 0004_baseline_cache
INFO Running upgrade 0004_baseline_cache -> 0005_eval_log_runwide_skips
INFO Running upgrade 0005_eval_log_runwide_skips -> 0006_ml_detector_registry
INFO Running upgrade 0006_ml_detector_registry -> 0007_flagged_npis
INFO Running upgrade 0007_flagged_npis -> 0008_ml_detector_seed
```

Scratch `reclaimrx.alembic_version` = `0008_ml_detector_seed`. Dev confirmed at same revision.

## Section 1: Tables Present

Both DBs: 16 tables in `reclaimrx` schema.

```
alembic_version, anomalies, anomaly_audit_log, baseline_cache,
case_anomaly_links, case_assignments, case_number_sequences, csv_upload_rows,
detection_rule_evaluation_log, detection_rule_instances, detection_rule_types,
detection_runs, flagged_npis, ml_detector_registry, ml_training_runs, recoup_cases
```

DELTA: none.

## Section 2: Columns (name, data_type, udt_name, is_nullable, column_default)

All 15 user tables (excluding alembic_version) verified column-by-column.  
DELTA: none. Column order, types, nullability, and server defaults are identical.

## Section 3: CHECK Constraints

62 CHECK constraints across both DBs. Every constraint name and `pg_get_constraintdef()` output is identical.  
DELTA: none.

## Section 4: Indexes

57 indexes (including PK indexes, partial indexes, BRIN index on eval_log) verified by name and `indexdef`.  
Partial indexes verified: `ix_reclaimrx_eval_log_anomaly WHERE anomaly_id IS NOT NULL`,
`ix_reclaimrx_rule_instances_active WHERE termination_date IS NULL`,
`uq_flagged_npis_active_per_npi WHERE is_active = true`.  
DELTA: none.

## Section 5: RLS — Policies and Row-Security Flags

13 RLS policies present on both DBs (all tenant-scoped tables). Policy names, permissive flag, cmd, and qual are identical.  
Row-security enabled+forced: anomalies, anomaly_audit_log, baseline_cache, case_anomaly_links, case_assignments, case_number_sequences, csv_upload_rows, detection_rule_evaluation_log, detection_rule_instances, detection_runs, flagged_npis, ml_training_runs, recoup_cases — identical on both.  
No RLS on: alembic_version, detection_rule_types, ml_detector_registry — identical on both.  
DELTA: none.

## Section 6: Grants

DELTA FOUND — documented, not a defect:

| Grantee | Scratch privileges | Dev privileges |
|---|---|---|
| `ifx_dev_app` | DELETE, INSERT, SELECT, UPDATE | DELETE, INSERT, REFERENCES, SELECT, TRIGGER, TRUNCATE, UPDATE |
| `ifx_dev_admin` | DELETE, INSERT, SELECT, UPDATE | DELETE, INSERT, SELECT, UPDATE |
| `ifx_prod_admin` | DELETE, INSERT, SELECT, UPDATE | DELETE, INSERT, SELECT, UPDATE |

`ifx_dev_admin` and `ifx_prod_admin` are identical between scratch and dev.

`ifx_dev_app` in dev has three extra privileges: `REFERENCES`, `TRIGGER`, `TRUNCATE`. These are not present in the migration scripts. The migration grants are issued via `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA reclaimrx TO ifx_dev_app` (migration 0001). The additional REFERENCES/TRIGGER/TRUNCATE on dev were granted outside of the migration chain — either via a superuser grant or via `ALTER DEFAULT PRIVILEGES` in another schema migration that applied globally. This is the ad-hoc migration history showing through.

**Assessment:** This delta is expected given dev's ad-hoc migration history. It is not a functional concern for the CSV detection pipeline — REFERENCES, TRIGGER, and TRUNCATE are not required by any reclaimrx service path. The World-A migration chain is correct; dev has extra privileges from out-of-band grants. Not a blocking finding.

## Section 7: Catalog Data

### ml_detector_registry (5 rows — expected match)

| detector_name | feature_schema_class | is_placeholder |
|---|---|---|
| member_cohort_outlier | reclaimrx.detection.ml.sklearn_detector.MemberFeatures | t |
| nq_target_clustering | reclaimrx.detection.ml.sklearn_detector.NqClusterFeatures | t |
| pharmacy_behavioral_baseline | reclaimrx.detection.ml.sklearn_detector.PharmacyFeatures | t |
| prescriber_baseline | reclaimrx.detection.ml.sklearn_detector.PrescriberFeatures | t |
| reject_resubmit_pattern | reclaimrx.detection.ml.sklearn_detector.RejectResubmitFeatures | t |

Both DBs: identical 5 rows.  
DELTA: none.

### detection_rule_types count

Both DBs: `count(*) = 0`.  
DELTA: none.

## Summary

| Section | Result |
|---|---|
| Tables | PASS — identical 16-table set |
| Columns | PASS — identical (all tables, all columns) |
| CHECK constraints | PASS — identical 62 constraints |
| Indexes | PASS — identical 57 indexes incl. partial/BRIN |
| RLS | PASS — identical policies and row-security flags |
| Grants | DELTA (documented) — dev has REFERENCES/TRIGGER/TRUNCATE on ifx_dev_app from ad-hoc out-of-band grant; not in migration chain; not functional |
| ml_detector_registry | PASS — exact 5-row match |
| detection_rule_types | PASS — 0 rows both |

**Overall verdict: PARITY CONFIRMED.** The World-A migration chain reproduces dev's schema and catalog data exactly, modulo one non-functional extra-privilege delta on dev that traces to its ad-hoc migration history (not the migration files).
