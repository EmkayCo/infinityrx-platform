# SP-3 Plan A5 --- R3 Adversarial Review

**Reviewer:** Codex CLI (forwarded via Claude)
**Date:** 2026-05-19
**Inputs:**
- Plan: docs/superpowers/plans/2026-05-18-sp3-plan-a5-contract-frontend.md
- R2 verdict: docs/superpowers/codex-sp3-plan-a5-review-r2.md
- Spec: docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md
- Reference: packages/contract/src/impls/prescriber-directory/{client,types,real,mock}.ts

---

## R2 Resolution Check

| Issue | Status | Evidence |
|---|---|---|
| **BLOCK 2** --- SPEC_55_ENDPOINT_COVERAGE row #5 must be /rule-firings (RuleFiringListResponseSchema), not /investigations/{id}/ml-scores | RESOLVED | Plan SPEC_55_ENDPOINT_COVERAGE matrix row #5 now reads n:5, method:GET, path:/rule-firings, req:null, response:RuleFiringListResponseSchema |
| **BLOCK 9** --- authedFetch try/catch -> NETWORK_ERROR; unwrap -> MALFORMED_RESPONSE; pickClientMethodForPath UUID paths | RESOLVED | Plan shows authedFetch wraps fetch in try/catch emitting RealClientError code=NETWORK_ERROR; unwrap block emits MALFORMED_RESPONSE on bad JSON; pickClientMethodForPath handles /investigations/{id}, /ml-scores/{id}/features, /graph-runs/{run_id}, /fraud-rings/{id} via UUID placeholder regex |
| **NEW-1** --- real.ts uses dedicated schemas for endpoints 2/3/4/12/13 | PARTIAL | real.ts section updated to import and use InvestigationDetailResponseSchema, InvestigationTransitionResponseSchema, InvestigationNoteResponseSchema, GraphRunDetailResponseSchema, FraudRingDetailResponseSchema for those endpoints. However the ReclaimRxClient interface, mock.ts return shapes, and parametrized tests for endpoints 2/3/4 still advertise old base shapes --- dedicated schemas not consistently propagated across all four files. |
| **NEW-4** --- InvestigationListParams.status/severity/source typed as enum unions; RecoveryParams.period/group_by typed unions | RESOLVED | Plan types.ts now shows status:InvestigationStatus, severity:InvestigationSeverity, source:InvestigationSource, period:RecoveryPeriod, group_by:RecoveryGroupBy --- all enum unions, not broad string. |

---

## New Issues Found

| # | Severity | Issue | Location | Fix Required |
|---|---|---|---|---|
| NEW-5 | **BLOCK** | ReclaimRxClient interface and mock.ts still return old base shapes for endpoints 2/3/4 (getInvestigation, transitionInvestigation, addNote). TypeScript will compile but callers that import mock for tests get wrong types, defeating the strict-invariant goal. | Plan section 3.2 client interface + section 3.4 mock.ts | Update interface method return types and mock return objects to match InvestigationDetailResponseSchema / InvestigationTransitionResponseSchema / InvestigationNoteResponseSchema |
| NEW-6 | **BLOCK** | mock.ts still emits released_at: new Date().toISOString() for the hold_released event shape. Spec line 623 locks this field name and the event type to payment.hold_released. The mock must not generate a live timestamp --- use a fixed ISO string to keep tests deterministic. | Plan section 3.4 mock.ts hold_released event stub | Replace new Date().toISOString() with a fixed deterministic ISO string e.g. 2026-01-15T10:00:00.000Z |
| NEW-7 | WARN | Event contract doc section 4 contains residual text reading "use fwa.* prefix, not payment.*" adjacent to the payment.hold_released doc entry. This directly contradicts the spec lock on lines 56 and 623. The body event_type field value payment.hold_released is correct; the adjacent explanatory text must be removed. | Plan section 4 event-contract doc | Delete or correct the contradictory fwa-prefix guidance next to the payment.hold_released entry |
| NEW-8 | WARN | DecimalStringSchema (regex /^-?\d+(\.\d+)?$/) accepts negative values. It is reused for fields that represent non-negative quantities: hold volume, threshold amounts, confidence scores (0-1), and recovery rates. Accepting -1.5 as a valid score or hold amount is a silent business-logic defect. | Plan section 2.1 types.ts DecimalStringSchema | Add a non-negative variant NonNegativeDecimalStringSchema = /^\d+(\.\d+)?$/ and use it for volume/threshold/score/rate fields; keep signed variant only for net-change / delta fields |
| NEW-9 | INFO | SPEC_55_ENDPOINT_COVERAGE has 17 rows in the plan. Spec section 5.5 lists 18 endpoints. The missing entry appears to be PATCH /investigations/{id}/assignments (bulk re-assign). Confirm whether this is out of scope for A5 or accidentally omitted. | Plan section 3.1 SPEC_55_ENDPOINT_COVERAGE | Either add the missing row or add an explicit in-scope comment marking it deferred |

---

## Verdict

**NO-GO**

---

## Summary

R2 BLOCK 2, BLOCK 9, and NEW-4 are fully resolved. NEW-1 is partially resolved: real.ts uses dedicated schemas but the ReclaimRxClient interface and mock.ts still expose old base shapes, so TypeScript consumers of the mock silently receive wrong types --- this is a new BLOCK (NEW-5). mock.ts also still generates a live timestamp for the hold_released event stub (NEW-6, BLOCK), making deterministic testing impossible. Two WARNs (contradictory event-doc prose; unsigned Decimal schema reused on non-negative fields) and one INFO (possible missing 18th endpoint) were found.

## Recommendation

Fix the two new BLOCKs --- NEW-5: propagate dedicated schemas through the ReclaimRxClient interface and mock.ts; NEW-6: replace new Date().toISOString() with a fixed ISO string --- correct the contradictory fwa-prefix prose in the event doc, add a NonNegativeDecimalStringSchema variant, and clarify the 18th endpoint scope, then resubmit for R4.
