# Codex Adversarial Review R5 — SP-3 Plan A2 (Outbox + Dispatcher + Scheduler + DLQ + Idempotency)

**Reviewed:** 2026-05-19
**Model:** gpt-5.5
**Session:** 019e401b-dcd8-72e1-a262-e97f8af5ad4b
**Tokens used:** 39,776

---

## Verdict
**GO-WITH-CHANGES**

---

## Summary

- **R4 BLOCK-11 carry-forward: PASSED.** No literal `...` (triple-dot ellipsis) appears inside any ` ```python ` code fence. The only `...` in the plan is inline prose at plan:82 (`NEVER write: EventEnvelope(type=..., emitted_at=...)`), which is not executable code.
- **R4 NEW-1: PASSED.** `test_save_and_get` at plan:999 calls `repo.get(entry_id, tenant_id=tenant_id)` — keyword-only signature matched.
- **R4 NEW-2 implementation: PASSED.** The `publish_failed` except branch (plan:834–849) stores only `exc.__class__.__module__ + "." + exc.__class__.__name__` in `error_label`; no `str(exc)`, no `exc.args`. Log field is `svc_error_class`. PHI-safe.
- **Regression scan: ALL PASSED.**
  - `payment.hold_released` event name preserved throughout (never `fwa.hold_released`).
  - Postgres claim path uses `FOR UPDATE SKIP LOCKED` at plan:763.
  - DLQ `replay()` and `drop()` both scope by `tenant_id` keyword arg.
  - `dropped_at` column is not referenced anywhere; `status='dropped'` is the sole signal.
  - Middleware test uses `m.cls` (not `type(m.cls)`) at plan:2043.
  - Audit chain ordering: `ORDER BY tenant_id, changed_at, id` at plan:1029–1031.
  - `PostgresIdempotencyStore` wired via `get_idempotency_store()` + `get_async_engine_for_idempotency()` at plan:1287–1292.

---

## Findings

**BLOCK-12** — plan:565–578 — **Stale dispatcher failure test assertion conflicts with R4 NEW-2 fix**

The test `test_publish_failure_increments_attempt_count` asserts:
```python
assert "broker down" in (row.last_error or "")
```
But the implementation at plan:839–841 now stores only the exception class label (`builtins.ConnectionError`), never the exception message. This test will either:
1. Fail at runtime (because `"broker down"` is not in `"builtins.ConnectionError"`), OR
2. Force the executor to revert to message-containing storage to make the test pass — which undoes the PHI-safe R4 NEW-2 fix.

**Fix required:** Replace the assertion with class-name-only checks:
```python
assert row.last_error is not None
assert row.last_error.endswith(".ConnectionError")
assert "broker down" not in row.last_error
```

**WARN-1** — plan:2254 — **Known-constraints section contradicts R4 NEW-2 fix**

The line reads:
> `last_error` on OutboxEvent must be sanitized (200-char truncated type+message only).

This says "type+message" — but the R4 NEW-2 fix stores class name only (no message). The constraint is now stale and will mislead the executor into thinking exception message content is acceptable in `last_error`.

**Fix required:** Update to:
> `last_error` on OutboxEvent must be sanitized — store exception class name only (`module.ClassName`). NEVER include exception args, message text, or any string derived from the exception payload (PHI risk per phi-compliance.md + R4 NEW-2).

---

## Recommendation

Two surgical patches to the plan before execution:

1. **plan:578** — Replace `assert "broker down" in (row.last_error or "")` with class-name-only assertions (see BLOCK-12 fix above).
2. **plan:2254** — Update the known-constraints `last_error` bullet to class-name-only (see WARN-1 fix above).

After those two patches are applied, R5 becomes **GO** with no further review required for these items.
