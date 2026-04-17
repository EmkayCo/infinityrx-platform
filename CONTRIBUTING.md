# Contributing to InfinityRx

Orientation for engineers working on the InfinityRx platform. Project
principles, architectural rules, and domain conventions live in the
root `CLAUDE.md` and the per-rule files under `.claude/rules/`. This
file is the shorter, operational companion.

## Repository discipline

### Local-only by design

This repository intentionally has **no remote push target**. All
development happens on a single workstation backed by external,
operator-managed backups. Consequences:

- `git push` is not part of any wave's done-criteria.
- `git merge` is local. Conflicts get resolved in-repo.
- There is no PR review gate — review happens pre-merge in conversation
  and via `.claude/agents/tier1-core/` QA sweeps.
- CI is local (`pytest` + Makefile targets), not hosted.

If you find yourself wanting to `git push`, stop — that is not the
workflow. A future collaboration model may change this; until then,
treat the local clone as authoritative.

### Branch layout

- `main` — production-deployable, updated only by merging `develop`.
- `develop` — integration branch. Wave-branches merge here with
  `--no-ff` so the wave boundary stays visible in `git log`.
- `wave-N-<topic>` — per-wave feature branches.
- `loader/base-refactor` — long-running branch preserved as SAM-loader
  insurance. Leave it. Do not merge, do not rebase, do not delete.

### Untracked paths

The following paths may sit in your working tree untracked across
sessions — don't try to clean them up unless you own them:

- `modules/mtm-clinical/` — placeholder for a future module.
- `.claude/scheduled_tasks.lock` — runtime lock file.
- `portal/operator/next-env.d.ts` — Next.js auto-regenerates this on
  dev-server start.

## Alembic migrations

### 32-character revision ID limit

`alembic_version.version_num` is `VARCHAR(32)` in every module's
bookkeeping table. Revision IDs longer than 32 chars cause the DDL
to succeed then trip a `StringDataRightTruncationError` on the
version-pointer UPDATE — leaving a half-applied state that needs a
manual `UPDATE alembic_version` to recover from.

Canonical naming: `NNNN_topic_area` (e.g. `0014_medical_code_refs`).
See `modules/core-platform/alembic/versions/README.md` for the fuller
pattern.

### Per-module migrations

Each module owns its alembic tree:

```
modules/core-platform/alembic/          → core + shared schema
modules/drug-database/alembic/          → drug_database schema
modules/pharmacy-directory/alembic/     → pharmacy_directory schema
modules/prescriber-directory/alembic/   → prescriber_dir schema
modules/billing/alembic/                → billing schema
modules/payment-processing/alembic/     → payment_processing schema
```

Run all modules against dev with:

```bash
./infrastructure/scripts/run_migrations.sh dev
```

## Environments

Three environments, one codebase. Switch with:

```bash
source infrastructure/scripts/switch_env.sh {dev|mock|prod}
```

Rules in `CLAUDE.md` cover which data goes where; the short version:

- Reference data (NPPES, NDC, ICD-10, HCPCS, …): shared read-only.
- Operational / PHI data: isolated per environment. NEVER copy prod to dev.
- Tenant config: isolated per environment.

## Data-ingestion loaders

Reference-data loaders live under `shared/data_ingestion/sources/` and
are invoked via the `scripts/load_*.py` CLIs. Each loader is a
`DataSourceIngester` subclass implementing `download`, `parse`, and
`load`. Bulk writes use `flush_upsert_batch` (VALUES path) from
`shared/data_ingestion/batching.py` by default; opt in to
`flush_upsert_batch_copy` (COPY-staging path) when the loader's size
justifies it — see `data/reference/nppes/README.md §7` for the
retrofit criteria.

Each loader has a companion scheduler entry in
`shared.data_ingestion.scheduler.DEFAULT_SCHEDULES` that picks the
cadence. Per-dataset operational docs live at
`data/reference/<dataset>/README.md`.

## Running tests

```bash
# Default: all fast tests
pytest

# One module / one topic
pytest shared/data_ingestion/tests/
pytest modules/billing/tests/

# Coverage floor: 100% on financial / PHI / security / auth paths;
# 99% branch coverage on all other active code. Enforced via
# pyproject.toml config; falls below → fail.
pytest --cov --cov-fail-under=99
```

### SQLite-on-tests compatibility

Test fixtures run against in-memory SQLite with SAVEPOINT-based
isolation (LESSON-001) and `_UUIDString` type-decorator for UUID
columns (LESSON-007). Reference-table tests also patch `JSONB` to
`JSON` on target tables. See `shared/data_ingestion/tests/conftest.py`
and `shared/data_ingestion/tests/test_medical_codes.py` for the
full pattern.

Tests that need to import a module's `src/` use a namespaced-load
trick (see `test_nppes.py`'s `_load_file_as`) so different modules'
`src.*` namespaces don't collide when multiple modules are exercised
in one pytest session.

## When in doubt

- Root `CLAUDE.md` is the architectural source of truth.
- `.claude/rules/*.md` contains per-concern rules (financial-precision,
  PHI, security, testing, event-bus, etc.).
- `docs/lessons-learned.md` records non-obvious bugs and their fixes.
- `data/reference/<dataset>/README.md` contains per-loader operational docs.

If a convention isn't written down and the answer isn't obvious from
code, write it down in the appropriate file above and then follow it.
