# SP-3 Plan A2 -- Codex R3 Adversarial Review
**Date:** 2026-05-19
**Reviewer:** Codex CLI R3
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md
**Prior review:** docs/superpowers/codex-sp3-plan-a2-review-r2.md

## R2 Carry-Forward Verification

| ID | R2 Finding | Status | Evidence |
|----|-----------|--------|---------|
| BLOCK-5 | 6c DELETE-and-replace language | RESOLVED | Plan section 6c says: "This is a deletion-and-replacement, not an addition. The InMemoryIdempotencyStore import on the current file line 22 and its module-level instantiation on line 29 MUST be removed" (plan:1232-1234), and "DELETE these lines" above the old import/instantiation (plan:1247-1249). |
| BLOCK-6 | Dispatcher finally bare pass | RESOLVED | Plan section 4.2 shows an explicit structural return, not bare pass: the finally block is followed by comment "No-op finally is intentional and structural, not a placeholder" and return (plan:737-744). |
| BLOCK-7 | _resolve_db_url() invented API | STILL-BLOCKED | The forbidden symbol still appears in the plan: "R2 BLOCK 7 fix: the prior draft called a nonexistent _resolve_db_url()" (plan:1300). Although the implementation uses get_engine().url and branches for postgresql://, postgresql+psycopg2://, and sqlite:/// (plan:1311-1322), the checklist says _resolve_db_url() must not appear anywhere. |
| BLOCK-8 | payment.hold_released spec lock | RESOLVED | The plan uses event_type="payment.hold_released" in the EventEnvelope binding (plan:63) and throughout outbox/DLQ examples. rg found no fwa.hold_released occurrences in the plan. The locked spec also says event_type: payment.hold_released (spec:623). |
| BLOCK-9 | DLQ tenant_id scoping | STILL-BLOCKED | get() takes tenant_id and has EventDLQEntry.tenant_id == tenant_id in its WHERE (plan:1130-1151), but replay(self, entry_id, *, tenant_id) and drop(self, entry_id, *, tenant_id) only call self.get(...) and then mutate the returned object (plan:1155-1179). They do not show tenant-scoped UPDATE/WHERE clauses as required by the checklist. |
| CONCERN-10 | Scheduler stop test assertions | RESOLVED | The scheduler stop test now asserts all three concrete conditions: sched._running is False, task.done(), and task.exception() is None (plan:1426-1443). |

## New Issues Found

**[BLOCK-10]** -- drop() writes a nonexistent EventDLQEntry.dropped_at column. Evidence: plan section 5 writes entry.dropped_at = datetime.now(UTC) (plan:1176-1177), but shared/db/models/events.py defines replayed_at and then status with no dropped_at column (shared/db/models/events.py:67-72). Impact: the implementation will fail because the ORM model has no mapped dropped_at attribute.

**[BLOCK-11]** -- Production code blocks still contain ellipsis placeholders. Evidence: the OutboxService production file snippet contains payload={...} (plan:273-284), and the main.py exact diff contains async_engine = ... (plan:2131-2136). Impact: the plan is not directly implementable as written and leaves app-factory async engine binding unresolved.

**[BLOCK-12]** -- Dispatcher _poll_once() uses return in a finally block, suppressing exceptions. Evidence: _poll_once() wraps claim/dispatch in try and then unconditionally returns from finally (plan:730-744). Impact: unexpected claim/dispatch failures are swallowed, hiding failed publishes, failed commits, and cancellation/error signals.

**[BLOCK-13]** -- DLQ replay() / drop() mutate an ORM object returned from a different AsyncSession. Evidence: get() creates an AsyncSession and returns result.scalar_one_or_none() (plan:1145-1153); replay() and drop() then open a new AsyncSession, mutate the returned entry, and call async_session.add(entry) (plan:1155-1179). Impact: SQLAlchemy can reject the object as already attached to another session, or behave inconsistently because the original async session is never closed.

## Verdict
**NO-GO**

## Summary
Four of the six R2 carry-forward items are resolved, but BLOCK-7 and BLOCK-9 remain blocked under the strict checklist. New blockers also prevent implementation as written: dropped_at is not present on EventDLQEntry, app-factory async engine wiring still contains ellipses, and the dispatcher finally-return suppresses exceptions.

## Recommendation
Remove the _resolve_db_url() mention entirely, rewrite DLQ get/replay/drop as tenant-scoped statements executing within a single session, either add a real dropped_at column and migration or stop writing it, and replace all production ellipses plus the dispatcher finally-return before proceeding to R4.
