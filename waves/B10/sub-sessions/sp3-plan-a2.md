# SP-3 Plan A2 Sub-Session Ledger

**Date:** 2026-05-18
**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md`
**Scope:** Outbox service, dispatcher, scheduler, DLQ real repo, Redis idempotency key helper, cleanup + audit + DLQ depth jobs, D14 create_app() 6-binding integration test.

---

## Pre-flight findings

| Check | Finding |
|---|---|
| `OutboxEvent` model | **Depends on Plan A1** — must exist before Task 1 |
| `shared/events/types.py` EventEnvelope | field names: `event_type`, `tenant_id` (uuid.UUID), `timestamp` — confirmed (audit §2) |
| `shared/events/idempotency.py` | `PostgresIdempotencyStore`, `InMemoryIdempotencyStore`, `idempotent_handler` confirmed present |
| `shared/events/dlq.py` | `DLQRepository` Protocol, `DLQService`, `build_dlq_router` confirmed present |
| `shared/events/jobs/cleanup_processed_events.py` | `run_cleanup(engine)` confirmed present, unscheduled |
| `shared/data_ingestion/scheduler.py` | `asyncio.create_task + croniter` pattern — the scheduling primitive |
| APScheduler | NOT installed, NOT used anywhere (audit §7 + docs/audit/h-07) |
| `modules/reclaimrx/src/main.py` D14 state | 3/6 mounted (Security, RateLimit, DLQ router); 3/6 missing (cleanup, DLQ monitor, audit chain) |
| `_EmptyDLQRepository` | Stub returning [] — LESSON-006 violation; Plan A2 replaces it |
| Advisory lock hash | Must use `zlib.crc32(...) & 0x7FFFFFFF` NOT Python `hash()` (codex BLOCK 7) |

---

## Codex R1 BLOCKS resolved by this plan

| Block | Issue | Resolution in Plan A2 |
|---|---|---|
| BLOCK 4 | Wrong EventEnvelope fields (`type`, `emitted_at`) | All tasks use `event_type`, `tenant_id: uuid.UUID`, `timestamp` (auto-set) |
| BLOCK 7 | Python `hash()` for advisory lock — PYTHONHASHSEED-randomized | `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF` documented in dlq_monitor.py, enforced in Plan A3 graph job |
| BLOCK 8 | TDD discipline missing | Every task: write failing test → confirm ImportError → implement → confirm pass |

---

## Task summary

| Task | Deliverable | TDD |
|---|---|---|
| 1 | `tests/unit/test_outbox_service.py` — 3 tests | Failing tests only |
| 2 | `src/outbox/event_outbox.py` — OutboxService | Implement → pass Task 1 |
| 3 | `tests/unit/test_outbox_dispatcher.py` — 3 tests | Failing tests only |
| 4 | `src/outbox/outbox_dispatcher.py` — OutboxDispatcher | Implement → pass Task 3 |
| 5 | `tests/unit/test_dlq_repository.py` + `test_redis_idempotency.py` | Failing tests only |
| 6 | `src/events/dlq_repository.py` + `src/events/idempotency_keys.py` | Implement → pass Task 5 |
| 7 | `tests/unit/test_reclaimrx_scheduler.py` — scheduler + audit chain + DLQ monitor | Failing tests only |
| 8 | `src/jobs/reclaimrx_scheduler.py` + `audit_chain_job.py` + `dlq_monitor.py` | Implement → pass Task 7 |
| 9 | `tests/integration/test_create_app_bindings.py` (6 tests) + extend `main.py` | Failing tests → wire → pass |

---

## Coverage requirements

- `src/outbox/event_outbox.py` — 100% (security/idempotency)
- `src/events/dlq_repository.py` — 100% (security)
- `src/events/idempotency_keys.py` — 100% (security/tenant-isolation)
- `src/jobs/audit_chain_job.py` — 100% (HIPAA)
- `src/outbox/outbox_dispatcher.py` — 100% (security)
- `src/jobs/reclaimrx_scheduler.py` — 95%+
- `src/jobs/dlq_monitor.py` — 95%+

---

## Files created by Plan A2

```
modules/reclaimrx/src/outbox/__init__.py
modules/reclaimrx/src/outbox/event_outbox.py
modules/reclaimrx/src/outbox/outbox_dispatcher.py
modules/reclaimrx/src/events/dlq_repository.py
modules/reclaimrx/src/events/idempotency_keys.py
modules/reclaimrx/src/jobs/reclaimrx_scheduler.py
modules/reclaimrx/src/jobs/audit_chain_job.py
modules/reclaimrx/src/jobs/dlq_monitor.py
modules/reclaimrx/tests/unit/test_outbox_service.py
modules/reclaimrx/tests/unit/test_outbox_dispatcher.py
modules/reclaimrx/tests/unit/test_dlq_repository.py
modules/reclaimrx/tests/unit/test_redis_idempotency.py
modules/reclaimrx/tests/unit/test_reclaimrx_scheduler.py
modules/reclaimrx/tests/integration/test_create_app_bindings.py
```

## Files extended by Plan A2

```
modules/reclaimrx/src/main.py  — DLQ real repo + scheduler startup + lifespan teardown
```

---

## Blockers / open items

- Plan A1 must complete before Task 1 (OutboxEvent table needed).
- `modules/reclaimrx/src/_shim/db.py` — executor must grep to find the async engine factory or create one wrapping the sync URL. Do not invent a name.
- `shared/db/models/events.py` — executor must verify `EventDLQEntry` has `id`, `event_id`, `tenant_id`, `event_type`, `envelope`, `failure_reason`, `attempt_count`, `dlq_topic`, `status`, `first_failed_at`, `last_failed_at` columns before writing DLQ repo.
