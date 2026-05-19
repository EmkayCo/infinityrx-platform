# Codex Adversarial Review R10 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Session ID:** 019e407c-1c03-7041-962d-823ae05d7606
**Model:** gpt-5.5 (reasoning effort: high)
**Date:** 2026-05-19
**Sandbox:** read-only

---

## Verdict
NO-GO

## Summary
- R9 BLOCK-27 fix is present: `get_async_engine_for_idempotency` is imported inside `get_idempotency_store()`, and the test patches before importing `src.events` plus resets the singleton.
- R9 BLOCK-29 is effectively resolved: literal `...` exists only in prose outside Python fences.
- Most R6-R8 regression items are present: `payment.hold_released`, no `str(exc)` in `publish_failed`, class-label `last_error`, startup orphan reclaim, cross-tenant dispatcher test, `get_sessionmaker()`, per-poll session scope, async DLQ sessions, `await conn.execute(stmt)`, sync audit job via `to_thread`, cancel+gather teardown, AST import check, and unconditional scheduler/dispatcher sleeps.
- One blocker remains in DLQ tenant fallback: the plan calls a `ContextVar` like a function.

## Findings

**BLOCK-30:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` line 1327 — DLQ `get()` fallback imports `shared.db.tenant_context.current_tenant_id` and calls `current_tenant_id()`, but `shared/db/tenant_context.py` line 45 defines it as a `ContextVar`, not a function. Runtime path raises `TypeError: 'ContextVar' object is not callable`, breaking shared `DLQService.replay/drop` when they call `repo.get(entry_id)` without tenant_id.
- **Fix:** Use `from src._shim.db import current_tenant_id` and call that wrapper, or import the contextvar as `_current_tenant_id` and call `_current_tenant_id.get()`.

**WARN-6:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` line 940 — a row at `attempt_count == 9` that fails is incremented to `10` but left `pending`; it is only marked `failed` on the next poll. This contradicts the plan text that after `_MAX_ATTEMPTS` failures the row is moved to `failed`.
- **Fix:** After incrementing, set `row.status = "failed"` when `row.attempt_count >= _MAX_ATTEMPTS`, else return it to `pending`; add a test for `attempt_count=9` plus one failing publish.

**NIT-7:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` line 1612 — comment says `create_app()` forces `wire_consumers`, but current app wiring runs consumers in lifespan, not factory construction. The assertion still validates `get_idempotency_store()`, but the comment overclaims.
- **Fix:** Correct the comment or enter lifespan in the test.

## R9 Fixes Confirmed
- BLOCK-27: RESOLVED — `get_async_engine_for_idempotency` imported inside function body; test singleton reset present; test imports after monkeypatch.
- BLOCK-29: RESOLVED — no literal `...` ellipsis inside Python fences.

## Regression Items Status
| Item | Status |
|---|---|
| payment.hold_released (no fwa.hold_released) | PASS |
| No str(exc) in publish_failed (R4 NEW-2) | PASS |
| last_error stores class label only (R5 BLOCK-12) | PASS |
| start() calls _reclaim_orphans before loop (R6 BLOCK-13) | PASS |
| Cross-tenant test test_dispatcher_publishes_all_tenants (R6 BLOCK-14) | PASS |
| session_factory=get_sessionmaker() (R6 BLOCK-15) | PASS |
| _poll_once uses `with self._session_factory() as session:` (R6 BLOCK-16) | PASS |
| DLQ repo .get() tenant fallback (R6 BLOCK-17) | **BLOCK-30 — FAIL** |
| check_dlq_depth uses `await conn.execute(stmt)` (R6 BLOCK-19) | PASS |
| verify_audit_hash_chain plain def + asyncio.to_thread (R6 WARN-2) | PASS |
| Rollback test commits seed first (WARN-3) | PASS |
| Teardown cancel + gather (WARN-4) | PASS |
| dlq_repository.py logging+datetime+UTC imports (R7 BLOCK-21) | PASS |
| TestAuditHashChainJob sync def (R7 BLOCK-22) | PASS |
| _get_dlq_service per-call engine factory (R7 BLOCK-23) | PASS |
| AST-based import check (R7 BLOCK-24) | PASS |
| logger.exception() at _dispatch_row catch (R7 WARN-5) | PASS |
| Unconditional asyncio.sleep in scheduler+dispatcher (R8 BLOCK-25) | PASS |
| DLQ repo list/get/save use AsyncSession(self._engine) (R8 BLOCK-26) | PASS |
| Known-constraints PHI bullet (R8 BLOCK-28) | PASS |

## Recommendation
Fix BLOCK-30 before execution (change `current_tenant_id()` → `current_tenant_id.get()` in the DLQ repo tenant fallback), then add the `attempt_count=9` terminal-failure test (WARN-6) while touching dispatcher tests. After those two fixes, this plan can move to GO-WITH-CHANGES or GO.

---

**Open blockers after R10:** 1 (BLOCK-30)
**Open warnings after R10:** 1 (WARN-6)
**Open nits after R10:** 1 (NIT-7)
**Previous open blockers resolved:** BLOCK-27, BLOCK-29 (+ all R1–R8 prior)
