# R4 Adversarial Review — SP-3 Plan A4 Endpoints + Auth

**Reviewer:** Codex CLI (R4)
**Date:** 2026-05-19
**Inputs:**
- `docs/superpowers/plans/2026-05-18-sp3-plan-a4-endpoints-auth.md`
- `docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md`
- `docs/superpowers/codex-sp3-plan-a4-review-r3.md`
- `shared/auth/dependencies.py`

---

## R3 BLOCK Verification

| ID | Status | Evidence |
|----|--------|----------|
| NEW-R3-1 | **RESOLVED** | All 10 reviewed async handlers declare `user: CurrentUser = ...` before `db: Session = Depends(get_db)` or equivalent business dependencies: `list_ml_scores` lines 985-992; `get_ml_score_features` lines 1027-1032; `list_investigation_ml_scores` lines 1056-1061; `trigger_graph_run` lines 1258-1266; `update_thresholds` lines 1542-1549; `get_investigation` lines 1595-1602; `transition_investigation` lines 1787-1796; `add_investigation_note` lines 1812-1819; `list_rule_firings` lines 1903-1911; A3 `release_hold_v2` lines 1631-1640. |
| NEW-R3-2 | **RESOLVED** | A4 `HoldReleaseRequest` body has only `reason`, `investigation_id`, `emergency_reason_code`, and `emergency_note` at lines 598-618; `idempotency_key` is supplied by `Idempotency-Key` header. A3 `HoldReleaseRequest` likewise has only those four fields at lines 1600-1612, and A3 `release_hold_v2` uses `idempotency_key: str = Header(..., alias="Idempotency-Key")` at lines 1638-1639. |

---

## New Issues

| ID | Location | Issue | Severity |
|----|----------|-------|----------|
| R4-INFO-1 | A4 lines 1902-1911; A4 lines 1980-2000 | SPEC_ENDPOINTS_18 row 5 present and correctly maps `(5, GET, /api/v1/reclaimrx/rule-firings, reclaimrx.viewer)`; endpoint implemented as `@router.get("/rule-firings")` with `async def list_rule_firings`. No violation. | INFO |
| R4-INFO-2 | A4 lines 1258-1265, 1542-1548, 1595-1602, 1787-1795; A3 lines 1631-1639 | MFA-gated handlers include `Depends(require_mfa_elevated)`: graph trigger, threshold update, investigation detail, investigation transition, and hold release. No endpoint found where an MFA-gated endpoint uses only a role dependency without `require_mfa_elevated`. | INFO |
| R4-INFO-3 | Auth contract `shared/auth/dependencies.py` lines 49, 139-142, 166-170; A4 imports lines 110-111, 252-256, 775, 1141, 1413, 1975, 2031 | A4 uses `shared.auth.dependencies` for `CurrentUser`, `get_current_user`, and role factories. `rg shared.auth.types` returned zero A4 matches. No phantom `shared.auth.types` import found. | INFO |
| R4-INFO-4 | A4 lines 1257-1265, 1541-1548, 1785-1795, 1807-1818; A3 lines 1626-1639 | Every POST/PUT handler in the reviewed A4 endpoint set declares required `Idempotency-Key` via `Header(..., alias="Idempotency-Key")`: graph trigger, thresholds update, investigation transition, investigation note; A3 hold release also declares the same required header. No violation. | INFO |

**No new BLOCK or WARN issues found beyond the R3 items, and both R3 items are resolved.**

---

## Verdict

**GO**

---

## Summary

R4 verifies that the R3 dependency-ordering block is resolved across all 10 named handlers, including the A3-owned `release_hold_v2`. The hold-release idempotency contract is now header-only in both A4 and A3 request schemas. The targeted new scan found `/rule-firings` correctly mapped, MFA-gated handlers using `require_mfa_elevated`, A4 auth imports grounded in `shared.auth.dependencies`, and required `Idempotency-Key` headers on reviewed POST/PUT handlers.

---

## Recommendation

Proceed with implementation. Keep the route-matrix and idempotency-header tests in CI so these auth/order guarantees remain locked during execution.
