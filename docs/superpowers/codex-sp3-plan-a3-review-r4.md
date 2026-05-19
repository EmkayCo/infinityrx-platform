# SP-3 Plan A3 — Adversarial Re-Review R4

**Reviewer:** Codex adversarial subagent
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md (post-R3 revision)
**R3 source:** docs/superpowers/codex-sp3-plan-a3-review-r3.md
**Tokens used:** 613,563

---

## R3 Fix Verification

| Item | Check | Evidence | Status |
|------|-------|----------|--------|
| BLOCK-2a | `transition_investigation_status` uses `build_error_envelope()` for all 4 error branches | Lines 1150-1199: 404 pre-check, 404 ValueError, 500 ValueError fallthrough, 422 InvalidTransitionError all use build_error_envelope() | PASS |
| BLOCK-2b | `trigger_graph_run` uses `build_error_envelope()` for 409 + extends with `existing_run_id` after construction | Lines 2887-2897: envelope = build_error_envelope("RUN_IN_PROGRESS",...); envelope["error"]["existing_run_id"] = exc.existing_run_id | PASS |
| BLOCK-2c | `release_hold_v2` route rebuilds service raw dict via `build_error_envelope()` for 409/422 and re-attaches extras | Lines 1716-1734: if status_code in (409, 422): svc_err = response_body["error"]; envelope = build_error_envelope(...); re-attach released_at/released_by/reason | PASS |
| WARN-1 | Task 5 test docstring states 2 A3 detectors + explicit B11 deferral | Lines 1763-1769: "Tests the TWO A3 pattern detectors (sudden_spike, multi_payer_convergence)... reset_evasion and threshold_oscillation detectors are explicitly deferred to B11" | PASS |
| BLOCK-1 (R3 FP) | Closed states match spec — 3 states only | Spec §5.5.1 lines 322-324 + 333: exactly closed_confirmed, closed_false_positive, closed_no_action | CONFIRMED FALSE POSITIVE — not re-raised |

---

## Verdict

**NO-GO**

---

## Summary

- R3 BLOCK-2 replacements are fully present: all route-level error paths use `build_error_envelope()`. Raw `{"error": ...}` dicts remain only in service-return branches and test assertions, which is correct.
- R3 WARN-1 is fixed: Task 5 docstring accurately states two A3 detectors and defers reset_evasion/threshold_oscillation to B11.
- All regression checklist items pass: event name, TRANSITION_REQUIRED_FIELDS type/contents, graph computation pipeline, _A3_AUTO_OPEN_PATTERNS gating, HoldReleaseRequest body shape, dependency order.
- New blocker (BLOCK-1): every hold-release test POSTs without `Idempotency-Key` header, but the route now requires it as a mandatory FastAPI `Header(...)` parameter. All 9 Task 4 tests plus the Task 8 registration test will fail with 422 before reaching intended business logic.
- WARN-1 (sequencing): `build_error_envelope` is first imported in the plan at line 1636 (Task 4 block), but Task 3 route handler uses it without an earlier import declaration.
- WARN-2 (pattern): Task 3 and Task 7 route handler signatures still place `db: Session = Depends(get_db)` before `user: CurrentUser` in the parameter list, inverting the auth-before-business ordering established in Task 4.

---

## Findings

**BLOCK-1:** Task 4 tests + Task 8 test — `Idempotency-Key` header missing from all test POSTs.

`release_hold_v2` declares `idempotency_key: str = Header(..., alias="Idempotency-Key")` (line 1652). FastAPI will 422 every request that omits it. Every `client.post(f"/api/v1/reclaimrx/holds/{hold_id}/release", json={...})` in Task 4 tests (lines 1317-1459) omits `headers={"Idempotency-Key": ...}`. The Task 8 create_app registration test at lines 2938-2942 (`resp = client.post("/api/v1/reclaimrx/holds/no-such-id/release", json={...})`) also omits it.

Fix: Add `headers={"Idempotency-Key": f"hold:release:{hold_id}:{uid}"}` (or a fixed sentinel value) to every `client.post(/.../release)` call in:
- `test_viewer_cannot_release` (must still use 403 path — viewer blocked before header parsed)
- `test_normal_release_returns_200`
- `test_missing_reason_returns_422`
- `test_investigation_mismatch_returns_403`
- `test_idempotency_case_a_same_actor_and_reason_returns_200` (both calls)
- `test_idempotency_case_b_different_actor_returns_409` (both calls)
- `test_idempotency_case_b_different_reason_same_actor_returns_409` (both calls)
- `test_idempotency_case_c_expired_hold_returns_422`
- `test_outbox_row_written_on_release`
- Task 8 `test_hold_release_endpoint_registered`

**WARN-1:** Task 3 (3b router edit) — `build_error_envelope` used before import declaration.

The plan introduces `build_error_envelope` in the Task 3 route body but the explicit import (`from src.api.errors import build_error_envelope`) first appears in the Task 4 block at line 1636. If the executor follows the strict TDD sequence (Task 3 before Task 4), the Task 3 route will raise `NameError: name 'build_error_envelope' is not defined` at test time.

Fix: Add `from src.api.errors import build_error_envelope  # noqa: E402` to the Task 3 implementation block (3b), before the route snippet.

**WARN-2:** Task 3 and Task 7 route signatures — `db` parameter before `user`.

`transition_investigation_status` (lines 1112-1115) and `trigger_graph_run` (lines 2867-2870) declare `db: Session = Depends(get_db)` before `user: CurrentUser = Depends(require_role(...))`. In FastAPI, dependency order doesn't affect HTTP short-circuit behavior (auth Depends always runs), but it creates an inconsistency with Task 4's documented auth-before-business pattern and may confuse future readers into thinking DB sessions are cheaper than auth checks.

Fix (low-urgency): Move `db: Session = Depends(get_db)` to after the auth dependency in both route signatures, matching the Task 4 ordering discipline.

**PASS-1:** R3 BLOCK-2 fully verified. All five error paths in transition, hold, and graph-trigger routes use `build_error_envelope()`. Raw inline dicts in service-layer return values (409/422 branches) are correct — the route layer rebuilds them at lines 1716-1734.

**PASS-2:** R3 WARN-1 fully verified. Task 5 docstring at lines 1763-1769 correctly states two A3 detectors and explicitly defers reset_evasion and threshold_oscillation to B11/follow-on/accumulator-patterns-3-4.

**PASS-3:** `payment.hold_released` event name confirmed at lines 1457, 1565, and 1586. No `fwa.hold_released` variant found anywhere in the plan.

**PASS-4:** `TRANSITION_REQUIRED_FIELDS` is `dict[tuple[str, str], frozenset[str]]`. `closed_confirmed` arcs require `frozenset({"reason", "outcome_label", "recovered_amount"})`; `closed_false_positive` and `closed_no_action` arcs require `frozenset({"reason", "outcome_label"})`; re-open arcs require `frozenset({"reason"})`. Lines 403-422.

**PASS-5:** `_run_graph_computation` pipeline verified at lines 2430-2542: queries `FlaggedClaim`, aggregates to `GraphEdge` via `defaultdict`, calls `FraudNetworkAnalyzer().build_graph(edges)`, calls `.detect_communities(graph)`, caps entity_refs at `refs[:500]`.

**PASS-6:** `_A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})` and membership gate `if anomaly.pattern_type in _A3_AUTO_OPEN_PATTERNS` confirmed at lines 1971-1975.

**PASS-7:** `release_hold_v2` dependency order verified: user (RECLAIMRX_INVESTIGATOR_DEP) → `_tenant_check` → `_mfa` → `idempotency_key: str = Header(...)` → `db: Session = Depends(get_db)`. Lines 1648-1653. `HoldReleaseRequest` has no `idempotency_key` body field. Lines 1613-1625.

**PASS-8:** R3 BLOCK-1 confirmed false positive. Spec §5.5.1 (lines 322-324) and spec line 333 define exactly 3 closed states: `closed_confirmed`, `closed_false_positive`, `closed_no_action`. Plan constants and tests match. Not re-raised.

---

## Recommendation

Patch all hold-release test calls to include `headers={"Idempotency-Key": "..."}` (BLOCK-1) and add the `build_error_envelope` import to the Task 3 implementation block (WARN-1), then rerun a narrow R5 check against those two items only.
