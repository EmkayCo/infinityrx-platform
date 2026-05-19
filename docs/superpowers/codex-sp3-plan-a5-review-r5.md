# SP-3 Plan A5 — R5 Adversarial Review

**Model:** gpt-5.5 via codex CLI  
**Session:** 019e401e-2bc3-77d0-a898-efe15df71d1f  
**Tokens used:** 104,822  
**Date:** 2026-05-19

---

## R4 Issue Resolution Status

| ID | Issue | Status | Evidence |
|----|-------|--------|----------|
| NEW-8 (primary) | All 9 threshold-related fields use `NonNegativeDecimalStringSchema` | RESOLVED | `PaymentHoldSchema.amount_threshold` line 288, `MlScoreThresholdsSchema.{open, auto_hold, escalate}` lines 424–426, `ThresholdConfigSchema.{rule_thresholds record-value, graph_density_threshold, accumulator_anomaly_sensitivity}` lines 434–437, `ThresholdUpdateRequestSchema` same fields `.optional()` variants lines 443–446 — all confirmed using `NonNegativeDecimalStringSchema`. |
| NEW-6 | `new Date().toISOString()` inside JSDoc comment only | CONFIRMED NOT-BUG | Both occurrences (lines 1108, 1287) are inside comment blocks explaining what was removed. Actual code uses `MOCK_FIXED_TIMESTAMP = "2026-05-18T00:00:00.000Z"` constant at lines 1111, 1251, 1265, 1292. |
| NEW-7 | `fwa.graph_run_completed` event name spec-locked | CONFIRMED NOT-BUG | Spec line 56 locks this name. Plan event contract doc at line 2038 uses `"fwa.graph_run_completed"` correctly. |

---

## Secondary Checks (R5 scan)

| Check | Result |
|---|---|
| `payment.hold_released` event name preserved | PASS — plan line 1988, event contract doc line 1976 both correct |
| 18-endpoint `SPEC_55_ENDPOINT_COVERAGE` inventory | PASS — rows 1–18 verified; row #5 is `/rule-firings` |
| `DecimalStringSchema` regex | PASS — `/^-?\d+(\.\d+)?$/` at plan line 146 |
| `NonNegativeDecimalStringSchema` regex | PASS — `/^\d+(\.\d+)?$/` at plan line 157 |
| `authedFetch` wraps `fetch` in try/catch returning `RealClientError(code: "NETWORK_ERROR")` | PASS |
| Empty-state pages use `@/components/ui/coming-soon-page` | PASS — component exists at `portal/operator/components/ui/coming-soon-page.tsx`; no shadcn primitives (`card`/`button`/`badge`/`table`) imported |
| Mock fixtures use `MOCK_FIXED_TIMESTAMP` + `MOCK_NOTE_ID` constants | PASS — constants defined at lines 1111–1112 |
| `_Assert18Endpoints` type-level invariant | PASS |

---

## Verdict
**GO-WITH-CHANGES**

---

## Summary

- R4 NEW-8 primary fix is present and complete: all 9 named threshold fields confirmed using `NonNegativeDecimalStringSchema`.
- Regexes are exact: signed `DecimalStringSchema` is `/^-?\d+(\.\d+)?$/`; non-negative schema is `/^\d+(\.\d+)?$/`.
- Spec-locked event names preserved: `payment.hold_released` and `fwa.graph_run_completed`.
- Endpoint inventory has exactly 18 rows; row #5 is `/rule-firings`; `_Assert18Endpoints` invariant present.
- `authedFetch` wraps fetch failures as `RealClientError("NETWORK_ERROR", ...)`.
- Empty-state pages use `@/components/ui/coming-soon-page`; component confirmed extant in portal/operator.
- Mock fixture timestamp/id constants used; `new Date().toISOString()` appears only in comment blocks.
- One new WARN finding: `threshold_snapshot` field still uses signed `DecimalStringSchema`.

---

## Findings

| ID | Severity | Location | Problem | Required Fix |
|----|----------|----------|---------|--------------|
| WARN-1 | WARN | `plan:521` — `InvestigationDetailResponseSchema.threshold_snapshot` | Field uses `z.record(z.string(), DecimalStringSchema).nullable()` (signed schema). Per spec line 153, `threshold_snapshot` is "an immutable copy of relevant threshold values at open time" — these are ratio/score values (0-1 non-negative), identical in domain to the threshold fields fixed in NEW-8. The signed schema silently admits negative threshold values (e.g., `-0.5` for `graph_density_threshold`), which are semantically invalid and can never be produced by the backend. | Change to `z.record(z.string(), NonNegativeDecimalStringSchema).nullable()` at plan line 521. One-line fix; no downstream type changes required since value type remains `string`. |

---

## Recommendation

Apply the one-line `threshold_snapshot` schema fix (plan line 521: `DecimalStringSchema` → `NonNegativeDecimalStringSchema`), then proceed to execution. The R4 NEW-8 named fields validate cleanly. No blockers remain — this WARN is a tightening fix, not a correctness regression.

If WARN-1 is deferred (accepted risk), document it as a known gap in the plan with a TODO pointing to a Plan B cleanup task. Do not leave it silently admitted in the schema.
