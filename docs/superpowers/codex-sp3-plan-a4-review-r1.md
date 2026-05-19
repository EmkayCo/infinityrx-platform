# Codex Adversarial Review -- SP-3 Plan A4 (Endpoints + Auth)

**Plan under review:** docs/superpowers/plans/2026-05-18-sp3-plan-a4-endpoints-auth.md
**Reviewer:** Codex CLI (adversarial review mode)
**Date:** 2026-05-19
**Prior context:** Plans A1/A2/A3 all received NO-GO verdicts; A4 must not repeat those mistakes.

---

## Review Verdict Table

| # | Concern | Severity | Plan ref | Evidence (path:line) | Fix |
|---:|---|---|---|---|---|
| 1 | Section 6 endpoint inventory not fully covered. A4 delegates POST /holds/release to A3 and uses response_model=dict for ML list responses. | BLOCK | Scope/T3/T6 | Spec endpoints: spec.md:293-310; release body at :301. A4 delegates at plan :54, :1141; dict responses at :675, :738. | Wire hold release body schema in A4 and replace dict response models with typed Pydantic schemas. |
| 2 | Auth dependencies do not match shared/auth/dependencies.py; A4 uses shim auth and invented require_viewer/require_admin. | BLOCK | A4-T1 | Shared auth at shared/auth/dependencies.py:139-195 exposes get_current_user, require_roles, require_permissions -- no require_role. A4 imports src._shim.auth at plan :94, :151. | Use shared require_roles(...) or explicitly document shim-only scope with migration ticket. |
| 3 | MFA gating under-applied and wrong status. Only on investigation detail, not graph trigger or hold release; returns 503 not 403 MFA_REQUIRED. | BLOCK | A4-T1/T4/T6 | Spec D6a at spec :70, :504. A4 stub returns 503 at plan :175-194; graph trigger uses only require_investigator at :887-890; release delegated. | Implement real fail-closed 403 MFA_REQUIRED and apply to all spec-required endpoints. |
| 4 | Tenant header validation absent. A4 tenant-scopes queries but never validates x-tenant-id header mismatch. | BLOCK | Cross-cutting | Spec requires mismatched header -> 403 TENANT_MISMATCH at spec :503. A4 only mentions cross-tenant data tests at plan :72. | Add reusable tenant-header dependency that fires before business logic on every endpoint. |
| 5 | Advisory lock uses deterministic zlib.crc32. | PASS | A4-T4 | A4 bans hash() at plan :66, tests crc32 at :854-858, implements at :884-901. Spec requires this at spec :5.5.3. | Keep. |
| 6 | POST idempotency incomplete and not tied to A2/A3 key design. | BLOCK | A4-T4/T7 | A4 delegates hold idempotency to A3 at plan :8, :54; graph trigger uses running-row conflict only at :909-930; transitions/notes have no idempotency at :1318-1351. | State exact idempotency key shape per POST endpoint or mark non-idempotent explicitly. |
| 7 | GraphRun.status=running row is correctly the cross-process authority. | PASS | A4-T4 | A4 at plan :893-895 and :909-950. Spec at spec :244, :461-465. | Keep. |
| 8 | A4 does not redefine A1 ORM tables/A2 outbox/A3 state machine -- imports only. | PASS | T3/T4/T5/T7 | Imports GraphRun, FraudRing, ThresholdConfig from src.models.tables at plan :478, :670, :800. | Keep. |
| 9 | Pydantic schemas use Decimal-as-string and no Float appears. | PASS | A4-T2/T3/T8 | Decimal-as-string at plan :209; str fields at :321, :366, :375, :393-407, :1377; no Float found. | Keep, but remove remaining dict response models. |
| 10 | TDD mostly explicit but T9 lacks fail/pass cycle and T3 uses shorthand for 7 endpoints. | CONCERN | T3/T9 | Cycles at plan :657, :776, :878, :977; T3 shorthand at :760; T9 missing pre-implementation failure at :1474-1552. | Expand T3 per-endpoint and add explicit T9 fail/implement/pass steps. |
| 11 | Error envelope does not match .claude/rules/error-handling.md. | BLOCK | Multiple | Required format at rules/error-handling.md:3-7. A4 examples omit message, field, correlation_id at plan :190-194, :727-729, :915-930, :1167, :1191-1194. | Add shared error-envelope helper and assert all required keys in tests. |
| 12 | PHI in errors/logs not fully proven absent. | CONCERN | T2/T3/T6 | PHI ban at rules/phi-compliance.md:8-11. A4 has some no-PHI checks at plan :593-596, :647-654 but no caplog tests. | Add caplog tests for PHI absence in error paths and service exceptions. |
| 13 | RBAC-before-tenant-before-business-logic order not specified or tested; 401 vs 403 unclear with shim auth. | BLOCK | T1/T9 | Shared auth 401 at shared/auth/dependencies.py:139-163; 403 at :166-175. Shim raises RuntimeError at src/_shim/auth.py:27-29. A4 role matrix only at plan :1519-1540. | Use shared auth and test 401 first, then 403 role, then 403 tenant mismatch, then business logic. |
| 14 | create_app() tests do not prove all routes are mounted/reachable. | BLOCK | T3/T4/T5/T9 | T9 covers 9 read + 2 write endpoints at plan :1499-1517; spec requires 18 at spec :293-310. | Add route matrix for all 18 endpoints asserting HTTP not 404/405. |
| 15 | Additive-only not enforced; no duplicate-route guard. | CONCERN | T6 | A4 modifies existing handlers at plan :1139-1213; router.py existing handlers at :287-341, :460-493, :574-589. | Add route table duplicate checks; document which existing partial handlers are modified. |

---

## Verdict

**NO-GO**

---

## Summary of BLOCKs

- **Auth contract mismatch:** A4 wires shim auth and invents require_viewer/require_admin instead of shared/auth/dependencies.py (require_roles, require_permissions).
- **MFA gating incomplete and wrong status:** MFA only on investigation detail, not on graph trigger or hold release per spec section 7; returns 503 not 403 MFA_REQUIRED.
- **Tenant header validation absent:** A4 tenant-scopes DB queries but never validates x-tenant-id header; mismatched header must return 403 TENANT_MISMATCH.
- **Hold release endpoint not fully owned by A4:** Spec assigns hold release body to A4 but A4 delegates to A3; ML list endpoints use untyped dict response_model.
- **POST idempotency not defined end-to-end:** Graph trigger uses running-row conflict only; transition/note POSTs have no idempotency semantics vs A2 outbox design.
- **Error envelopes non-compliant:** A4 error examples omit message, field, correlation_id required by error-handling.md.
- **RBAC/tenant/logic ordering not tested:** Shim auth makes 401-vs-403 distinction untestable; ordered dependency chain never asserted.
- **create_app() route coverage incomplete:** T9 covers 11 of 18 spec-required endpoints; 7 unchecked for mount/reachability.

---

## Recommendation

Do not dispatch A4 as written. The plan is solid on its targeted concerns: deterministic graph locking via zlib.crc32, GraphRun row as cross-process authority, Decimal-as-string serialization, and clean import-only delegation to A1/A2/A3. However, auth closure is not execution-safe. Revise A4 to wire the real shared/auth/dependencies.py surface, add tenant-header validation on every endpoint, implement fail-closed 403 MFA_REQUIRED across all gated endpoints, own the hold-release response schema, define explicit idempotency key contracts per POST, enforce the error-handling.md envelope in every error example, and expand the T9 integration matrix to all 18 spec endpoints before moving to GO-WITH-CHANGES.
