# Codex Adversarial Review R7 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Reviewed:** 2026-05-19
**Model:** gpt-5.5 (via codex exec)
**Tokens used:** 37,117
**Prior round:** R6 was NO-GO (8 BLOCKs + 4 WARNs). All 12 verified below.

---

## Verdict
**NO-GO**

---

## Summary

- BLOCK-13: PASSED. `start()` calls `_reclaim_orphans()` before the loop; reclaim SQL sets `publishing -> pending` and increments `attempt_count`; solo-deployment model is documented.
- BLOCK-14: PASSED. Dispatcher docstring states system-wide/all-tenant behavior, and `test_dispatcher_publishes_all_tenants` seeds 6 rows across 2 tenants and asserts all 6 publish.
- BLOCK-15: PASSED. Lifespan wiring uses `session_factory=get_sessionmaker()`.
- BLOCK-16: PASSED. `_poll_once()` owns the session via `with self._session_factory() as session:`.
- BLOCK-17: PASSED WITH REGRESSION. `get(entry_id, *, tenant_id=None)` is optional and falls back to `current_tenant_id()`, but the proposed file has missing imports that will crash runtime paths.
- BLOCK-18: PASSED. Concurrent claim test import and constructor kwarg are corrected.
- BLOCK-19: PASSED. `check_dlq_depth` uses `await conn.execute(...)` directly and the stub only mocks `conn.execute -> result.one()`.
- BLOCK-20: PASSED. Spec references now describe fixed retry on next poll and defer per-row backoff.
- WARN-2: PASSED. `verify_audit_hash_chain` is sync `def`; scheduler wrapper uses `asyncio.to_thread(...)`.
- WARN-3: PASSED. Atomicity rollback test commits seed first, mutates, rolls back, and asserts hold reverted plus no outbox row.
- WARN-4: PASSED. Lifespan teardown cancels both tasks and gathers with `return_exceptions=True`.

Regression scan: PASSED. `payment.hold_released` remains; no `fwa.hold_released`; no literal `...` in Python fences; no `str(exc)` in `publish_failed`; `last_error` stores only the exception class label.

---

## Findings

**BLOCK-21** — Task 6a, `modules/reclaimrx/src/events/dlq_repository.py` — **Missing imports crash runtime**

`logger.warning(...)` is used in `get()`, but `logger` is never imported or defined. `datetime.now(UTC)` is used in `replay()`, but `datetime` and `UTC` are never imported.

**Fix required:** Add `import logging`, `from datetime import UTC, datetime`, and `logger = logging.getLogger("reclaimrx.dlq_repository")`.

---

**BLOCK-22** — Task 7 tests (TestAuditHashChainJob), `test_reclaimrx_scheduler.py` — **Tests `await` a sync function**

Task 7 tests call `await verify_audit_hash_chain(...)`, but Task 8 changes `verify_audit_hash_chain` to plain `def`. This makes the plan internally inconsistent and the tests will fail with `TypeError: object dict can't be used in 'await' expression`.

**Fix required:** Remove `await` from both audit-chain unit tests (`test_clean_chain_returns_ok` and `test_broken_chain_returns_alert`).

---

**BLOCK-23** — Task 9b, `main.py` lifespan `_get_dlq_service()` — **`async_engine` scoping error**

The lifespan code defines `async_engine` as a local variable inside the lifespan generator. `_get_dlq_service()` is defined as a module-level or inner function that references `async_engine`, but it will not see the local lifespan variable. This will raise `NameError` at the first DLQ router call.

**Fix required:** Resolve the async engine inside `_get_dlq_service()` by calling `get_async_engine_for_idempotency()` directly, or define a module-level `_async_engine` variable that the lifespan initializes.

---

**BLOCK-24** — Task 6d, `test_idempotency_wired.py:test_module_source_does_not_import_inmemory_store` — **Overly broad string assertion**

The test forbids the string `"InMemoryIdempotencyStore"` anywhere in `events/__init__.py`, including comments. The plan's surrounding instructions explicitly discuss removing that name; if an executor adds even a comment referencing the old class, the test fails spuriously.

**Fix required:** State that the implementation file must contain zero occurrences including comments, OR make the test check runtime imports/objects (`from shared.events.idempotency import InMemoryIdempotencyStore; isinstance(...)`) instead of raw full-source string matching.

---

**WARN-5** — Task 4, `outbox_dispatcher.py:_dispatch_row()` — **Comment claims stack traces are logged but they are not**

The comment says "Stack traces are captured separately by `logger.exception()` at OutboxDispatcher level." Publish exceptions are caught inside `_dispatch_row()` and not re-raised, so the outer `start()` loop's `logger.exception(...)` will never fire for publish failures. The comment is false.

**Fix required:** Either remove the stack-trace claim, or add `exc_info=True` to the `logger.warning(...)` call in `_dispatch_row` so the stack trace is captured without serializing exception args into row/log fields.

---

## Recommendation

Fix BLOCK-21 through BLOCK-24 before execution. BLOCK-21 (missing imports) and BLOCK-23 (scoping error) are the highest-blast-radius items — both will crash at first runtime use before any test can exercise the feature. BLOCK-22 will fail the entire audit-chain test class before assertions run. BLOCK-24 is a test fragility issue that will produce false failures. Request R8 focused on the patched sections only.
