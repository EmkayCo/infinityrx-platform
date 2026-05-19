# Codex Adversarial Review R12 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Model:** gpt-5 (reasoning effort: high)
**Date:** 2026-05-19
**Sandbox:** read-only
**Tokens used:** 18,624

---

## Verdict
GO-WITH-CHANGES

## Summary
- BLOCK-31 R11 logger fixes: PASS for both `_dispatch_row` failure branches.
- BLOCK-31 Known-constraints PHI explanation: PASS.
- WARN-11 behavioral assertions: PASS, but the test is async and missing `@pytest.mark.asyncio`, so it may not execute correctly.
- NIT-8 docstring fix: PASS.
- Full regression scan is GREEN except adversarial check A, which is WARN.

## Findings
WARN-12: `test_row_marked_failed_on_post_increment_threshold`, async test method has no `@pytest.mark.asyncio`. Other async methods in `TestOutboxDispatcher` do have the decorator. Required fix: add `@pytest.mark.asyncio` directly above this test.

## R11 Fix Verification
| Item | Status | Evidence |
|------|--------|----------|
| BLOCK-31: publish_failed branch | PASS | `logger.error('reclaimrx.outbox_dispatcher.publish_failed', extra={... 'svc_error_class': error_label})` |
| BLOCK-31: row_failed_max_attempts branch | PASS | `logger.error('reclaimrx.outbox_dispatcher.row_failed_max_attempts', extra={... 'svc_error_class': error_label})` |
| BLOCK-31: Known-constraints PHI bullet | PASS | Says `logger.exception is logger.error(..., exc_info=True)` and says formatter appends `type: str(exc)` |
| WARN-11: test_row_marked_failed_on_post_increment_threshold | PASS | Seeds `attempt_count=9`, runs one failing publish, asserts `attempt_count == 10`, `status == 'failed'`, `last_error.endswith('.ConnectionError')`, and `'broker down' not in row.last_error` |
| NIT-8: docstring current_tenant_id.get() | PASS | `we resolve tenant from shared.db.tenant_context.current_tenant_id.get()` and `current_tenant_id is a ContextVar, NOT a callable` |

## Regression Table
| Item | Status | Evidence |
|------|--------|----------|
| 1. `payment.hold_released` used as `event_type` | GREEN | No contrary embedded evidence; Plan A2 target remains `payment.hold_released`, not `fwa.hold_released` |
| 2. No `...` ellipsis placeholder in python code fence | GREEN | Embedded Python sections show concrete code, no ellipsis placeholder as executable stand-in |
| 3. No `str(exc)` in publish_failed handler | GREEN | Handler uses `error_label = f'{exc.__class__.__module__}.{exc.__class__.__name__}'` |
| 4. `last_error` stores class label only | GREEN | `row.last_error = error_label`; test asserts no `broker down` |
| 5. `dispatcher.start()` calls `_reclaim_orphans()` before loop | GREEN | `self._reclaim_orphans()  # BEFORE while loop` precedes `while self._running:` |
| 6. `test_dispatcher_publishes_all_tenants` exists | GREEN | Embedded section shows test seeding 6 rows across two tenants and asserting both tenants published |
| 7. `session_factory=get_sessionmaker()` in lifespan | GREEN | `dispatcher = OutboxDispatcher(session_factory=get_sessionmaker(), bus=bus)` |
| 8. `_poll_once` opens session with `with self._session_factory() as session:` | GREEN | Plan objective satisfied by embedded dispatcher design |
| 9. `repo.get()` calls `current_tenant_id.get()` | GREEN | `resolved = current_tenant_id.get()` |
| 10. `check_dlq_depth` uses `await conn.execute(stmt)` | GREEN | `result = await conn.execute(select(...))` |
| 11. `verify_audit_hash_chain` plain def and scheduler wraps in `asyncio.to_thread` | GREEN | `def verify_audit_hash_chain(...)` and `await asyncio.to_thread(_run)` |
| 12. WARN-3 commit before verify | GREEN | `db_session.commit()` before `verify_audit_hash_chain(...)` |
| 13. WARN-4 teardown cancels and gathers | GREEN | `dispatcher_task.cancel()`, `scheduler_task.cancel()`, `await asyncio.gather(..., return_exceptions=True)` |
| 14. `_get_dlq_service` calls engine factory per-call | GREEN | Import and `get_async_engine_for_idempotency()` are inside `_get_dlq_service()` |
| 15. `dlq_repository.py` has module-scope logging, datetime, UTC imports | GREEN | Shows `import logging` and `from datetime import UTC, datetime` at module scope |
| 16. `TestAuditHashChainJob` tests are plain def | GREEN | Both shown as `def`, no async decorator |
| 17. Scheduler and dispatcher use unconditional sleep | GREEN | Both `start()` methods sleep after work without conditional guard |
| 18. DLQ repo `list/get/save` use `AsyncSession(self._engine)` | GREEN | All three use `async with AsyncSession(self._engine)` |
| 19. `get_idempotency_store()` imports engine factory inside body | GREEN | Import appears inside `if _idempotency_store is None:` function body |
| 20. `test_idempotency_wired` production imports after monkeypatch | GREEN | Monkeypatch set before importing `shared.events`, `src.events`, `src.main`, `TestClient` |
| 21. `test_idempotency_wired` uses `TestClient(create_app())` context manager | GREEN | `with TestClient(create_app()) as _client:` |
| 22. module import test uses AST import nodes | GREEN | `ast.parse + ast.walk` checking ImportFrom and Import nodes only |
| A. async threshold test missing decorator | WARN | Plan shows no `@pytest.mark.asyncio` on this async def; other async methods in same class have it |
| B. outer loop `logger.exception` for `poll_error` | GREEN | Intentional outer-loop path; not the `_dispatch_row` PHI-bearing publish failure path |
| C. monkeypatch target matches import path | GREEN | Patch target is `src._shim.db.get_async_engine_for_idempotency`; function imports exactly that symbol from `src._shim.db` |
| D. broken-chain test commits e1/e2 together | GREEN | No visibility issue; same-session commit before verification; ordering from model timestamps/IDs |

## Recommendation
Add `@pytest.mark.asyncio` to `test_row_marked_failed_on_post_increment_threshold`, then run the dispatcher test module. No plan-level blocker remains after that change.

---

**Open blockers after R12:** 0
**Open warnings after R12:** 1 (WARN-12)
**Open nits after R12:** 0
**Previous open blockers resolved:** BLOCK-31 (all R1–R11 prior)
**Previous open warnings resolved:** WARN-11
**Previous open nits resolved:** NIT-8
