# SP-3 Plan A3 — Adversarial Re-Review R6

**Reviewer:** Codex adversarial subagent (via /codex consult)
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md (post-R5 revision)
**R5 source:** docs/superpowers/codex-sp3-plan-a3-review-r5.md
**Tokens used:** 415,692

---

## R5 Fix Verification

| Item | Check | Evidence | Status |
|------|-------|----------|--------|
| BLOCK-1 | Both old-DELETE tests assert `404` (not `405`) | `test_old_delete_route_is_gone` asserts `resp.status_code == 404` with R5 fix comment; `test_old_delete_hold_route_gone` asserts `resp.status_code == 404` with same rationale | PASS |
| BLOCK-1 | Acceptance checklist says "404 on call (path is unregistered; FastAPI returns 405 only on method mismatch at a registered path)" | Checklist bullet updated at plan line ~3071 | PASS |

---

## Verdict

**GO-WITH-CHANGES**

---

## Summary

- R5 BLOCK-1 is fixed: both old `DELETE /holds/{hold_id}` tests now assert `404`, which is correct after the path is unregistered.
- All 11 listed regression items pass against the current A3 plan.
- One remaining coverage warning: Task 8 registration tests for transition and hold-release routes can still pass if those routes are missing, because missing routes also return `404`.

---

## Findings

**PASS-1:** Old DELETE tests now assert `404`, not `405`. Comment correctly explains FastAPI path-registration semantics.

**PASS-2:** `event_type="payment.hold_released"` is preserved everywhere. No `fwa.hold_released` or `hold.released` variants found.

**PASS-3:** All hold-release POST test calls include `Idempotency-Key` via `_idem()` helper or inline `{"Idempotency-Key": ...}` headers. The `idempotency_case_b_different_reason` test uses `:retry` suffix on the second call to bypass replay and reach the 409 branch.

**PASS-4:** `build_error_envelope` imported in Task 3 implementation section (before Task 4), with R4 WARN-1 fix comment.

**PASS-5:** All three route signatures declare `user` before `db`: `transition_investigation_status`, `release_hold_v2`, `trigger_graph_run`.

**PASS-6:** `TRANSITION_REQUIRED_FIELDS` is a data-driven `dict[tuple[str, str], frozenset[str]]` with 15 arcs. No if/elif chain.

**PASS-7:** `_A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})` is present and used as the gate for auto-opening investigations.

**PASS-8:** `_run_graph_computation` queries `FlaggedClaim` with tenant/date/NPI filters, aggregates via `defaultdict` into `GraphEdge` list, then calls `FraudNetworkAnalyzer.build_graph` + `detect_communities`.

**PASS-9:** Route handlers use `build_error_envelope()`; service-layer raw `{"error": {...}}` dicts for 409/422 are rebuilt at the route layer via `build_error_envelope()` before `raise HTTPException`.

**PASS-10:** `HoldReleaseRequest` body has no `idempotency_key` field. Header-only contract via `idempotency_key: str = Header(..., alias="Idempotency-Key")`.

**PASS-11:** Task 5 test docstring explicitly states two A3 pattern detectors (`sudden_spike`, `multi_payer_convergence`) and defers `reset_evasion` / `threshold_oscillation` to B11.

**PASS-12:** `_build_entity_refs` returns `refs[:500]` — capped at 500 per spec §5.5 #13.

**WARN-1:** Task 8 route-registration tests for transitions and hold-release routes assert only `resp.status_code == 404` on a not-found probe. A missing route also returns `404` — these tests cannot distinguish "route registered but entity missing" from "route not registered at all". Strengthen them by also asserting the A3 error envelope shape, e.g.:
```python
assert resp.json()["error"]["code"] == "NOT_FOUND"
```
This ensures the route handler (not the FastAPI default 404 page) produced the response.

---

## Recommendation

Patch Task 8 `test_transitions_endpoint_registered` and `test_hold_release_endpoint_registered` to add `assert resp.json()["error"]["code"] == "NOT_FOUND"` alongside the existing `assert resp.status_code == 404`. This closes the ambiguity between a registered route returning 404 and an unregistered path returning 404. Once patched, the plan is GO.
