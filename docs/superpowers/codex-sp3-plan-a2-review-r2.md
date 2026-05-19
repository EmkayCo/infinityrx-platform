# Codex Adversarial Review — SP-3 Plan A2 — R2

**Date:** 2026-05-19
**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a2-outbox-scheduler.md`
**R1 verdict:** `docs/superpowers/codex-sp3-plan-a2-review-r1.md` (NO-GO — 4 BLOCKs + 5 CONCERNs)
**Reviewer:** OpenAI Codex CLI
**Note on file write:** Codex sandbox blocked the write twice; verdict body relayed from Codex stdout and written via Claude main thread.

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | R1 BLOCK 3 — dispatcher concurrency via `FOR UPDATE SKIP LOCKED` + atomic `UPDATE … RETURNING` | PASS | plan dispatcher | `_claim_postgres` issues `FOR UPDATE SKIP LOCKED` claim; `_claim_generic` flips status under SAVEPOINT; concurrent-dispatcher test asserts disjoint claims | None |
| 2 | R1 BLOCK 9 — DLQ duration threshold via `min(first_failed_at)`; status `ok / monitoring / alert` | PASS | `check_dlq_depth` | Under/over/boundary tests added; threshold = 15 minutes | None |
| 3 | R1 BLOCK 11 — middleware assertion uses `m.cls` (the class) not `type(m.cls)` | PASS | T9 test | Comment explains metaclass vs class confusion | None |
| 4 | R1 CONCERN 8 — audit chain ordering deterministic via secondary `id` tiebreak | PASS | `verify_audit_hash_chain` | `ORDER BY tenant_id, changed_at, id` | None |
| 5 | R1 BLOCK 6 — wire `PostgresIdempotencyStore` in `events/__init__.py` | BLOCK | plan §6c | Current `modules/reclaimrx/src/events/__init__.py:22,29` still imports + instantiates `InMemoryIdempotencyStore`. Plan documents the replacement but the integration test `test_idempotency_wired.py` will fail as written until the executor actually edits the file. Plan is correct but must explicitly call out that the prior `InMemoryIdempotencyStore` import is REMOVED, not merely supplemented. | Tighten plan §6c: add a "git diff -" preview that proves `InMemoryIdempotencyStore` line is deleted, not commented out. |
| 6 | New BLOCK — bare `pass` in production code snippet | BLOCK | plan:~740 | A `pass` placeholder appears in the dispatcher loop's `_poll_once` shutdown path | Replace with explicit `return` or `break` semantics |
| 7 | New BLOCK — `_resolve_db_url()` referenced by plan but not present in `_shim/db.py` | BLOCK | plan §6c | `get_async_engine_for_idempotency()` calls `_resolve_db_url()`, which does not exist in the current `_shim/db.py`. Either name the real helper (e.g. `_db_url()`) or add `_resolve_db_url()` as part of A2 scope | Pick one and make the plan internally consistent |
| 8 | New BLOCK — event type name conflict with spec lock | BLOCK | plan vs spec:56,624 | Plan uses `fwa.hold_released` after the R1 BLOCK 8 unification, but the locked spec lists `payment.hold_released` at `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md:56` and `:624`. Spec is the contract; either revise the spec (and A1/A2/A3/A5 in lock-step) or revert to `payment.hold_released` everywhere | Decide the canonical name once and propagate. `event-bus.md` dot-notation guidance (`fwa.*` prefix) suggests `fwa.hold_released` is correct, but the spec must be updated explicitly to match |
| 9 | New BLOCK — `ReclaimRxDLQRepository.get()` lacks tenant_id WHERE clause | BLOCK | plan:1126,1131 | DLQ `get(entry_id)` queries by id only; cross-tenant read enumeration possible | Add `tenant_id` predicate from current tenant context (or pass tenant_id arg); cross-tenant `get`/`replay`/`drop` test required |
| 10 | New CONCERN — `assert True` no-op in scheduler test | CONCERN | plan:1349 | `assert True` placeholder in `test_stop_prevents_further_ticks` | Replace with an explicit assertion against scheduler state (`assert sched._running is False`) |
| 11 | R1 CONCERN 2 — outbox same-transaction atomicity integration test | PASS | plan §2c | Rollback + commit both tested through a real PaymentHold mutation | None |
| 12 | R1 CONCERN 4 — APScheduler no-op assertion replaced with source-level check | PASS | plan | Real source-scan assertion in place | None |
| 13 | R1 CONCERN 5 — async engine construction concrete | PARTIAL | plan §6c | Factory documented but still has `... ellipsis` placeholder for the URL conversion path (see BLOCK 7) | Resolve alongside BLOCK 7 |

---

## Verdict

**NO-GO**

Resolved: R1 BLOCKs 3, 9, 11; CONCERNs 2, 4, 8.
Unresolved or newly introduced: BLOCKs 5, 6, 7, 8, 9 (5 new/residual).

---

## Summary of BLOCKs (5 total)

- **BLOCK 5:** §6c must show an explicit replacement (remove the old import) — current draft reads as additive.
- **BLOCK 6:** bare `pass` placeholder in dispatcher production code.
- **BLOCK 7:** `_resolve_db_url()` referenced but does not exist in `_shim/db.py`.
- **BLOCK 8:** event-name conflict between spec (`payment.hold_released`) and unified A1/A2/A3/A5 plans (`fwa.hold_released`).
- **BLOCK 9:** DLQ `get()` lacks tenant_id WHERE — cross-tenant read enumeration risk.

---

## Recommendation

Five concrete BLOCKs remain. Two are mechanical (BLOCK 6 `pass`, BLOCK 10 `assert True`). Three require coordinated decisions:

1. **BLOCK 8 (event names):** resolve in spec, then propagate. `.claude/rules/event-bus.md` recommends `fwa.*` prefix for FWA-domain events. Either update the spec at lines 56 and 624 to `fwa.hold_released` OR revert all four plans to `payment.hold_released`.
2. **BLOCK 7 (async engine factory):** name the real `_shim/db.py` helper, or add `_resolve_db_url()` as a scoped deliverable.
3. **BLOCK 9 (DLQ tenant scoping):** add `tenant_id` predicate to repository methods plus cross-tenant get/replay/drop tests.

After these fixes, BLOCK 5 should also clear naturally (plan §6c will be coherent end-to-end).

---

*Verdict body relayed from Codex stdout; sandbox blocked direct file write.*
