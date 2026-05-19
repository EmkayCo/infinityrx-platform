# SP-3 Plan A5 — R4 Adversarial Review

## R3 Issue Resolution Status

| ID | Issue | Status | Evidence |
|----|-------|--------|----------|
| NEW-5 | Dedicated response schemas in client + mock | RESOLVED | Plan-only:  does not exist in this checkout. Plan  returns ,  returns ,  returns ,  returns , and  returns . Mock methods construct detail/transition/note shapes at , , , and return graph/fraud detail aliases at , . |
| NEW-6 | MOCK_FIXED_TIMESTAMP, no new Date() | STILL-OPEN | Plan-only:  does not exist. The plan defines  at  and uses it in method return fields at , , and ; however the requested grep criterion is zero  hits in mock fixtures/method bodies, and the planned mock section still contains  text at  and . |
| NEW-7 | No fwa.* prefix annotations | STILL-OPEN | Plan-only: no reclaimrx contract files exist. The plan still references  at , , , and , titles the doc  at , and sets  to  at . |
| NEW-8 | NonNegativeDecimalStringSchema defined + applied | STILL-OPEN | Plan-only:  is defined at  and applied to rule/ML  at  and ,  at , recovery  at  and , and dashboard , ,  at . But signed  is still applied to non-negative threshold/amount fields:  at ,  at ,  at  and ,  at  and , and  at  and . |

## New Issues Found

| ID | Severity | File / Section | Description | Required Fix |
|----|----------|---------------|-------------|--------------|
| EVENT_TYPE_LOCK | BLOCK |  | The task's event lock requires every  reference in the plan + contract files to equal . The plan still defines a second event contract with  =  and references the  filename at , , , and . | Remove the  event contract from Plan A5 or move it outside the locked event-contract scope so all Plan A5  entries are . |
| DECIMAL_SCHEMA_MISUSE | BLOCK |  |  is documented as signed-capable at , but the plan still applies it to threshold fields that are non-negative by definition: ML thresholds, rule thresholds, graph density threshold, and accumulator anomaly sensitivity. It also applies the signed schema to  at . | Replace those fields with ; reserve  for genuinely signed fields such as adjustments, reversals, deltas, or net-change values. |

## Verdict
**NO-GO**

## Summary
The plan resolves the dedicated client/mock response-shape issue (NEW-5) in the planned reclaimrx files, and the endpoint coverage table now has row #5 as  with exactly 18 rows (plan ). Empty-state page guidance uses  () and explicitly avoids unavailable shadcn primitives (, ). However, two R3 issues remain open under the requested grep/lock criteria:  text remains in the planned mock section, and  remains as an event contract. The decimal split is also incomplete because signed  is still used for non-negative threshold/amount fields — both a carryover from NEW-8 and a new application surface.

## Recommendation
Revise Plan A5 to: (1) remove all  event-contract references from this locked scope, (2) eliminate all  text from the mock code block so the only date source is , and (3) convert all non-negative threshold/amount fields (, ML/rule/graph-density thresholds, accumulator sensitivity) to . Then rerun R5 against the revised plan and the actual reclaimrx contract files once they are committed.
