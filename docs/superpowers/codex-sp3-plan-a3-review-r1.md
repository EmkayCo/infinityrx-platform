# Codex Adversarial Review — SP-3 Plan A3 R1

**Date:** 2026-05-18  
**Plan:** `docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md`  
**Audit ground truth:** `waves/B10/SP-3-audit-deep.md`  
**Prior review:** `docs/superpowers/codex-sp3-plan-a-review-r1.md` (NO-GO on original Plan A)  
**Spec:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`  
**Model:** codex (OpenAI frontier agentic, `model_reasoning_effort="medium"`)  
**Session:** `019e3e54-44b9-75b1-ad4c-3c54f54862a5`  
**Tokens:** 894,745

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence | Fix |
|---|---|---|---|---|---|
| 1 | State machine map is complete, but required-field enforcement is not spec-exact | **BLOCK** | Plan A3:281–306, 410–432 | Map matches spec §5.5.1 lines 318–331. But `closed_false_positive`, `closed_no_action`, and `escalated → closed_*` allow missing `outcome_label`; plan comment says optional at lines 421–432. Spec requires outcome labels for all closed states. Also `TRANSITION_REQUIRED_FIELDS` is promised/imported at lines 69 and 82–85 but never defined in Task 1b implementation. | Define `TRANSITION_REQUIRED_FIELDS`; require `outcome_label` for every `closed_*` transition; require `recovered_amount` only for `closed_confirmed`; add missing tests for the label-required cases. |
| 2 | Old hold DELETE route removal is correctly planned | PASS | Plan A3:1203, 1358, 1512 | Tests assert old `DELETE /holds/{id}` returns 405; plan explicitly deletes old route and adds `POST /holds/{hold_id}/release`. Audit confirms old DELETE at router.py line 475. | Keep. |
| 3 | Hold release idempotency covers same actor, different reason, different actor — all 3 cases | PASS | Plan A3:1252–1305, 1377–1435 | Case A (200 replay) exists. Case B same-actor different-reason (409) at lines 1292–1305. Case B different-actor (409) at lines 1270–1290. Case C expired/non-active (422) at lines 1307–1331. Uses `PaymentHold.status` with active/released/other dispatch. | Keep. All 3 spec §7.2 idempotency cases are present. |
| 4 | Correct hold amount field — `amount_threshold` not `hold_amount` | PASS | Plan A3:1190, 1454–1455, 2543 | Uses `amount_threshold` throughout; no `hold_amount` reference in A3 code. Audit §1:145 confirms `amount_threshold` is the correct column. Acceptance criteria grep explicitly checks this. | Keep. |
| 5 | Accumulator event name matches spec; 4 pattern detectors incomplete | CONCERN | Plan A3:19, 1704–1746, 1865–1871 | Spec §5.3 and §11.5 confirm consumed event is `accumulator.updated` — plan uses `accumulator.updated`. Good. But implementation only detects `sudden_spike` and `multi_payer_convergence` in `_detect_patterns()`; `reset_evasion` and `threshold_oscillation` are listed in spec as AccumulatorAnomaly pattern types but have no detectors or tests in A3. | Keep event name. Explicitly scope A3 as wiring `sudden_spike` + `multi_payer_convergence` only, and create follow-on task for the other two patterns; OR add `reset_evasion` + `threshold_oscillation` detectors with tests before marking A3 complete. |
| 6 | Graph advisory lock — `zlib.crc32` used correctly | PASS | Plan A3:2064–2070, 2211–2215 | Uses `zlib.crc32(f"graph_run:{tenant_id}".encode()) & 0x7FFFFFFF` for lock key. SQL call uses `text("SELECT pg_try_advisory_xact_lock(:key)")`. No Python `hash()`. Audit §9:546–554 confirms this is the correct fix. | Keep. |
| 7 | CurrentUser access — `user.has_role()` used throughout, not `user.get()` | PASS | Plan A3:1033–1036, 1535, 2542 | No `user.get` calls in A3 code. All role checks use `user.has_role("reclaimrx.admin")` and `require_role(...)`. Acceptance criteria grep explicitly checks for absence of `user.get`. Audit §3:258 confirms `CurrentUser` is a dataclass. | Keep. R1 BLOCK 6 fully resolved. |
| 8 | TDD discipline mostly present; Task 8 missing explicit fail/pass cycle | CONCERN | Plan A3:2447–2509 | Tasks 1–7 each have explicit `pytest ... -x → expect FAIL`, implement, `pytest ... -x → expect ALL PASS` pattern. Task 8 adds `test_create_app_a3_bindings.py` and coverage run but lacks explicit run-FAIL step before implementation and explicit run-PASS step after wiring. | Add: `pytest modules/reclaimrx/tests/integration/test_create_app_a3_bindings.py -x → expect FAIL (routes not registered)`, implement/wire, rerun `→ expect ALL PASS`. |
| 9 | No cross-plan schema duplication | PASS | Plan A3 overall | No `class GraphRun`, `class FraudRing`, `class AccumulatorAnomaly`, `class OutboxEvent`, or `op.create_table` in A3. Tables are imported from `src.models.tables` (Plan A1). Pre-task checklist requires Plan A1 to be merged before A3 runs. | Keep. |
| 10 | EventEnvelope field names corrected | PASS | Plan A3:1456–1479, 2176–2203 | Uses `event_type=`, `timestamp` auto-set (not passed), no `emitted_at`. Correct `tenant_id` as `uuid.UUID` (not str). R1 BLOCK 4 resolved. | Keep. |
| 11 | Graph job `_run_graph_computation` returns empty rings without real graph computation | **BLOCK** | Plan A3:2235–2244 | `_load_tenant_graph_data()` returns `{"nodes": 0, "edges": 0}` always. `_run_graph_computation()` imports `FraudNetworkAnalyzer` but immediately returns `{"rings": [], "investigations": 0, "records": 0}` without calling `build_graph()` or `detect_communities()`. This means the graph job is still a stub — it writes `GraphRun` rows and publishes outbox events, but never detects any fraud rings. Tests mock both internals, so test coverage hides the gap. | Implement `_load_tenant_graph_data()` with a real tenant-scoped claim query (90-day window); call `FraudNetworkAnalyzer.build_graph()` + `detect_communities()` in `_run_graph_computation()`; write `FraudRing` rows for detected communities above density threshold; add at least one integration test with a fixture that produces real ring output (not fully mocked). |

---

## Verdict: NO-GO

**What A3 fixes from R1 (original Plan A review):**
- Hold route shape: DELETE removed, POST /holds/{id}/release added with correct body
- `amount_threshold` field: no `hold_amount` anywhere
- `CurrentUser.has_role()`: no `user.get()` anywhere
- EventEnvelope fields: `event_type`, not `type`; no `emitted_at`
- Advisory lock: `zlib.crc32` deterministic key, not `hash()`
- All 3 §7.2 idempotency cases: present and tested (Case A same-actor/same-reason 200, Case B different-actor OR different-reason 409, Case C non-active/expired 422)
- Cross-plan schema isolation: no re-definitions, all A1 tables imported only

**What still blocks GO:**

**BLOCK 1 — State machine required fields:** `TRANSITION_REQUIRED_FIELDS` is imported by the test (line 82–85) but never defined in the `constants.py` implementation (Task 1b, lines 271–465). The `validate_transition()` function does not enforce `outcome_label` on `closed_false_positive` and `closed_no_action` transitions — the comment says "optional" but spec §5.5.1 requires outcome label for all closed states. Tests will fail at import with `ImportError: cannot import name 'TRANSITION_REQUIRED_FIELDS'`.

**BLOCK 2 — Graph job is still a stub:** `_run_graph_computation()` returns empty results without calling the `FraudNetworkAnalyzer`. The task is titled "Graph job real implementation" but the implementation delegates to a method that returns `{"rings": [], "investigations": 0, "records": 0}` unconditionally. The unit tests all mock `_run_graph_computation`, so they pass without validating any actual graph computation. This is the same failure mode as the original stub, just wrapped in a more complex scaffold.

**CONCERN 5 — Accumulator patterns incomplete:** Acceptable if explicitly scoped to two patterns in A3, but must be stated clearly. Currently not noted as partial.

**CONCERN 8 — Task 8 TDD steps incomplete:** Minor, fixable in plan text before dispatch.

---

## Minimum changes to reach GO-WITH-CHANGES

1. Define `TRANSITION_REQUIRED_FIELDS` dict in `constants.py` Task 1b (even as an empty dict that maps arc tuples to required field lists — it must be importable).
2. Enforce `outcome_label` in `validate_transition()` for `closed_false_positive` and `closed_no_action` (currently only `closed_confirmed` enforces it fully).
3. Add tests for the missing required-field enforcement on the two other closed states.
4. In `_run_graph_computation()`, call `FraudNetworkAnalyzer` for real — at minimum load flagged claims, build the graph, run community detection, and return actual `FraudRing` data. At minimum one test with real (non-mocked) fixture output.
5. Add explicit TDD fail/pass steps for Task 8's `test_create_app_a3_bindings.py`.
6. Explicitly document in Task 5 scope note that `reset_evasion` and `threshold_oscillation` are deferred to a follow-on task.
