# Alembic migrations — core-platform

This directory holds Alembic migrations for the `core-platform` module.
They manage the `core` schema and the shared cross-module tables in the
`shared` schema (reference data, audit, ingestion-tracking).

## Revision ID — 32-character limit

**`revision` strings must be ≤ 32 characters.** Alembic stores the
current revision in `core.alembic_version.version_num` which is
`VARCHAR(32)`. A longer ID causes the DDL portion of the migration to
succeed followed by a `StringDataRightTruncationError` on the
`UPDATE core.alembic_version SET version_num='<too-long-id>'` that
Alembic runs at the end — leaving the DB with the new schema but the
version pointer still on the prior revision. Rollback from that state
requires a manual `UPDATE core.alembic_version`.

Wave 13 tripped on this with the 35-char ID `0014_medical_code_reference_tables`;
the fix was to rename to `0014_medical_code_refs` (22 chars). See commit
`6855c25` for the before/after.

## Naming convention

Prefer `NNNN_topic_area` where:

- `NNNN` is the zero-padded sequential revision number.
- `topic_area` is a short (2-5 word) underscore-separated tag.

Examples in the current tree (all ≤ 32 chars):

```
0007_ingestion_tracking
0008_compliance_reference_tables
0012_ofac_sdn_tables
0013_drop_part_d_schema
0014_medical_code_refs
```

The `down_revision` string must match an existing revision exactly. Keep
it in sync when renaming.

## Running migrations

From the repo root:

```bash
./infrastructure/scripts/run_migrations.sh dev
```

The script:

1. Sources `.env.{dev,mock,prod}` into the subshell only (doesn't pollute
   the caller's env).
2. Forces `DATABASE_URL_SYNC=DATABASE_URL` because this module's
   `env.py` uses `async_engine_from_config` which requires an async
   driver — the otherwise-sync `DATABASE_URL_SYNC` with a psycopg2
   prefix would break it here. Modules whose `env.py` uses
   `engine_from_config` (sync) get a psycopg2 URL swapped in.
3. Runs `alembic upgrade head` from inside the module directory for
   each module that has an `alembic.ini`.

Production migrations refuse to run without `PROD_DB_PASSWORD` (and
other `PROD_*`) already exported — the prod env file has vault-injected
placeholders that local runs cannot resolve, so the script exits 2
rather than build a half-real URL.

## Module scope

Each module's `env.py` scopes Alembic to its own schema via `include_object`.
core-platform's scope is:

- Own schema: `core` (auth, sessions, audit, MFA fields)
- Shared-schema tables: ingestion-tracking, compliance reference tables,
  OFAC SDN, bank holidays, medical code refs

Migrations in other modules must not touch these tables, and vice
versa. Cross-module reference is via API calls and event-bus messages,
not direct SQL (LESSON-011 / project CLAUDE.md §Database Rules).
