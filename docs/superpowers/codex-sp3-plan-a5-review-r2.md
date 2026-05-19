# Codex Adversarial Re-review R2 — SP-3 Plan A5

> Reviewed: 2026-05-19  
> Reviewer: Codex CLI (adversarial R2)  
> Inputs: plan A5 (updated post-R1), R1 verdict (NO-GO 6 BLOCKs), spec lock, audit para5, reference pattern, tsconfig, event-bus rule, surgical-changes rule

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence | Fix |
|---|---|---|---|---|---|
| BLOCK 2 | Zod coverage matrix row #5 maps non-spec endpoint | BLOCKER | Plan lines 520-543; spec para5.5 lines 294-312 | PARTIAL. Plan defines SPEC_55_ENDPOINT_COVERAGE and _Assert18Endpoints (lines 520 543) and adds six named schemas (lines 454-510). Matrix row #5 maps GET /investigations/{id}/ml-scores while spec endpoint #5 is GET /api/v1/reclaimrx/rule-firings. Real impl agrees with spec (lines 868-870) so the matrix is not a valid 1:1 spec coverage table. | Replace row #5 with /rule-firings and RuleFiringListResponseSchema. |
| BLOCK 3 | DecimalStringSchema regex accepts negatives | OK | Plan line 140 | RESOLVED. Regex has optional leading minus: /^-?d+(.d+)?$/. | None. |
| BLOCK 8 | Event name matches spec lock payment.hold_released | OK | Plan lines 58 105 1838 1850; spec lines 56 620 623 638 | RESOLVED. Plan creates docs/api-contracts/events/payment.hold_released.md with event_type: payment.hold_released (line 1850). No fwa.hold_released in implementation text. | Optional: remove fwa.* parenthetical at lines 58/105. |
| BLOCK 9 | Contract test branch coverage | MAJOR | Plan lines 1261 1502 1532 1545 1556; impl line 810 | PARTIAL. All four branch names present. But authedFetch (line 810) has no catch/wrap so a fetch rejection is a raw TypeError not { code: NETWORK_ERROR }. GET parse-failure loop covers only zero-arg list endpoints not detail paths. | Add network-error catch/wrap in authedFetch or align test expectation. Extend GET parse-failure loop to cover detail paths with fixture IDs. |
| BLOCK 10 | Empty-state pages use existing component | OK | Plan lines 95-101 1806-1815; tsconfig; component on disk | RESOLVED. Pages import ComingSoonPage from @/components/ui/coming-soon-page (line 1806) and map title/description/phase props. Alias and component verified on disk. | None. |
| BLOCK 12 | TypeScript strict invariants | OK | Plan lines 142-151 548-550 | RESOLVED for R1 invariants. InvestigationStatusSchema defined and exported once. Invariant block forbids Record<string unknown> z.any() @ts-ignore as any (lines 548-550). Those patterns appear only in invariant text. | None for R1. See NEW-4 for broader strict-union gap. |
| NEW-1 | Dedicated response schemas not wired into client and real impl | BLOCKER | Plan lines 619 621 623 844-863; schemas lines 454-510 | Plan adds six dedicated response schemas but client still returns Promise<Investigation> for getInvestigation/transitionInvestigation and Promise<{created:true}> for addInvestigationNote. Real impl uses InvestigationSchema for endpoints 2-3 and inline {created:true} for endpoint 4. Dedicated schemas are dead code. | Wire InvestigationDetailResponseSchema InvestigationTransitionResponseSchema and InvestigationNoteResponseSchema through client/real/mock/tests for endpoints 2 3 4. |
| NEW-2 | All 6 new portal page paths exist as A5 deliverables | OK | Plan lines 41-46 1791-1796; spec para6 line 341 | RESOLVED. Plan lists all six: dashboard holds fraud-rings graph-runs thresholds accumulator-anomalies. | None. |
| NEW-3 | Surgical changes: existing directories pages not modified | OK | Plan lines 54 1785; .claude/rules/surgical-changes.md | RESOLVED. Plan states DO NOT replace existing investigations pages and Do NOT touch existing pages. Directory pages absent from deliverables list. | None. |
| NEW-4 | InvestigationListParams uses broad string instead of explicit unions | MAJOR | Plan lines 606-610; spec para5.4 | Plan defines status?: string; severity?: string; source?: string (lines 606-610) while these are explicit enum schemas in types.ts (lines 142-162). Violates plan own strict-TypeScript invariant. | Type status as InvestigationStatus severity and source as their inferred union types from types.ts. |
| NEW-5 | Mock fixtures use NPI 8084009009 and avoid PHI fields | OK | Plan lines 1059 1095; spec para9.4 line 544 | RESOLVED. entity_id: 8084009009 with Luhn-valid comment. No PHI fields in fixtures. | None. |
| NEW-6 | Mock fixture determinism: released_at uses new Date() | MINOR | Plan line 1163 | releaseHold mock sets released_at: new Date().toISOString() (line 1163). Non-deterministic value breaks snapshot tests. | Replace with a fixed ISO timestamp constant. |
| NEW-7 | Manifest update includes reclaimrx module env var and health endpoint | OK | Plan lines 60 1651 1757-1774 | RESOLVED. Adds reclaimrx to modules RECLAIMRX_URL to env and http://reclaimrx:8007/health to health checks. | None. |
| NEW-8 | No invented hooks in portal pages | OK | Plan lines 1806-1815 | RESOLVED. Empty-state pages import only ComingSoonPage with three props. No invented hook. Contract package exports client factories via index (lines 1593-1619). | None. |

---

## Verdict

**NO-GO**

---

## Summary

- **RESOLVED (4/6 R1 BLOCKs):** BLOCK 3 BLOCK 8 BLOCK 10 BLOCK 12 are fully resolved against R1 requirements.
- **Still BLOCKING - BLOCK 2:** Row #5 maps /investigations/{id}/ml-scores instead of spec endpoint #5 /rule-firings. The real impl section in the same plan correctly uses /rule-firings making the matrix internally inconsistent with both spec and implementation.
- **Still PARTIAL - BLOCK 9:** All four required test branch names present but authedFetch has no network-error catch/wrap (raw TypeError != {code:NETWORK_ERROR}) and GET parse-failure loop omits detail paths needing fixture IDs.
- **New BLOCKER - NEW-1:** Six dedicated response schemas defined but not wired into ReclaimRxClient or real.ts for endpoints 2 3 4. Client and real impl use narrower base schemas - the new schemas are dead code as written.
- **New MAJOR - NEW-4:** InvestigationListParams.status/severity/source typed as broad string instead of explicit enum unions already defined in types.ts violating plan own strict-TypeScript invariant.

---

## Recommendation

Do not implement from this A5 draft as written. Four of six original BLOCKs are resolved - a clear improvement from R1 - but two structural BLOCKs remain and two new issues were introduced in the revision. All four required fixes are mechanical: (1) correct endpoint coverage matrix row #5 to /rule-firings; (2) wire dedicated response schemas through client/real/mock for endpoints 2-4; (3) add authedFetch network-error wrapping or align the test expectation to the actual thrown error type; (4) tighten InvestigationListParams to use explicit enum unions. A targeted A5-R3 pass addressing only these four points should achieve GO.
