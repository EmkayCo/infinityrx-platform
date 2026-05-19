# SP-3 Plan A3 — Adversarial Re-Review R3

**Reviewer:** Codex adversarial subagent
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md (post-R2 revision)
**R2 source:** docs/superpowers/codex-sp3-plan-a3-review-r2.md
**Tokens used:** 43,276

---

## R2 N7 Fix Verification

| Item | Check | Evidence | Status |
|------|-------|----------|--------|
| N7a | `_A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})` present | Plan lines 1931-1940: frozenset defined with explicit comment tying it to B11 deferral scope note | PASS |
| N7b | `if anomaly.pattern_type in _A3_AUTO_OPEN_PATTERNS:` membership check present | Plan line 1943: guard wraps `_open_investigation()` call | PASS |

---

## Verdict

**NO-GO**

---

## Summary

- N7 is fixed: `_A3_AUTO_OPEN_PATTERNS = frozenset({"sudden_spike", "multi_payer_convergence"})` is present and investigation opening is gated by `if anomaly.pattern_type in _A3_AUTO_OPEN_PATTERNS:`.
- `payment.hold_released` is preserved (not renamed).
- `TRANSITION_REQUIRED_FIELDS` is data-driven and uses `frozenset` values.
- Graph job is real: queries `FlaggedClaim`, builds `GraphEdge`, calls `FraudNetworkAnalyzer`, caps `entity_refs` at 500.
- Hold release v2 correctly keeps `idempotency_key` header-only with correct dependency order.
- Two blocking regressions remain: closed-state contract mismatch (4 missing states) and inconsistent `build_error_envelope()` usage across route handlers.

---

## Findings

**BLOCK-1:** Task 1, state machine constants/tests — the plan does not cover the requested closed states `closed_unconfirmed`, `closed_recovered`, `closed_duplicate`, or `closed_pending`. It only models `closed_confirmed`, `closed_false_positive`, and `closed_no_action`. If the regression checklist is authoritative, this fails the outcome-label requirement for four closed arcs. Fix by aligning `VALID_STATUS_TRANSITIONS`, `TERMINAL_STATES`, `_OUTCOME_LABEL_FOR_STATE`, `TRANSITION_REQUIRED_FIELDS`, and tests to the spec-locked closed states.

**BLOCK-2:** Task 3, Task 4, Task 7 route snippets — not all inline error dicts use `build_error_envelope()`. `transition_investigation_status()` uses raw `{"error": ...}` dicts, hold release passes raw service error dicts for 409/422, and `trigger_graph_run()` returns a raw `RUN_IN_PROGRESS` error dict. Fix all route-level errors to call `build_error_envelope()` consistently, and update tests accordingly.

**WARN-1:** Task 5 test header says "Tests 4 pattern detectors," but the actual A3 scope and implementation only test/detect two patterns. This is misleading and will confuse future B11 work. Fix the test docstring to say two A3 detectors, with `reset_evasion` and `threshold_oscillation` explicitly deferred.

---

## Recommendation

Do not approve A3 as written. The N7 accumulator auto-open filter is confirmed in place. Before marking the plan executable:
1. Add the four missing closed states (`closed_unconfirmed`, `closed_recovered`, `closed_duplicate`, `closed_pending`) with their outcome-label arcs to the state machine constants and tests (BLOCK-1).
2. Replace every new raw inline error dict in route handlers with `build_error_envelope()` calls (BLOCK-2).
3. Fix the Task 5 test docstring to accurately state two A3 detectors (WARN-1).

Once those three items are addressed, plan is ready for R4 verification (or GO if author self-certifies fixes against this checklist).
