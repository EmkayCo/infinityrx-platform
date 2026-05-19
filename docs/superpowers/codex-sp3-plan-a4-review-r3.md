# SP-3 Plan A4 — R3 Adversarial Review

## R2 Issue Resolution Table

| ID | Issue | Status | Evidence |
|----|-------|--------|----------|
| NEW-1 | `shared.auth.types` phantom import | RESOLVED | `rg shared.auth.types` returned 0 matches in A4; `CurrentUser` imports are from `shared.auth.dependencies` at A4 plan lines 111, 256, 766, 1129, 1402, 1958. |
| NEW-3/BLOCK-14 | route matrix row 5 = `/rule-firings` | RESOLVED | `SPEC_ENDPOINTS_18` row 5 is `(5, "GET", "/api/v1/reclaimrx/rule-firings", "reclaimrx.viewer")` at A4 plan lines 1963-1970; spec row 5 is rule-firings at spec lines 289-298. |
| BLOCK-3 | 503 MFA_CHECK_UNAVAILABLE removed | RESOLVED | `rg MFA_CHECK_UNAVAILABLE` returned 0 matches in A4; A4 requires 403 `MFA_REQUIRED` at lines 89, 176-182, 240, 1638, 2152. |
| NEW-4 | test fixtures use `dependency_overrides` | RESOLVED | Fixtures override `app.dependency_overrides[get_current_user] = lambda: ...` at A4 plan lines 766-793, 1129-1151, 1402-1424, 2014-2015; `rg 'set_current_user('` returned 0 matches. |
| BLOCK-11 | `build_error_envelope` replaces inline dicts | RESOLVED | `build_error_envelope` imported at A4 plan line 258; `HTTPException` details use it at lines 315, 336, 347, 356, 1032, 1062, 1299-1304, 1314-1319, 1598, 1625; no inline `detail={"error": ...}` dicts found. |
| BLOCK-13 | `user` before `db` in all three handlers | PARTIAL | RESOLVED for `transition_investigation` (A4 lines 1772-1781). RESOLVED for `release_hold_v2` in A3 (lines 1629-1636). STILL OPEN for `trigger_graph_run`: `db` is before `user` at A4 lines 1245-1255. |
| BLOCK-1 | A3 `release_hold_v2` `response_model` decorator | RESOLVED | A3 decorator has `response_model=HoldReleaseRead` at A3 plan lines 1624-1628. |
| NEW-2 | `event_type = payment.hold_released` | RESOLVED | A3 test asserts `payment.hold_released` at A3 lines 1443-1444; outbox envelope uses `event_type="payment.hold_released"` at lines 1551-1553 and 1570-1574; docstring names it at lines 1638-1641; `rg fwa.hold_released` returned 0 matches in A3/A4. |

## New Issues Found

### NEW-R3-1 — BLOCK — Dependency ordering violation in additional handlers

A4 has `db` before `user` in multiple endpoint stubs beyond the BLOCK-13 trio already checked:

- `list_ml_scores`: `db` before `user` at A4 lines 975-982
- `get_ml_score_features`: `db` before `user` at A4 lines 1016-1021
- `list_investigation_ml_scores`: `db` before `user` at A4 lines 1042-1049
- `trigger_graph_run`: `db` before `user` at A4 lines 1245-1255 (the confirmed BLOCK-13 regression)
- `update_thresholds`: `db` before `user` at A4 lines 1530-1537
- `get_investigation`: `db` before `user` at A4 lines 1582-1588
- `add_investigation_note`: `db` before `user` at A4 lines 1797-1803
- `list_rule_firings`: `db` before `user` at A4 lines 1886-1894

Fix required: in every handler, the dependency order must be: auth/role header, tenant, MFA, idempotency header, then `db: Session = Depends(get_db)`.

### NEW-R3-2 — BLOCK — Idempotency-Key body/header contract inconsistency on hold release

`HoldReleaseRequest` still contains a body-level `idempotency_key` field (A4 plan lines 598-609) despite the plan requiring the `Idempotency-Key` header on all POSTs (A4 lines 2156-2159). This creates two competing idempotency contracts on the same endpoint.

Fix required: remove `idempotency_key` from `HoldReleaseRequest` body; `release_hold_v2` must receive it via `idempotency_key: str = Header(..., alias="Idempotency-Key")`.

### NEW-R3-3 — WARN — `build_error_envelope` import scope not explicit in all handler sections

A4 has a single `build_error_envelope` import at line 258, but handler code snippets at lines 1032, 1062, 1299, 1314, 1598, and 1625 use it in separate sections without restating the import. If these sections land in separate router files, each will fail at import time.

Fix required: either confirm all snippets belong to the same router module after the line-258 import, or add the import explicitly in each handler file/section that constructs an error response.

## Verdict

**NO-GO**

## Summary

A4 resolved the core R2 text regressions: phantom auth import gone, `/rule-firings` in route matrix, MFA failures are 403-only, test fixtures use `dependency_overrides`, inline error dicts replaced with `build_error_envelope`, and A3 hold-release has the typed decorator plus `payment.hold_released`. The BLOCK-13 ordering fix was applied to `transition_investigation` and A3 `release_hold_v2`, but `trigger_graph_run` still has `db` before `user`, and a deeper scan found the same ordering violation in seven additional handlers. There is also a hard idempotency contract conflict on hold release where both a body field and a required header claim ownership of the key.

## Recommendation

Do not implement A4 as written. Perform a targeted A4 revision that: (1) moves `db` after all auth/tenant/MFA/header dependencies in every handler — a mechanical pass over every `async def` in the plan; (2) removes `idempotency_key` from `HoldReleaseRequest` body; (3) makes the `build_error_envelope` import explicit per router file. Then submit for a narrow R4 diff review scoped only to dependency ordering and idempotency-key placement — the remaining issues are fully localised and an R4 should reach GO or GO-WITH-CHANGES quickly.
