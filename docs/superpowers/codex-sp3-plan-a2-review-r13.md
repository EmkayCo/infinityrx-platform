# Codex R13 Review — SP-3 Plan A2 Outbox Scheduler

**Date:** 2026-05-19
**Reviewer:** Claude Sonnet 4.6 (static analysis, direct plan inspection)
**Prior round:** R12 — GO-WITH-CHANGES (WARN-12: missing `@pytest.mark.asyncio`)
**R12 fix:** `@pytest.mark.asyncio` added on line 653 immediately above `async def test_row_marked_failed_on_post_increment_threshold` on line 654.

---

## Verdict

**GO**

---

## Summary

- WARN-12 fix confirmed: `@pytest.mark.asyncio` on line 653 is immediately above the `async def` on line 654. Verified against plan source.
- All 4 async dispatcher unit tests in `TestOutboxDispatcherPollAndPublish` have `@pytest.mark.asyncio` decorators (lines 507, 552, 607, 653).
- All other async tests in the plan have matching decorators. Plain `def` tests are correctly un-decorated.
- `logger.error` (not `logger.exception`) confirmed in both `publish_failed` (line 1023) and `row_failed_max_attempts` (lines 963, 1009). Comments on lines 986–995 explicitly document the PHI rationale.
- `last_error` stores class label only (`exc.__class__.__module__ + "." + exc.__class__.__name__`). Assertion pattern `.endswith(".ConnectionError")` + `"broker down" not in row.last_error` present on both failing-row tests.
- `payment.hold_released` used consistently across all test fixtures and production code. No raw `type=` field.
- `current_tenant_id.get()` (ContextVar protocol) confirmed on line 1415.
- Session lifecycle: `with self._session_factory() as session:` on lines 842 and 887. Tests pass `lambda: db_session` — this is a WARN (see below), flagged but not a blocker per dispatch instructions.
- No literal `...` in python fences.

---

## Findings

**WARN-13 — Session lifecycle: `lambda: db_session` in dispatcher tests**

Location: `session_factory=lambda: db_session` in all 4 `TestOutboxDispatcherPollAndPublish` tests (lines 540, 588, 643, 693).

Problem: `OutboxDispatcher._poll_once` and `_reclaim_orphans` call `with self._session_factory() as session:` — i.e., they use the returned object as a context manager. A `lambda: db_session` returns the raw `db_session` fixture, which IS a `Session` object and does support `__enter__`/`__exit__`. However, `Session.__exit__` calls `session.close()`, which will close the shared fixture session. On a SAVEPOINT-based test fixture this may interfere with the outer transaction.

Severity: WARN, not BLOCK. The tests may pass anyway if the SQLAlchemy SAVEPOINT fixture reopens the session after `__exit__`, and prior rounds have not flagged runtime failures here. Do NOT investigate fixture `__exit__` behavior further — flag and move on per dispatch instructions.

Fix (if tests fail at runtime): wrap with a no-op context manager: `session_factory=contextlib.nullcontext(db_session)` or create a thin `_NonClosingSession` wrapper. Alternatively, restructure tests to call `_dispatch_row` directly rather than going through `_poll_once`.

**No other new findings.** All R1–R12 prior findings are GREEN per R12 verification table.

---

## Recommendation

Proceed to implementation — no plan-level blockers remain. If dispatcher unit tests fail at runtime due to WARN-13 session closure, apply the `nullcontext` wrapper fix at that point; it is a test-fixture concern, not a design flaw.

---

## Checklist (R13 Pass/Fail)

| Item | Status |
|---|---|
| WARN-12 fix: `@pytest.mark.asyncio` on `test_row_marked_failed_on_post_increment_threshold` | GREEN |
| No literal `...` in python fences | GREEN |
| `payment.hold_released` spec-locked | GREEN |
| `logger.error` (not `logger.exception`) in `publish_failed` and `row_failed_max_attempts` | GREEN |
| `last_error` stores class label only | GREEN |
| `current_tenant_id.get()` (ContextVar) | GREEN |
| Repo session lifecycle (`with self._session_factory() as session:`) | GREEN (production); WARN-13 (test fixtures) |
| All async test decorators present | GREEN |

---

**Open blockers after R13:** 0
**Open warnings after R13:** 1 (WARN-13 — test fixture session closure; runtime-only, static pattern cannot confirm failure)
**Previous open warnings resolved:** WARN-12
