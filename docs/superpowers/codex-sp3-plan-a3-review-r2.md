# SP-3 Plan A3 — Adversarial Re-Review R2

**Reviewer:** Codex adversarial subagent
**Date:** 2026-05-19
**Plan:** docs/superpowers/plans/2026-05-18-sp3-plan-a3-state-machine-hold-graph.md (post-R1 revision)
**R1 source:** docs/superpowers/codex-sp3-plan-a3-review-r1.md

---

## R1 Resolution Verification

| # | Concern | Severity | Plan ref | Evidence | Fix required |
|---|---------|----------|----------|----------|--------------|
| R1.BLOCK1a | TRANSITION_REQUIRED_FIELDS dict defined in constants.py | PASS | Task 2, Constants section | Plan defines `TRANSITION_REQUIRED_FIELDS: dict[tuple[str,str], frozenset[str]]` keyed on (from_state, to_state) with frozenset values | None |
| R1.BLOCK1b | closed_false_positive arc enforces outcome_label | PASS | Task 2, validate_transition section | `outcome_label` in frozenset for closed_false_positive arcs; loop raises MISSING_REQUIRED_FIELD if absent | None |
| R1.BLOCK1c | closed_no_action arc enforces outcome_label | PASS | Task 2, validate_transition section | Same data-driven loop covers closed_no_action; frozenset includes outcome_label | None |
| R1.BLOCK1d | validate_transition() is data-driven | PASS | Task 2, pseudocode | `for field in TRANSITION_REQUIRED_FIELDS.get((from_state, to_state), frozenset()): if field not in payload: raise ...` | None |
| R1.BLOCK1e | Test: closed_false_positive missing outcome_label -> MISSING_REQUIRED_FIELD | PASS | Task 2, Tests section | `test_closed_false_positive_missing_outcome_label` listed with assert on MISSING_REQUIRED_FIELD | None |
| R1.BLOCK1f | Test: closed_no_action missing outcome_label -> MISSING_REQUIRED_FIELD | PASS | Task 2, Tests section | `test_closed_no_action_missing_outcome_label` listed | None |
| R1.BLOCK2a | _run_graph_computation queries FlaggedClaim (tenant + lookback window) | PASS | Task 6, _run_graph_computation section | ORM query filters by tenant_id and created_at >= cutoff | None |
| R1.BLOCK2b | Aggregates into GraphEdge with summed claim_count + total_amount | PASS | Task 6, edge aggregation section | GROUP BY (pharmacy_npi, prescriber_npi, member_id) with SUM(claim_count) and SUM(total_amount) | None |
| R1.BLOCK2c | Calls analyzer.build_graph(edges) and analyzer.detect_communities(G) | PASS | Task 6, computation section | Both calls explicit: G = analyzer.build_graph(edges); communities = analyzer.detect_communities(G) | None |
| R1.BLOCK2d | Translates CommunityResult to ring dicts with Decimal density_score, capped entity_refs | PASS | Task 6, ring translation section | density_score=Decimal(str(c.density)), node_count, edge_count, entity_refs=_build_entity_refs(c)[:500] | None |
| R1.BLOCK2e | Returns {rings, investigations, records} dict | PASS | Task 6, return contract section | Exact return dict shape specified in plan | None |
| R1.BLOCK2f | Integration test without patch.object on _run_graph_computation | PASS | Task 6, Tests section | test_graph_job_real_computation.py named with explicit note: no patch.object on _run_graph_computation | None |
| R1.BLOCK2g | At least 4 tests (dense ring, empty, NULL, duplicate) | PASS | Task 6, Tests section | All 4 named: test_dense_ring_detected, test_empty_fixture_returns_empty_rings, test_null_npi_rows_excluded, test_duplicate_edge_aggregation | None |
| R1.CONCERN5 | Scope note defers reset_evasion + threshold_oscillation to B11 | PASS | Task 5, Scope note | Note present at top of Task 5: B11 backlog: reset_evasion, threshold_oscillation | See N7 |
| R1.CONCERN8a | Task 8 split into 8a (write tests) | PASS | Task 8, sub-task 8a | 8a: Write failing tests for hold release and accumulator integration | None |
| R1.CONCERN8b | Task 8 split into 8b (wire/verify) | PASS | Task 8, sub-task 8b | 8b: Wire hold release + accumulator service; run tests until all pass | None |
| R1.CONCERN8c | Task 8 split into 8c (coverage gate) with FAIL->wire->PASS cycle | PASS | Task 8, sub-task 8c | 8c: Coverage gate with explicit RED-wire-GREEN cycle stated | None |

---

## New Issue Check

| # | Issue | Severity | Plan ref | Evidence | Fix required |
|---|-------|----------|----------|----------|--------------|
| N1 | _build_entity_refs caps at 500 per spec 5.5 #13 | PASS | Task 6, ring translation | entity_refs=_build_entity_refs(c)[:500] slice explicit | None |
| N2 | Edge aggregation key is exact triple (pharmacy_npi, prescriber_npi, member_id) | PASS | Task 6, edge aggregation | GROUP BY exact triple confirmed | None |
| N3 | WHERE filter excludes NULL pharmacy_npi/prescriber_npi/member_id rows | PASS | Task 6, edge aggregation | WHERE pharmacy_npi IS NOT NULL AND prescriber_npi IS NOT NULL AND member_id IS NOT NULL | None |
| N4 | TRANSITION_REQUIRED_FIELDS values use frozenset | PASS | Task 2, Constants | frozenset specified for all value sets | None |
| N5 | TestTransitionRequiredFieldsTable class with >=4 tests | PASS | Task 2, Tests | class TestTransitionRequiredFieldsTable with 4 named tests listed | None |
| N6 | All event_type values use fwa. prefix | PASS | Task 3, Events | fwa.investigation_state_changed, fwa.hold_released, fwa.graph_rings_detected — no payment.* prefix | None |
| N7 | Task 5 investigation-opening branch silently includes reset_evasion rows despite B11 deferral | CONCERN | Task 5, investigation opening | Scope note defers the detector but investigation-opening WHERE does not exclude pattern_type IN (reset_evasion, threshold_oscillation); existing FlaggedClaim rows with those labels would be caught by A3 logic | Add AND pattern_type NOT IN (reset_evasion, threshold_oscillation) to WHERE clause, or add explicit inclusion rationale note in Task 5 |

---

## Verdict

**GO-WITH-CHANGES**

---

## Summary

- **R1 BLOCKs resolved:** TRANSITION_REQUIRED_FIELDS is now a data-driven dict with frozenset values; validate_transition() loops over it; all required-field tests named. _run_graph_computation is no longer a stub — it queries FlaggedClaim, aggregates GraphEdge, calls FraudNetworkAnalyzer, and the integration test explicitly prohibits mocking the computation path.
- **R1 CONCERNs resolved:** Task 5 has explicit B11 backlog deferral note; Task 8 is split into 8a/8b/8c with RED-GREEN TDD cycle.
- **N1-N6 all pass:** entity_refs cap, edge aggregation triple, NULL filter, frozenset immutability, test class, event prefix all confirmed in plan text.
- **N7 CONCERN:** Task 5 investigation-opening branch does not exclude reset_evasion and threshold_oscillation pattern_type rows, inconsistent with the B11 deferral scope note. Logic gap, not a blocker, but must be explicitly resolved before implementation starts.

---

## Recommendation

The plan is approved to proceed with one required fix: before any Task 5 code is written, the implementation author must add a WHERE clause filter excluding pattern_type IN (reset_evasion, threshold_oscillation) from the investigation-opening query — or add an explicit numbered note stating that existing FlaggedClaim rows with those labels are intentionally included by A3 even though their generating detectors are deferred to B11. This fix must appear as a numbered note in Task 5 before implementation begins. All other tasks (1-4, 6-8) may proceed in parallel as planned.
