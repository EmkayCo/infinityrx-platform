# Codex Adversarial Review — SP-3 Plan A2 — R1

**Date:** 2026-05-18
**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md`
**Audit ground truth:** `waves/B10/SP-3-audit-deep.md`
**Prior review:** `docs/superpowers/codex-sp3-plan-a-review-r1.md` (unified Plan A — NO-GO)
**Spec:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
**Model reasoning effort:** medium
**Tokens used:** 464,593

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | EventEnvelope construction uses correct fields | PASS | Lines 61-82, 312-320 | Uses `event_type`, `tenant_id=uuid.UUID(...)`, `correlation_id`, `source_module`; explicitly bans `type`/`emitted_at`. | Keep. |
| 2 | Outbox same-DB-transaction guarantee is only a helper, not proven in a domain flow | CONCERN | Lines 250-255, 301-336 | `OutboxService.write()` flushes without commit, which is correct, but Plan A2 has no integration test showing a real domain mutation and outbox row commit/rollback atomically. | Add a domain-service integration test: update a hold/graph-run row, call `OutboxService.write()` in the same session, rollback and assert neither persists; commit and assert both persist. |
| 3 | Dispatcher is not idempotent or transient-retry safe enough | BLOCK | Lines 620-631, 653-664 | Poll query has no claim/lock semantics such as `FOR UPDATE SKIP LOCKED` or status transition to `publishing`; two dispatchers can publish the same pending row. Failure path retries, but duplicate concurrent publish is still possible. | Lock rows transactionally or atomically claim them before publish. Add concurrent dispatcher test proving one publish per outbox row. |
| 4 | Scheduler uses `asyncio.create_task` + `croniter`, not APScheduler | PASS WITH TEST GAP | Lines 1084-1099, 1158, 1173 | Implementation uses `croniter` and `asyncio.create_task`. The no-APScheduler test is weak: `assert spec is None or True` is a no-op at line 988. | Replace with a real source/import assertion only; remove the no-op. |
| 5 | DLQ real repo replacement is planned, but app wiring is under-specified around async engine | CONCERN | Lines 1531-1575; current `main.py:46-58` | Plan correctly replaces `_EmptyDLQRepository`, but says `async_engine = ...` and "create_async_engine wrapping existing sync URL" without a concrete repo-verified factory. Current `_shim/db.py` exposes sync engine/session only. | Make the async engine construction explicit and tested through `create_app()` without ellipses or invented names. |
| 6 | Redis idempotency key format is correct, but Redis/Postgres idempotency is not actually wired | BLOCK | Lines 19, 777-809, 894-922; current `events/__init__.py:22,29` | Plan scope says Redis idempotency wiring, but implementation only adds `build_reclaimrx_idempotency_key()`. Existing `events/__init__.py` still uses `InMemoryIdempotencyStore`; no `PostgresIdempotencyStore`, no Redis store, no consumer wiring change. | Add the real store wiring in `events/__init__.py` or correct the plan scope. Integration test `wire_consumers()` through `create_app()` must prove durable tenant-prefixed idempotency is used. |
| 7 | `processed_events` cleanup is scheduled | PASS | Lines 1529, 1546-1548, 1560 | Registers `run_cleanup(async_engine, retention_days=7)` as `cleanup_processed_events` at `0 1 * * *`. | Keep, but depends on fixing concrete async engine. |
| 8 | Daily audit prev-hash chain verification mostly covers chain, but ordering is not robust | CONCERN | Lines 1188-1192, 1226-1278 | It walks per tenant and checks `prev_entry_hash` against prior `entry_hash`. Ordering only by `tenant_id, changed_at`; equal timestamps can make verification nondeterministic. | Order by `tenant_id, changed_at, id` or sequence/version. Add 3-entry and same-timestamp tests. |
| 9 | DLQ depth monitor threshold is wrong | BLOCK | Lines 1309-1313, 1347-1362 | Requirement is alert when DLQ depth `> 0 for > 15 minutes`; plan logs CRITICAL immediately whenever count > 0. No duration tracking, first-seen timestamp, or threshold test. | Track persistence duration, or query oldest queued `first_failed_at/last_failed_at`; alert only when oldest queued age exceeds 15 minutes. Test both under/over threshold. |
| 10 | Advisory lock formula is correct but not actually tested or implemented in Plan A2 | CONCERN | Lines 88-97, 1316-1319, 1642 | Formula is correct. But Plan says "includes it in scheduler-level advisory lock tests"; no such test exists, only a docstring reminder in `dlq_monitor.py`. | Add an explicit deterministic hash helper/test now, or move the claim entirely to Plan A3. |
| 11 | D14 integration test coverage is present but one test is broken and bindings are not all verified deeply | BLOCK | Lines 1401-1495 | Rate-limit test uses `type(m.cls)`; for a class this yields `type`, so `RateLimitMiddleware in middleware_types` will fail. Tests check scheduler job names, but not dispatcher task lifecycle or DLQ router behavior through route calls. | Fix middleware assertion to `[m.cls for m in app.user_middleware]`. Add route-level DLQ test and lifespan teardown assertions. |
| 12 | TDD is substantially better; Float/money and tenant-scoping are not fully addressed | CONCERN | Lines 3, 348-353, 1604-1621; `rg` shows no `Float(` | TDD steps are explicit. No `Float` introduced. Tenant scoping appears in DLQ `list()`, but `get(entry_id)` is unscoped and D14 DLQ replay/drop could enumerate cross-tenant entries depending on shared router behavior. | Make DLQ `get` tenant-scoped or enforce tenant in service/router dependency. Add cross-tenant DLQ get/replay/drop tests. |

---

## Verdict

**NO-GO**

Plan A2 fixes the obvious EventEnvelope and scheduler-direction mistakes from R1, but it still has execution-level blockers:

- **BLOCK 3** — Dispatcher concurrency can duplicate publishes (no `FOR UPDATE SKIP LOCKED` or atomic claim step).
- **BLOCK 6** — Idempotency "wiring" is only a key helper; `events/__init__.py` still uses `InMemoryIdempotencyStore` — the real store is never substituted.
- **BLOCK 9** — DLQ alert fires on first count > 0 instead of the required `> 0 for > 15 minutes`; duration tracking is absent.
- **BLOCK 11** — `create_app()` integration test as written contains a failing middleware type assertion (`type(m.cls)` yields `type`, not the class itself).

Concerns 2, 5, 8, 10, 12 are non-blocking but must be addressed before execution.

---

## Required fixes before GO

1. Add `FOR UPDATE SKIP LOCKED` (or status transition to `publishing`) in dispatcher poll query + concurrent dispatcher test.
2. Wire `PostgresIdempotencyStore` (or Redis equivalent) in `events/__init__.py`; integration test through `create_app()` must confirm durable store is active.
3. DLQ monitor: query `min(last_failed_at)` or equivalent; alert only when oldest unresolved entry age exceeds 15 minutes. Add sub/over-threshold tests.
4. Fix `middleware_types` assertion: `[m.cls for m in app.user_middleware]`, not `[type(m.cls) ...]`.
5. (Concern 2) Add domain atomicity integration test for outbox write within domain transaction.
6. (Concern 5) Resolve async engine construction concretely — no ellipses or assumed factory.
7. (Concern 8) Order audit chain walk by `(tenant_id, changed_at, id)`; add same-timestamp test.
8. (Concern 10) Add advisory lock hash determinism test now; do not defer to a docstring.
9. (Concern 12) Tenant-scope DLQ `get` and replay/drop; add cross-tenant isolation test.
