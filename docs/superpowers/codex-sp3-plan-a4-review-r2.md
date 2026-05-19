# SP-3 Plan A4 - Adversarial Re-Review R2

**Date:** 2026-05-19
**Reviewer:** Codex R2 (automated adversarial re-review)
**Input A:** docs/superpowers/plans/2026-05-18-sp3-plan-a4-endpoints-auth.md (updated post-R1)
**Input B:** docs/superpowers/codex-sp3-plan-a4-review-r1.md (R1 NO-GO, 8 BLOCKs)
**Grounding:** waves/B10/SP-3-audit-deep.md, shared/auth/dependencies.py, error-handling.md, phi-compliance.md, event-bus.md, modules/reclaimrx/src/api/router.py
**Note:** shared/auth/types.py - FILE_NOT_FOUND on disk (see NEW-1 below)

---

## R1 Block Verification Table

| # | BLOCK | Severity | Plan Section | Evidence | Status | Gap |
|---|-------|----------|--------------|----------|--------|-----|
| 1 | response_model=dict; HoldRelease schemas; MlScoreListRead | HIGH | T1 schemas block | Plan defines MlScoreListRead, InvestigationMlScoreListRead, InvestigationNoteRead. HoldReleaseRequest/HoldReleaseRead in schema table under T3. response_model=dict removed. | PARTIAL | T3 handler code block does not set response_model=HoldReleaseRead at the FastAPI route decorator level. Cannot confirm typed response_model enforced at the decorator. |
| 2 | Auth surface uses shared/auth/dependencies.py require_roles; no shim imports | CRITICAL | T1 auth bindings | Plan imports require_roles and get_current_user from shared.auth.dependencies. RECLAIMRX_VIEWER_DEP, RECLAIMRX_INVESTIGATOR_DEP, RECLAIMRX_ADMIN_DEP bound as require_roles at module load. | PARTIAL | REGRESSION: T1 still states thin wrappers require_viewer/require_investigator/require_admin from src._shim.auth are preserved for backward-compatibility. R1 required shim elimination not preservation. |
| 3 | MFA gate raises 403 MFA_REQUIRED not 503; applied to all write/state-change endpoints | CRITICAL | T2 MFA section | Plan defines require_mfa_elevated raising HTTPException status_code=403. Applied to graph trigger, investigation transitions, threshold update. | PARTIAL | TWO REGRESSIONS: (a) T2 intro still contains text about falling back to 503 MFA_CHECK_UNAVAILABLE. (b) POST /holds/{id}/release not shown with Depends require_mfa_elevated in T3 handler stub. |
| 4 | X-Tenant-Id header: 400 INVALID_TENANT_HEADER / 403 TENANT_MISMATCH | HIGH | T2 tenant section | Plan defines require_tenant_match. Returns 400 INVALID_TENANT_HEADER on missing/malformed UUID. Returns 403 TENANT_MISMATCH on cross-tenant. Applied to every new endpoint. | **RESOLVED** | No gap found. |
| 6 | POST idempotency-key REQUIRED header; per-endpoint format; graph replay | HIGH | T4 idempotency section | Plan uses idempotency_key Header with ellipsis meaning required. Per-endpoint formats documented for graph_run, inv_transition, inv_note, threshold_update. Graph trigger checks existing run row and returns early. | PARTIAL | (a) holds/{id}/release idempotency format absent from per-endpoint table. (b) Graph replay HTTP status code unspecified - 200 vs 202 vs 409 - ambiguous contract. |
| 11 | build_error_envelope helper; no inline dicts; correlation_id fallback | HIGH | T5 errors section | Plan defines build_error_envelope in src/api/errors.py. Includes get_correlation_id contextvar fallback. | PARTIAL | MFA gate example in T2 and tenant-mismatch example in T4 both still inline error dict construction instead of calling build_error_envelope. |
| 13 | Dependency ordering 401 to role to tenant to MFA to business | HIGH | T6 ordering section | Plan states invariant in prose: FastAPI evaluates Depends in declaration order. | PARTIAL | transition_investigation handler stub declares body and db before user - get_db fires before role gate, violating the stated ordering invariant. |
| 14 | Route matrix covers all 18 spec section 5.5 endpoints; lower-role 403; tenant-mismatch 403 tests | HIGH | T9 route matrix | Plan includes 18-row matrix by method, path, role floor. Parametrized tests described. | PARTIAL | Row 5 in plan = GET /investigations/{id}/ml-scores. Spec section 5.5 endpoint 5 = GET /rule-firings. Different resources. GET /rule-firings absent from matrix and test plan. |

---

## New Issues Table

| # | Issue | Severity | Evidence | Recommendation |
|---|-------|----------|----------|----------------|
| NEW-1 | shared/auth/types.py does not exist on disk | CRITICAL | FILE_NOT_FOUND when reading shared/auth/types.py. Plan imports CurrentUser from shared.auth.types. Real CurrentUser lives in shared/auth/dependencies.py. | Fix import to reference the actual module on disk. |
| NEW-2 | Hold-release event type not specified in plan | HIGH | Neither payment.hold_released nor fwa.hold_released appears in plan text. Spec section 5.5 requires payment.hold_released. | Add event_type=payment.hold_released to T3 hold-release task. Not fwa.hold_released. |
| NEW-3 | GET /api/v1/reclaimrx/rule-firings missing from route matrix | HIGH | Spec section 5.5 row 5 = GET /rule-firings. Plan matrix row 5 = GET /investigations/{id}/ml-scores. Different resources. | Add rule-firings to route matrix and test parametrize list. If deferred, document with spec reference. |
| NEW-4 | Stale shim thin-wrapper test imports defeat BLOCK 2 fix | MEDIUM | Plan explicitly preserves shim for backward-compat in T1. Tests importing require_viewer from src._shim.auth exercise shim path not shared auth path. | Remove shim entirely. Update all tests to use RECLAIMRX_VIEWER_DEP, RECLAIMRX_INVESTIGATOR_DEP, RECLAIMRX_ADMIN_DEP dependency override pattern. |
| NEW-5 | Header ellipsis = REQUIRED confirmed correct | INFO | Plan uses idempotency_key: str = Header with ellipsis. Ellipsis means required in FastAPI/Pydantic. Correct. | No action required. Confirmed non-issue. |
| NEW-6 | risk_score typed as float in MlScoreRead schema | MEDIUM | MlScoreRead.risk_score typed as float in plan schema table. Risk scores feed financial adjudication - financial-precision rules apply. | Change to Decimal with json_encoders or model_config serialization override. |

---

## Verdict

**NO-GO**

---

## Summary

- BLOCK 2 (PARTIAL - regression): Shim thin-wrappers explicitly preserved for backward-compat, directly contradicting R1 fix requirement to eliminate them.
- BLOCK 3 (PARTIAL - two regressions): 503 fallback text remains in plan; hold-release endpoint not shown as MFA-gated.
- BLOCK 13 (PARTIAL): transition_investigation handler stub declares db before user, violating 401 to role to tenant to MFA ordering invariant.
- BLOCK 14 (PARTIAL): GET /rule-firings absent from route matrix; non-spec endpoint substituted at row 5.
- NEW-1 (CRITICAL): shared/auth/types.py does not exist on disk - plan imports from a phantom module.
- NEW-2 (HIGH): Hold-release event type unspecified - spec mandates payment.hold_released.
- BLOCK 1, 6, 11 (PARTIAL): Typed response_model not explicit at decorator level; hold-release idempotency contract missing; build_error_envelope not used in plan code samples.
- BLOCK 4: RESOLVED.

---

## Recommendation

Plan A4 has improved since R1 but contains two regressions (BLOCK 2 shim preservation clause, BLOCK 3 503-fallback text) and one critical new defect (NEW-1: phantom module shared/auth/types.py that does not exist on disk). Before execution begins, the author must: (1) eliminate the shim entirely and remove the backward-compat preservation clause from T1; (2) delete all 503 MFA fallback text and replace with 403-only behavior; (3) fix the shared.auth.types import to reference the actual module present on disk; (4) add payment.hold_released event type to the hold-release task; (5) add GET /rule-firings to the route matrix and parametrized test list; (6) reorder the transition_investigation handler stub so user (role gate) comes before db; (7) replace all inline error dict constructions in plan code samples with build_error_envelope calls. A R3 review is required only if items 1 through 3 (regressions + phantom import) are disputed - the remaining items are fixable by the author without re-review.
