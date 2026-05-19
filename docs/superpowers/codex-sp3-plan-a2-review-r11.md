# Codex Adversarial Review R11 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Model:** gpt-5.5 (reasoning effort: high)
**Date:** 2026-05-19
**Sandbox:** read-only
**Tokens used:** 200,037

---

## Verdict
NO-GO

## Summary
- R10 BLOCK-30 is fixed in code: `current_tenant_id.get()` is used and the comment names `shared/db/tenant_context.py:45`.
- R10 NIT-7 is fixed: `TestClient(create_app())` is used as a context manager and hits `/health`.
- R10 WARN-6 implementation is fixed, but the required post-increment test is still missing (existing test seeds `attempt_count=10`, not `attempt_count=9`).
- Regression item "no `str(exc)` in publish_failed log" is not green: `logger.exception(...)` still emits the exception message via traceback formatting.

## Findings

**BLOCK-31:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` lines 952, 966, 2607
`logger.exception(...)` logs the exception value, including `str(exc)`, at the end of the traceback. The plan claims stack traces only contain code locations and filenames — this is false for Python logging. If publish exceptions can contain PHI (e.g. from the envelope payload embedded in the exception message), this is a PHI log leak.
- **Fix:** Do not use `logger.exception` for publish failures unless the exception message is guaranteed sanitized. Use `logger.error(..., extra={"svc_error_class": error_label})` with no `exc_info`, or implement sanitized traceback logging that omits the exception value and locals.

**WARN-11:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` lines 608–649, 940–949
The WARN-6 code path is implemented (post-increment `if row.attempt_count >= _MAX_ATTEMPTS`), but the test seeds `attempt_count=10` — it only exercises the pre-check guard at dispatch-row entry, not the post-increment path. No test for `attempt_count=9` + one publish failure → `status='failed'` after increment.
- **Fix:** Add a test that seeds `attempt_count=9`, makes `bus.publish` raise, calls `_poll_once()`, then asserts `attempt_count == 10`, `status == 'failed'`, and class-only `last_error`.

**NIT-8:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md` line 1335
The docstring prose still says `current_tenant_id()` (the old calling convention) even though the code correctly uses `.get()`. Risks re-introducing the exact mistake the R10 BLOCK-30 fix resolved.
- **Fix:** Change prose to `current_tenant_id.get()`.

## R10 Fixes Confirmed
- BLOCK-30: RESOLVED — code uses `current_tenant_id.get()` at line ~1354; comment cross-references `shared/db/tenant_context.py:45`.
- WARN-6 (code): RESOLVED — post-increment threshold check present at lines 940–961.
- WARN-6 (test): NOT RESOLVED — see WARN-11 above.
- NIT-7: RESOLVED — `TestClient(create_app()) as _client: _client.get("/health")` present; comment accurately states `create_app()` alone does not trigger lifespan.

## Regression Status

| Item | Status | Evidence |
|---|---|---|
| `payment.hold_released` (not `fwa.hold_released`) | PASS | Many hits; no `fwa.hold_released` in plan |
| No `str(exc)` in publish_failed log | **FAIL** | `logger.exception` at lines 952, 966 emits exception message via traceback |
| `last_error` stores class label only | PASS | `error_label = module.ClassName`, `row.last_error = error_label` at lines 938–941 |
| `_reclaim_orphans` called before loop in `start()` | PASS | `self._reclaim_orphans()` before while loop |
| Cross-tenant test `test_dispatcher_publishes_all_tenants` | PASS | Present at line 1060 |
| `session_factory=get_sessionmaker()` | PASS | Lines 731, 2473 |
| `_poll_once` uses `with self._session_factory() as session:` | PASS | Line 832 |
| DLQ list/get/save use `AsyncSession(self._engine)` | PASS | Lines 1312, 1366, 1426 |
| `check_dlq_depth` uses `await conn.execute(stmt)` | PASS | Line 2169 |
| `verify_audit_hash_chain` plain `def` + `asyncio.to_thread` | PASS | `def` at line 1993; `to_thread` at line 2500 |
| `start()` teardown: cancel + gather | PASS | Present |
| AST-based import check (no `InMemoryIdempotencyStore` at module load) | PASS | Present |
| Unconditional `asyncio.sleep` in scheduler + dispatcher | PASS | Present |
| Known-constraints PHI bullet | PASS | Present |

## Recommendation
Fix BLOCK-31 first (switch `logger.exception` at publish-fail branches to `logger.error(..., exc_info=False)` to prevent exception message from reaching the log), then add the missing `attempt_count=9` terminal-failure test (WARN-11). Fix NIT-8 (prose `current_tenant_id()` → `current_tenant_id.get()`) in the same pass. The pre-check guard at dispatch-row entry is intentional and reachable — it handles legacy rows, manually repaired rows, and orphan-reclaimed rows already at `_MAX_ATTEMPTS`; do not remove it.

---

**Open blockers after R11:** 1 (BLOCK-31)
**Open warnings after R11:** 1 (WARN-11)
**Open nits after R11:** 1 (NIT-8)
**Previous open blockers resolved:** BLOCK-30 (+ all R1–R9 prior)
**Previous open warnings resolved:** WARN-6 (code path) — test gap remains as WARN-11
**Previous open nits resolved:** NIT-7
