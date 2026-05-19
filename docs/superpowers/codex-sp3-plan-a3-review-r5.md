# SP-3 Plan A3 — Adversarial Re-Review R5

**Reviewer:** Codex adversarial subagent (via /codex consult)
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md (post-R4 revision)
**R4 source:** docs/superpowers/codex-sp3-plan-a3-review-r4.md
**Tokens used:** 582,400

---

## R4 Fix Verification

| Item | Check | Evidence | Status |
|------|-------|----------|--------|
| BLOCK-1 | All 13 `client.post(.../holds/.../release)` calls pass `headers=_idem(hold_id, actor)` | All release POSTs including Task 8 `test_hold_release_endpoint_registered` now pass `headers=` argument with Idempotency-Key | PASS |
| WARN-1 | `build_error_envelope` imported in Task 3 section (before Task 4) | Import block with comment "R4 WARN-1 fix: build_error_envelope is FIRST used in this Task 3 route" added at top of Task 3 implementation section | PASS |
| WARN-2 | `transition_investigation_status` and `trigger_graph_run` signatures: `user` before `db` | Both route handlers now declare `user: CurrentUser = Depends(require_role(...))` before `db: Session = Depends(get_db)` | PASS |

---

## Verdict

**NO-GO**

---

## Summary

- R4 BLOCK-1 fully resolved: all hold-release POST calls include `Idempotency-Key` header via `_idem()` helper.
- R4 WARN-1 fully resolved: `build_error_envelope` imported at Task 3 section, before first use.
- R4 WARN-2 fully resolved: both route signatures show `user → db` ordering.
- All regression checklist items pass: `payment.hold_released` event name, data-driven `TRANSITION_REQUIRED_FIELDS`, A3 auto-open gate, graph computation pipeline, route-level `build_error_envelope`, header-only hold release idempotency, dep order, Task 5 detector docstring.
- New blocker found (BLOCK-1): both old-DELETE-route tests assert `405 Method Not Allowed`, but after Plan A3 removes `DELETE /holds/{hold_id}`, FastAPI returns `404` — not `405`.

---

## Findings

**BLOCK-1:** `test_hold_release_endpoint.py:test_old_delete_route_is_gone` (plan line ~1332-1337) and `test_create_app_a3_bindings.py:test_old_delete_hold_route_gone` (plan line ~2995-2998)

Problem: Both tests assert `resp.status_code == 405`. FastAPI returns `405 Method Not Allowed` only when the **path** is registered with a different method. After Task 4b Step 1 removes `@router.delete("/holds/{hold_id}")`, no route exists at that path template at all (only `POST /holds/{hold_id}/release` exists, which has a distinct path). A request to `DELETE /holds/{hold_id}` will match no path and FastAPI will return `404 Not Found`, not `405`.

The existing live router (`modules/reclaimrx/src/api/router.py`) was checked: it has `POST /holds`, `GET /holds`, and the old `DELETE /holds/{hold_id}`. Once the DELETE is removed and only `POST /holds/{hold_id}/release` is added, the path `/holds/{hold_id}` is gone.

Fix required: Change both old-DELETE assertions to `assert resp.status_code == 404`. Update comments accordingly.

**PASS-1:** R4 BLOCK-1 fully verified. All 13 hold-release POSTs pass `headers=_idem(hold_id, actor)` or inline `headers={"Idempotency-Key": ...}`. The `_idem()` helper generates per-test unique keys. `test_idempotency_case_b_different_reason` uses `:retry` suffix on second call — correctly bypasses idempotency replay to reach Case B 409 business logic.

**PASS-2:** R4 WARN-1 fully verified. `from src.api.errors import build_error_envelope` import appears at Task 3 section before any route code.

**PASS-3:** R4 WARN-2 fully verified. Both signatures show `user → db`.

**PASS-4:** Regression scan clean. `payment.hold_released` confirmed (no `fwa.hold_released` or `hold.released` variants). `TRANSITION_REQUIRED_FIELDS` is `dict[tuple[str,str], frozenset[str]]`. `_A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})`. `_run_graph_computation` queries `FlaggedClaim`, aggregates via `defaultdict`, builds `GraphEdge` list. Route handlers use `build_error_envelope()`. `HoldReleaseRequest` has no `idempotency_key` body field. `release_hold_v2` dep order: `user → tenant_check → mfa → idempotency_key Header → db`. Task 5 docstring states "TWO A3 pattern detectors" with explicit B11 deferral for `reset_evasion` and `threshold_oscillation`.

**PASS-5:** Deep adversarial scan items A, B, C, E, F all correct:
- Case B logic for different actor: uid_b's different key bypasses idempotency replay, hits service with already-released hold, different actor → 409.
- Case B different-reason: `:retry` suffix key correctly reaches business-logic 409 branch.
- No HTTP idempotency middleware found in plan path that would side-effect on viewer role-check failure.
- `released_at` is set during release and re-attached in 409 envelope.
- Case A double-release logic works at service layer without middleware (service checks hold.status == "released" and same fields → Case A → 200 with `idempotent_replay=True`).

---

## Recommendation

Patch the two stale `assert resp.status_code == 405` assertions to `assert resp.status_code == 404` (one in `test_hold_release_endpoint.py`, one in `test_create_app_a3_bindings.py`). Update the associated comments. Then run a narrow R6 scoped to that single assertion change only.
