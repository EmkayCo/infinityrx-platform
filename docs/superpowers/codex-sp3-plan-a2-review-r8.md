# Codex Adversarial Review R8 -- SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Reviewed:** 2026-05-19
**Model:** codex-cli 0.130.0 (via codex exec)
**Tokens used:** 38,139
**Prior round:** R7 was NO-GO (4 BLOCKs + 1 WARN). R8 validates fixes and scans for regressions.

---

## Verdict
**NO-GO**

---

## Summary

- BLOCK-21: PASSED mechanically, but WARN: logger name changed from R7 expected `reclaimrx.dlq_repository` to `reclaimrx.events.dlq_repository` -- flag for clarification.
- BLOCK-22: PASSED. Audit chain tests are sync, no `@pytest.mark.asyncio`, no `await`; `verify_audit_hash_chain` is `def`.
- BLOCK-23: PASSED. `_get_dlq_service()` imports and calls `get_async_engine_for_idempotency()` inside the function.
- BLOCK-24: PASSED. Test uses AST import-node inspection and `alias.name`, not source substring scanning.
- WARN-5: PASSED in Task 4 implementation, but regressed in Known constraints prose (still references outer-loop logger.exception which R7 proved never fires).
- Regression scan: most prior round fixes remain intact, but 3 new blockers found below.

---

## Findings

**BLOCK-25** -- Task 8a, `ReclaimRxScheduler.start()` + Task 7 `test_stop_prevents_further_ticks` -- **Scheduler busy-loop can starve event loop**

With `tick_interval_seconds=0`, `start()` loops without any `await asyncio.sleep(...)` when the condition `self._tick_interval > 0` is False. `_tick()` performs no awaitable work unless a job fires, so the scheduler task can monopolize the event loop. The test does `task = asyncio.create_task(sched.start()); await asyncio.sleep(0); await sched.stop()`, but `stop()` may never execute because `start()` busy-loops without yielding.

**Fix required:** Always yield once per loop regardless of tick interval value:
```python
await asyncio.sleep(self._tick_interval if self._tick_interval > 0 else 0)
```
Remove the conditional guard so sleep(0) still yields the event loop when tick_interval is 0.

---

**BLOCK-26** -- Task 6a, `ReclaimRxDLQRepository.save()` -- **Double transaction-management with AsyncSession inside engine.begin()**

`async with self._engine.begin() as conn:` already owns transaction commit/rollback. Creating `AsyncSession(bind=conn)` and calling `await async_session.commit()` inside that context is a transaction-management footgun -- it can close/commit the transaction before the context manager completes. The same `AsyncSession(bind=conn)` anti-pattern appears in the `list()` and `get()` read methods without the session being properly closed.

**Fix required:** Use `async with AsyncSession(self._engine) as session: ... await session.commit()` for ORM writes. Do not mix `engine.begin()` transaction ownership with `AsyncSession.commit()`. For reads in `list()` and `get()`, either use `async with AsyncSession(self._engine) as session:` or use `conn.execute(select(...))` directly inside `engine.connect()`.

---

**BLOCK-27** -- Task 6d, `test_idempotency_store_is_postgres_not_in_memory` -- **Integration test triggers real async engine in non-DB test environment**

The test calls `create_app()` then `get_idempotency_store()`, which lazily calls `get_async_engine_for_idempotency()`. In sqlite-backed tests this requires `aiosqlite`; in non-configured environments it may fail or create an engine pointing at production. The plan says tests "typically stub PostgresIdempotencyStore," but this test stubs nothing and has no guard.

**Fix required:** Monkeypatch `get_async_engine_for_idempotency()` to return a test engine, OR add a pytest fixture that ensures a test DB URL is configured before `create_app()` is called. The test must prove wiring (PostgresIdempotencyStore is instantiated), not ambient DB availability.

---

**BLOCK-28** -- Known constraints, "No PHI in logs" bullet -- **Contradicts R7 WARN-5 fix**

The final Known constraints section still says: "Stack traces remain available via `logger.exception()` at OutboxDispatcher outer-loop level." R7 WARN-5 explicitly proved this is false -- publish exceptions are swallowed inside `_dispatch_row`; the outer loop never sees them. Task 4 code and comment are correct, but this constraint prose is wrong and will cause a future executor to undo the fix.

**Fix required:** Replace with: "Stack traces for publish failures are logged inside `_dispatch_row` via `logger.exception()`, while `last_error` stores only the exception class label."

---

**WARN-6** -- Task 6a, `dlq_repository.py`, module-level logger -- **Logger name inconsistency between R7 note and plan fix**

R7 BLOCK-21 fix note said the logger should be `reclaimrx.dlq_repository`. The plan defines `logging.getLogger("reclaimrx.events.dlq_repository")`. This is inconsistent -- not necessarily wrong, but needs a deliberate decision so future readers know which is canonical.

**Fix required:** Either change to `reclaimrx.dlq_repository` to match the R7 note, or annotate the definition with a comment explaining that `reclaimrx.events.dlq_repository` is the canonical name (preferred -- matches module path).

---

## Recommendation

Fix BLOCK-25 through BLOCK-28 before execution.

- BLOCK-26 (AsyncSession/engine.begin mixing) is the highest blast radius -- it silently corrupts DLQ transactions at runtime and is invisible in tests.
- BLOCK-25 (scheduler busy loop) will cause the test_stop_prevents_further_ticks test to hang and may starve the event loop in production.
- BLOCK-28 (constraints prose) is a maintenance trap that will cause an executor to revert a correct fix.
- BLOCK-27 (integration test ambient DB) will fail in CI with no actionable error.

Request R9 focused on BLOCK-25 through BLOCK-28 only.
