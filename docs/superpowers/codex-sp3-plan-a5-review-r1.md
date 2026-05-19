# Codex Adversarial Review — SP-3 Plan A5
**Date:** 2026-05-19
**Branch tip:** 8559dd35
**Reviewer:** Codex (adversarial-review mode, effort=high, thread=019e3e9b-0b7e-73e0-a305-c1ff1d239f9c)

---

## Verdict Table

| # | Concern | Severity | Plan ref | Evidence | Fix |
|---|---------|----------|----------|----------|-----|
| 1 | Contract layout — flat 4-file (src/impls/reclaimrx/{client,types,real,mock}.ts) | PASS | §3 Deliverables | A5 specifies the correct flat layout matching prescriber-directory; no nested clients/schemas/impls/cache references found in the plan | — |
| 2 | Zod schemas cover all 18 endpoint shapes from A4 | BLOCK | §4.1 types.ts | A5 defines schemas for ~12 shapes. Missing: investigation-list response, hold-detail response, audit-trail pagination, 2 bulk-action response shapes, and flag-override response — 6 of 18 shapes absent | Add the 6 missing Zod schemas before implementation begins |
| 3 | Decimal amounts as z.string() with correct regex | BLOCK | §4.1 types.ts | A5 uses /^d+(.d+)?$/ — missing optional leading minus sign. Holds and adjustments carry negative balances; valid server responses will be rejected at runtime | Change to /^-?d+(.d+)?$/ across all Decimal fields |
| 4 | authedFetch + unwrap pattern matches prescriber-directory real.ts verbatim | CONCERN | §4.2 real.ts | A5 describes the pattern but pseudocode shows a slightly different error-unwrap path vs prescriber-directory real.ts. Drift risk at implementation time | Add explicit note to copy error branch verbatim from packages/contract/src/impls/prescriber-directory/real.ts |
| 5 | Mock returns realistic fixtures (NPI 8084009009); no PHI | PASS | §4.3 mock.ts | A5 explicitly uses NPI 8084009009 per spec §9.4; all member references use fictional IDs (MBR-0001 etc.) with no real names, DOBs, SSNs, or contact data | — |
| 6 | 6 NEW portal pages only — existing 13 in portal/operator/app/directories/ untouched | PASS | §5 Portal scaffold | A5 lists exactly 6 new pages under portal/operator/app/reclaimrx/ and explicitly states existing directories/ pages are not modified | — |
| 7 | Manifest update passes build-manifest validation | CONCERN | §6 Manifest | A5 adds RECLAIMRX_URL and a health key but does not show the exact JSON diff against the manifest schema. The health entry format may not match the nested {url:...} object used in packages/shell/src/_generated/manifest.json | Verify manifest schema from the file before writing the diff |
| 8 | Event contract docs match event-bus.md dot-notation | BLOCK | §7 Event docs | A5 documents claim.flagged and hold.released. The A4 backend registers fwa.claim_flagged and fwa.hold_released per event-bus.md convention. Contract event docs will be wrong on day one | Rename to fwa.claim_flagged and fwa.hold_released matching event-bus.md and A4 backend |
| 9 | Contract tests 100% on auth error + Zod validation branches | BLOCK | §8 Tests | A5 test plan covers happy-path and a single 401 case. Missing: (a) Zod parse failure per endpoint (>=12 cases), (b) 403 tenant mismatch branch, (c) network error branch in authedFetch. testing.md requires 100% on all security-path branches | Add explicit test cases for Zod parse failure per schema, 403 branch, and network error branch |
| 10 | shadcn/ui imports resolve in portal/operator | BLOCK | §5.2 Components | A5 imports from @/components/ui/card, @/components/ui/button, @/components/ui/badge, @/components/ui/table. These paths do not exist in portal/operator. This is the same BLOCK that killed A3 and A4 | Scaffold the missing shadcn components under portal/operator or verify the correct import path from portal/operator/tsconfig.json |
| 11 | No PHI in mock fixtures | PASS | §4.3 mock.ts | Confirmed: all mock fixtures use fictional IDs; no real PHI fields present | — |
| 12 | TypeScript strict mode: no any, explicit unions, no @ts-ignore | BLOCK | §4.1–4.3 | A5 uses Record<string, unknown> as catch-all for metadata fields in 3 schema definitions (implicit any in downstream consumers under strict mode). InvestigationStatus union defined as string in one place and z.enum([...]) in another — inconsistency fails strict type checks | Replace all Record<string, unknown> metadata fields with explicit typed objects; unify InvestigationStatus to a single z.enum exported from types.ts |
| 13 | Mock seedable and deterministic for replay | CONCERN | §4.3 mock.ts | A5 mock uses hardcoded fixture arrays (deterministic) but does not expose a reset() export or seed parameter matching the prescriber-directory mock pattern. Any Date.now() usage will cause CI/local divergence | Add a reset() export and replace any Date.now() calls with a fixed ISO date constant |
| 14 | A5 does not redefine A1-A4 backend artifacts | PASS | §2 Scope | A5 explicitly states it imports backend types exclusively via @infinityrx/contract and does not redeclare service classes, ORM models, or event consumers | — |
| 15 | No invented helpers (non-existent hooks) | CONCERN | §5.3 Components | A5 references useReclaimRxClient() hook. Defined within A5 deliverables (client.ts) but the export chain — client.ts to package index to portal import path — is not made explicit. Portal pages cannot import it without this chain being spelled out | Make the export chain explicit: client.ts to packages/contract/index.ts to portal import path |

---

## Verdict

**NO-GO**

---

## Summary of BLOCKs

- **BLOCK 2 — Incomplete Zod coverage:** 6 of 18 endpoint shapes from A4 are absent from A5 type definitions. The contract layer is incomplete; portal pages will have untyped data for investigation detail, hold detail, audit-trail pagination, and bulk-action responses.

- **BLOCK 3 — Decimal regex excludes negative values:** The regex /^d+(.d+)?$/ rejects negative amounts. Payment holds and adjustments carry negative balances. Every Decimal amount field will silently reject valid server responses at runtime.

- **BLOCK 8 — Event type naming mismatch:** A5 documents claim.flagged and hold.released. The A4 backend registers fwa.claim_flagged and fwa.hold_released per event-bus.md. The contract event docs will be wrong on day one.

- **BLOCK 9 — Incomplete contract test coverage:** Auth/Zod security paths require 100% branch coverage per testing.md. A5 covers one 401 case and happy paths. Missing: Zod parse failure per endpoint (>=12 cases), 403 tenant mismatch branch, network error branch.

- **BLOCK 10 — shadcn/ui import paths do not exist in portal/operator:** @/components/ui/card and siblings are not present in portal/operator. The 6 new pages will not compile. This BLOCK has survived A3, A4, and A5 without resolution.

- **BLOCK 12 — TypeScript strict violations:** Record<string, unknown> metadata fields and dual InvestigationStatus definitions will fail strict mode compilation. These are type errors under strict: true, not style issues.

---

## Recommendation

Plan A5 is a meaningful improvement over A1-A4: it correctly adopts the flat 4-file contract layout, does not invent new directory structures, and respects the surgical-changes rule for existing portal pages. However, six blockers remain — all are concrete mechanical corrections, not architectural redesigns. The shadcn/ui import path problem (BLOCK 10) has now survived A3, A4, and A5 without resolution; the A6 author must start by verifying the actual component import paths in portal/operator before writing any portal page code. The Decimal regex fix (BLOCK 3) is a one-character change. Event type names (BLOCK 8) require coordinating with the A4 event bus registration. Zod completeness (BLOCK 2) requires confirming each of the 18 A4 endpoints has a schema. Test coverage (BLOCK 9) requires enumerating the missing branch test cases explicitly in the plan. TypeScript violations (BLOCK 12) require replacing the two Record<string, unknown> patterns with typed objects. Fix these six items and re-submit as A6.

---

## End-of-message contract

```
STATUS: DONE
REASON: Full adversarial review completed across all 15 checks; 6 BLOCKs found; NO-GO verdict
ATTEMPTED:
  - Read plan, audit ground truth, spec, prior NO-GO verdicts (A1-A4), reference impls, event-bus.md, testing.md, surgical-changes.md
  - Ran targeted rg searches for contract layout, Decimal regex, event names, any/ts-ignore, shadcn imports, portal page listing
  - Produced 15-row verdict table with plan section citations
  - Codex sandbox blocked direct file writes; verdict file written via Claude main thread Node.js
RECOMMENDATION: Address all 6 BLOCKs before submitting A6 — start with shadcn import path verification in portal/operator
EVIDENCE:
  files_created: [docs/superpowers/codex-sp3-plan-a5-review-r1.md]
  files_modified: []
  commit_sha: null
  test_command: null
  test_result: null
  raw_return_archive_path: null
  warnings: [Codex sandbox rejected apply_patch and python writes; file written via Claude main thread Node.js]
```
