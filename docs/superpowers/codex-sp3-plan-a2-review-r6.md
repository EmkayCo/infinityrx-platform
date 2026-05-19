# Codex Adversarial Review R6 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Reviewed:** 2026-05-19
**Model:** gpt-5.5 (via codex exec)
**Tokens used:** 1,111,662
**Prior round:** R5 was GO-WITH-CHANGES (BLOCK-12 + WARN-1). Both fixes verified applied.

---

## Verdict
**NO-GO**

---

## Summary

- **R5 BLOCK-12: PASSED.** Plan lines 578–585 now assert class-label-only `last_error`; no positive `"broker down"` assertion remains.
- **R5 WARN-1: PASSED.** Plan line 2261 says `module.ClassName` only; no truncated-message or "type+message" language.
- **Regression scan: PASSED.** `payment.hold_released` preserved; no `fwa.hold_released`; dispatcher failure path avoids `str(exc)`; `...` only in prose; `repo.get()` passes `tenant_id`; Postgres claim uses `FOR UPDATE SKIP LOCKED`; `replay()`/`drop()` include tenant filters; no `dropped_at` write.
- **Fresh scan: 8 BLOCKs + 4 WARNs.** Multiple execution blockers in dispatcher recovery, app wiring, DLQ protocol compatibility, and tests.

---

## Findings

**BLOCK-13** — plan:762–787, 798–851 — **Orphaned `status='publishing'` rows on process crash**

The claim path commits `status='publishing'` before `bus.publish()`. Future polls only claim `status='pending'`. A process crash mid-publish permanently strands the row — no recovery path exists.

**Fix required:** Add a `claim_expires_at` timestamp and a stale-claim reclaim step in `_claim_postgres`/`_claim_generic`, OR keep rows in `pending` and use a distributed lock, OR document explicitly that orphaned rows are moved to `failed` by an operator job.

---

**BLOCK-14** — plan:762–787, 798–804 — **Dispatcher claim queries are all-tenant (no tenant scoping)**

The raw Postgres SQL and the generic SELECT both bypass tenant filtering. If this is intentionally a system-wide dispatcher the plan must state that and test cross-tenant behavior explicitly. If not, add `tenant_id` to `OutboxDispatcher.__init__` and filter both claim paths.

**Fix required:** Either add tenant scoping to dispatcher claims, or add an explicit architectural note stating the dispatcher is system-wide and add a cross-tenant isolation test.

---

**BLOCK-15** — plan:2150 vs `modules/reclaimrx/src/_shim/db.py` — **`get_session` is a generator dependency, not a Session factory**

App wiring passes `get_session` to `OutboxDispatcher(session_factory=get_session, ...)`. In the current repo `get_session` is a generator/dependency function, not a `Session` factory. `OutboxDispatcher._poll_once()` will receive a generator and fail at `session.bind`.

**Fix required:** Pass `lambda: get_sessionmaker()()` or a real `sessionmaker` callable. Close sessions after each poll.

---

**BLOCK-16** — plan:747–754 — **`_poll_once()` never closes sessions — connection leak**

With a real sessionmaker this leaks DB sessions/connections forever. Session is opened but `close()` is never called.

**Fix required:** Wrap session lifecycle in `with self._session_factory() as session:` or add `try/finally: session.close()`.

---

**BLOCK-17** — plan:1143–1165, 1186–1208 vs `shared/events/dlq.py:35,84,98` — **`ReclaimRxDLQRepository` breaks the shared `DLQRepository` protocol**

`ReclaimRxDLQRepository.get()` requires `tenant_id` as a mandatory keyword arg. The shared `DLQService` calls `repo.get(entry_id)` without it. The new repo does not satisfy the existing protocol — replay/drop endpoints will raise `TypeError` at runtime.

**Fix required:** Update the shared router/service to derive current tenant and call tenant-scoped repo methods, or provide an adapter shim that satisfies the protocol while internally routing to the tenant-scoped implementation.

---

**BLOCK-18** — plan:883, 929–932 — **Concurrent-claim test has wrong import path and wrong kwarg name**

Two bugs in `test_two_dispatchers_each_claim_disjoint_rows`:
1. `from src.events.outbox_service import OutboxService` — the plan defines `OutboxService` at `src.outbox.event_outbox`, not `src.events.outbox_service`.
2. `OutboxDispatcher(..., poll_interval=0.01)` — the constructor parameter is `poll_interval_seconds`, not `poll_interval`.

Both bugs cause `ImportError` and `TypeError` before any concurrency is tested.

**Fix required:** Correct the import to `from src.outbox.event_outbox import OutboxService`. Correct the kwarg to `poll_interval_seconds=0.01`.

---

**BLOCK-19** — plan:1834–1869, 1927–1978 — **`test_dlq_monitor` stubs don't patch `AsyncSession` — tests will fail**

`check_dlq_depth()` constructs `AsyncSession(bind=conn)` where `conn` is a `MagicMock`. The `_stub_engine` helper comment admits monkeypatching is required but the tests do not do it. These tests will fail with `TypeError` or `AttributeError` from SQLAlchemy internals.

**Fix required:** Either rewrite the implementation to use `await conn.execute(...)` directly (avoids `AsyncSession` entirely), or patch `AsyncSession` in the test fixture with `monkeypatch.setattr`.

---

**BLOCK-20** — plan:651–656, 846–851 — **"Exponential backoff" claimed but not implemented**

The plan and spec §7.2 claim exponential backoff on failure. The implementation immediately sets failed rows back to `pending` with no delay field (`next_attempt_at`), no backoff calculation, and no claim filter excluding rows before their retry time. Every poll retries all failed rows immediately.

**Fix required:** Add `next_attempt_at` column (or use existing if present), set exponential delay on failure, and add `AND (next_attempt_at IS NULL OR next_attempt_at <= NOW())` to claim predicates. Or remove the exponential-backoff claim from the spec references in the plan/docs.

---

**WARN-2** — plan:1699–1729 — **`verify_audit_hash_chain` is `async def` but uses sync `Session.execute()` — will block event loop**

The function is declared `async def` but calls sync `session.execute()` and `session.scalars()` directly. During a large daily all-tenant scan this will block the asyncio event loop for the full table walk duration.

**Fix required:** Make it a plain `def` and call it from `asyncio.to_thread()` in the scheduler job wrapper, or convert to an async session throughout.

---

**WARN-3** — plan:388–414 — **`test_rollback_drops_both_rows` is a weak atomicity test**

The test seeds the hold inside the transaction that is then rolled back, so the hold was never committed. `refreshed is None` is trivially true — it would pass even if `OutboxService` were removed entirely. The test does not prove atomicity.

**Fix required:** Commit the seed first, then mutate (`hold.status = "released"`) + write outbox row, then rollback, then assert hold remains `active` (not missing) and no outbox row exists.

---

**WARN-4** — plan:2153–2186 — **Lifespan teardown calls `stop()` but never awaits or cancels tasks**

`dispatcher_task` and `scheduler_task` are created but the teardown block only calls `await dispatcher.stop()` and `await scheduler.stop()` without cancelling or awaiting the tasks themselves. The scheduler can keep sleeping for up to 60 seconds before exiting. Under ASGI the process may be killed before the scheduler exits cleanly.

**Fix required:** Add `dispatcher_task.cancel(); scheduler_task.cancel()` followed by `await asyncio.gather(dispatcher_task, scheduler_task, return_exceptions=True)` in the teardown block.

---

## Recommendation

8 BLOCKs require plan patches before execution. Priority order by blast radius:

1. **BLOCK-15 + BLOCK-16** (session factory + lifecycle) — executor cannot even start the dispatcher without these.
2. **BLOCK-17** (DLQ protocol breakage) — router calls will `TypeError` at first use.
3. **BLOCK-13** (publishing orphan) — data integrity issue; stranded rows are unrecoverable without operator intervention.
4. **BLOCK-18** (wrong import + kwarg) — concurrent-claim test is dead on arrival.
5. **BLOCK-19** (DLQ monitor test stubs) — entire test class will fail before assertions.
6. **BLOCK-14** (all-tenant dispatcher) — needs a design decision (system-wide vs tenant-scoped) captured in the plan.
7. **BLOCK-20** (backoff claim vs implementation gap) — either implement it or remove the claim.
8. **WARN-2** (sync session blocking event loop) — fix before load testing.

After surgical patches on BLOCK-13 through BLOCK-20, request R7 focused on the patched sections.
