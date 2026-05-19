# Codex Adversarial Review R9 -- SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Reviewed:** 2026-05-19
**Model:** codex-cli 0.130.0 / gpt-5.5 (via codex exec)
**Prior round:** R8 was NO-GO (4 BLOCKs + 1 WARN). R9 validates R8 fixes and scans for regressions.

---

## Verdict
NO-GO

---

## Summary

- R8 BLOCK-25: PASS. Dispatcher and scheduler both use unconditional `await asyncio.sleep(...)` at Task 4 lines 753-774 and Task 8a lines 1860-1876.
- R8 BLOCK-26: PASS. DLQ `list/get/save` use `AsyncSession(self._engine)`; `replay/drop` use `self._engine.begin()` + `conn.execute()` at Task 6a.
- R8 BLOCK-27: FAIL. The monkeypatch is too late / wrong scope because imports happen before patching.
- R8 BLOCK-28: PASS. `_dispatch_row` catch point calls `logger.exception()` inside the `except` branch, lines 926-946; Known Constraints line 2551 says the same.
- R8 WARN-6: PASS. Logger is canonical: `logging.getLogger("reclaimrx.events.dlq_repository")`, line 1265.
- Regression scan: 17/18 pass. Regression item 2 fails: Python fences still contain literal `...`.

---

## Findings

**BLOCK-27** (carried from R8, partially fixed) — Task 6d, lines 1559 and 1578-1592: `create_app` and `get_idempotency_store` are imported before `monkeypatch.setattr("src._shim.db.get_async_engine_for_idempotency", ...)`. The implementation imports the factory at module scope in `src.events` line 1476, so patching `src._shim.db` after `src.events` is already imported will not affect the function object used by `get_idempotency_store()`. Fix: move `from src.main import create_app` and `from src.events import get_idempotency_store` inside the test after the monkeypatch, or change `get_idempotency_store()` to import `get_async_engine_for_idempotency` inside the function per call. Also reset `_idempotency_store` so prior tests cannot mask this.

**BLOCK-29** (new) — Regression item 2, multiple Python fences still contain literal `...`: Task 6a line 1312, Task 8a lines 1864-1865, Task 8b line 1948, Task 8c line 2104, Task 9b line 2473. Fix all Python-fence ellipses with concrete identifiers or prose outside code fences. Example: replace `` `get(entry_id) -> ... | None` `` with `` `get(entry_id) -> EventDLQEntry | None` ``.

---

## Recommendation

Do not execute Plan A2. Patch BLOCK-27 and BLOCK-29, then rerun the R8 verification checklist plus the full regression scan.

- BLOCK-27 (monkeypatch import ordering) is the highest blast radius — if the factory is already bound in `src.events` module scope before the patch lands, the idempotency wiring test will silently pass with a stale real engine in CI and fail at runtime with a different error.
- BLOCK-29 (literal `...` in fences) will cause executor to copy non-runnable code and produce import or syntax errors at test time.
