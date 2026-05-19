# R4 Adversarial Review — SP-3 Plan A2

| BLOCK_ID | Status | Evidence |
|---|---|---|
| BLOCK-7 | RESOLVED | `rg "_resolve_db_url"` returned zero hits. Plan 6c uses `get_engine().url`: "No parallel URL resolver." |
| BLOCK-9 | RESOLVED | Plan lines 1155-1174: `replay(..., *, tenant_id)` uses `async with self._engine.begin()`, `update(EventDLQEntry).where(id == entry_id, tenant_id == tenant_id, status == "queued")`, returns `int(result.rowcount or 0)`. |
| BLOCK-10 | RESOLVED | Plan lines 1179-1182 mention `dropped_at` only as explanatory prose. `drop()` lines 1186-1198 only sets `status="dropped"`. |
| BLOCK-11 | STILL_BLOCKED | Production Python fences still contain literal `...`: plan lines 722-723 `UPDATE ... WHERE` / `RETURNING ...`; lines 1758-1759 append `"..."` in log fields. Verification requires zero literal `...` hits. |
| BLOCK-12 | RESOLVED | Plan lines 733-746 state the `try/finally: return` wrapper was removed; `_poll_once` directly claims and dispatches rows. |
| BLOCK-13 | RESOLVED | Plan lines 1176-1198: `drop(..., *, tenant_id)` uses one `self._engine.begin()` block, tenant-scoped `update(EventDLQEntry)`, returns rowcount. |
| NEW-1 | NEW | Plan lines 974-996 call `await repo.get(entry_id)` without `tenant_id`, but the planned API at lines 1133-1138 requires `get(entry_id, *, tenant_id)`. Fix test to call `repo.get(entry_id, tenant_id=tenant_id)`. |
| NEW-2 | NEW | Plan lines 835-846 log `svc_error = error_str` where `error_str` includes `str(exc)[:200]`. Exception messages can contain serialized payload/PHI; truncation is not sanitization. Log exception class plus non-PHI error metadata only. |

## Additional Checks

- `get_async_engine_for_idempotency()` is called in lifespan at lines 2147-2151 with no ellipsis placeholder.
- No `fwa.hold_released` appears. `fwa.graph_run_completed` appears and is allowed by spec line 56.
- `DLQ get()` accepts `tenant_id` as a keyword-only arg at lines 1133-1138.
- No bare production `pass` or `NotImplementedError` found.
- No `Float` or money-handling `float` found; float hits are scheduler intervals/DLQ age.
- Repository read/mutate methods are tenant-scoped in `list`, `get`, `replay`, and `drop`.

## Verdict
**NO-GO**

## Summary
R4 resolves the core R3 issues for `_resolve_db_url`, `dropped_at`, tenant-scoped DLQ replay/drop, and dispatcher exception suppression. It remains blocked by literal `...` inside production Python fences, a stale DLQ test call that omits `tenant_id`, and PHI-risky raw exception logging.

## Recommendation
Remove all literal `...` from production Python fences, update `test_save_and_get` to pass `tenant_id`, and replace raw exception-message logging with sanitized non-PHI error metadata.
