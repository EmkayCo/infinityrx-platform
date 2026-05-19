# SP-3 Plan A1 Sub-session Ledger

**Date:** 2026-05-18  
**Scope:** Models + Alembic 0008 + RLS + Indexes  
**Plan file:** `docs/superpowers/plans/2026-05-18-sp3-plan-a1-models-migration.md`  
**Authored by:** Sub-agent (model/migration slice)  
**Next dispatch:** Codex Plan A1 consult → then A2 (services + endpoints)

---

## Scope summary

This plan covers exactly the schema layer of SP-3 Plan A — nothing more:

| Deliverable | File(s) |
|---|---|
| 6 new ORM model classes | `modules/reclaimrx/src/models/tables.py` (appended) |
| 11 new columns on Investigation | `modules/reclaimrx/src/models/tables.py` (in-place edit) |
| 1 new column on PaymentHold (`status`) | `modules/reclaimrx/src/models/tables.py` (in-place edit) |
| Alembic migration 0008 | `modules/reclaimrx/alembic/versions/0008_sp3_extensions.py` |
| Unit tests (SQLite, no PG) | `modules/reclaimrx/tests/unit/test_new_models_instantiate.py` |
| Unit tests (index declarations) | `modules/reclaimrx/tests/unit/test_model_indexes.py` |
| Integration test (migration) | `modules/reclaimrx/tests/integration/test_migration_0008.py` |
| Integration test (RLS null-deny) | `modules/reclaimrx/tests/integration/test_rls_null_deny.py` |

---

## Tasks

| # | Task | Verified by |
|---|---|---|
| T1 | Add 6 new model classes + extend Investigation + PaymentHold in tables.py | test_new_models_instantiate.py |
| T2 | Write migration 0008 (CREATE + ALTER + RLS + indexes + grants) | test_migration_0008.py + alembic up/down |
| T3 | RLS null-deny acceptance test | test_rls_null_deny.py |
| T4 | Index declaration unit tests | test_model_indexes.py |
| T5 | Coverage gate (95%+ models slice; 100% financial columns) | pytest --cov |

---

## BLOCKS resolved

| Codex BLOCK | How resolved |
|---|---|
| BLOCK 1: `released_by` already exists at tables.py:607 | Plan explicitly documents the existing columns and adds ONLY `status` |
| BLOCK 2: Migration used wrong table names (`investigation`, `payment_hold`) | Plan uses exact `__tablename__` values from audit: `reclaimrx_investigations`, `reclaimrx_payment_holds`; new tables in `reclaimrx` schema without prefix |
| BLOCK 3: Plan used invented `TenantScopedBase` | Plan uses `Base` (from `src._shim.db`) + explicit `tenant_id: Mapped[str]` per existing tables.py pattern; new tables document the `TenantScopedMixin` import path but use the existing String(36) pattern for ORM-level consistency |
| BLOCK 5: `hold.hold_amount` field does not exist | Plan adds `hold_amount` as a new column on Investigation (the model that tracks financial amounts per spec §5.2); PaymentHold uses `amount_threshold` (existing) |

---

## Key ground-truth facts applied

- GUC: `app.current_tenant_id` (from 0002/0007 — NOT `app.tenant_id` as spec said)
- Migration schema: `reclaimrx`; existing ORM tables are in `public` schema with `reclaimrx_` prefix
- UUID columns in migrations: `postgresql.UUID(as_uuid=False)`
- Advisory lock (for Plan A2/A3): use `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF`
- No APScheduler; use `asyncio.create_task + croniter` pattern from `shared/data_ingestion/scheduler.py`
- `EventEnvelope` fields: `event_type`, `timestamp` (not `type`, `emitted_at`)
- `CurrentUser`: dataclass with `.roles` / `.has_role()` (not dict)

---

## Boundaries (what A1 does NOT do)

- No API endpoints
- No services (state machine, threshold service, outbox dispatcher)
- No consumers (accumulator consumer)
- No graph analysis job wiring
- No contract layer (packages/contract)
- No frontend scaffold
- No D14 app factory bindings
