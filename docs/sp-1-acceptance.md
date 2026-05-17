# SP-1 Acceptance Document

**Date:** 2026-05-17
**Branch:** wave/B10-w5-sp1-paysync
**Final Task 6 commit:** 7326d268
**Author:** Mike K

---

## Summary

SP-1 (PaySync Operator Portal) delivered the full financial-processing module
for the InfinityRx operator portal across 5 plans and ~93 SP-1-tagged commits.
The module covers upload ingestion through payment reconciliation, with a
complete RBAC model, 11 inbox card kinds, 13 surfaces, hash-chain journal
ledger, and contract layer.

---

## Deliverables by Plan

### Plan A -- Module Scaffold + Inbox Spine
- `@infinityrx/module-paysync` package scaffolded (SD-4 shape)
- `module.config.ts` with RBAC matrix and 13 route-surface mappings
- Inbox spine: `InboxItemKind` union (11 kinds), `INBOX_KIND_ROLE` map,
  `ItemRegistry`, `useInboxItems`, `InboxQueue`
- Primitives: `MoneyDisplay`, `MoneyInput`, `RbacGate`, `ProvenanceBreadcrumb`,
  `HashChainBadge`
- 13 surface stubs registered in `src/index.ts`
- `operator-dev.yml` manifest wired with paysync module
- `dev-only/RoleSwitcherChip` isolated behind `NODE_ENV` guard in
  `paysyncComposition.qa`

### Plan B -- Upload Resource + Cycles Surface (R3)
- `modules/billing` Upload ORM + migration 0011 (`billing.uploads`,
  `claim_records.upload_id`, `claim_records.amount_billed Numeric(14,4)`)
- Upload service: CSV/Excel parse, SHA-256 content-address dedup, row-error
  collection, `paysync.upload.parsed` event publication (async EventEnvelope)
- 5 upload router endpoints (RBAC-gated, PHI-audited)
- Cycles router backed by `PaymentBatch`
- `UploadsClient`, `InboxClient`, `CyclesClient` contract interfaces + RealImpl
  + MockImpl
- `uploads` and `cycles` surfaces wired to real BFF handlers
- 4 inbox cards: `UploadPendingReviewCard`, `UploadValidatedCard`,
  `CyclePendingCloseCard`, `CycleCloseReviewCard`
- Fixtures: 3 CSV test files, 2 seed JSON files, `cleanup_old_uploads` job

Codex history:
- R1: NO-GO (10 blocks) -- wrong paths, missing PHI controls, sync event
  publisher, financial schema errors, MFA gate non-implementable against HEAD
- R2: NO-GO (3 blocks) -- MFA gate resolution, async event publisher, financial
  schema corrections (amount_billed column, quantity 3dp)
- R3: GO-WITH-CHANGES -- all blocks resolved; execution authorized

### Plan C -- Batches + AR/AP + Payment Runs + Supporting Surfaces (R3)
- `BatchesClient`, `InvoicesClient`, `PaymentRunsClient`, `CarryoversClient`,
  `BankSettlementsClient`, `ReconciliationsClient` contract clients
- `batches`, `invoices`, `payment-runs`, `carryovers`, `bank-settlements`,
  `reconciliations` surfaces wired to real BFF handlers with `RbacGate` on all
  mutating actions
- RBAC enforcement audit + Approver gate added to 19 unguarded billing endpoints
- `upload_id` FK propagation onto Batch, InvoiceLine, PaymentRun ORM models
- 6 inbox cards: `BatchDraftedCard`, `ArInvoiceDraftCard`,
  `ApPaymentRunHeldCard`, `BankingDiscrepancyCard`,
  `ReconciliationPendingCard`, `CarryoverOpenCard`
- Fixtures: invoices.json (10), payment-runs.json (5), reconciliations.json (1)
- SAVEPOINT-based test isolation in billing conftest (LESSON-001)

Codex history:
- R1: NO-GO -- list schema bare-array/envelope mismatch, broken re-export
  shims, missing GET stubs for 4 new surfaces, Cache-Control gaps
- R2: NO-GO -- B4 union not applied to 3 list schemas, C1 error passthrough
  incomplete
- R3: GO-WITH-CHANGES -- all blocks resolved; 2 accepted nits (see deferred
  items below)

### Plan D -- Files (NACHA/835) + Journal Ledger + Hash-Chain Verifier (R2)
- `FileArtifact` ORM + migration 0005 (`billing.file_artifacts`)
- Files router: generate NACHA/835, download, list, get (Approver-only on
  generate; Auditor-only on verify-chain)
- Journal hash-chain: SHA-256 chained entries, `sync_verifier` endpoint,
  configurable 10K-entry threshold (`PAYSYNC_HASH_CHAIN_SYNC_LIMIT`)
- `FilesClient`, `JournalClient` contract clients
- `files` and `journal` surfaces with `HashChainBadge` wired
- `journal_periodic_review` inbox derivation (Auditor inbox when last verify
  >7 days ago) + `JournalPeriodicReviewCard`
- `Cache-Control: no-store` on all HTTPException responses (C1 fix)

Codex history:
- R1: NO-GO (4 blocks) -- entry_hash auto-compute missing, tenant-scoped
  NACHA/835 query gaps, chain index ordering non-deterministic, Cache-Control
  missing on HTTPException paths
- R2: GO-WITH-CHANGES -- all 4 blocks resolved; TenantScopedMixin retrofit for
  billing models deferred as out-of-scope debt (see deferred items below)

### Plan E -- Reports + Setup + E2E + Cleanup (this document)
- `reports` surface (read-only, all roles)
- `setup` surface (Approver-only mutations)
- 8 fixture seed types populated for E2E validation
- Portal scaffolding cleanup: 9 copied surface directories deleted from
  `portal/operator/app/` after confirming module surface counterparts exist
- `echo-client.ts` contract stub (types + cache policies for Wave 41 M6)
- `operator-dev.yml` manifest updated to final SP-1 state
- `packages/modules/paysync/README.md` written
- This acceptance document

Deferred from Plan E:
- E2E Playwright round-trip (`sp1-paysync-round-trip.spec.ts`, 25 steps) --
  separate subagent effort (Task 4/5)
- `portal/operator/app/admin/paysync/echo/` portal page deletion deferred
  until E2E step 6.4 confirms module echo route works end-to-end
- Setup surface dirs (`cycle-schedules`, `email-*`, `export-templates`,
  `gl-account-mappings`, `invoice-sequences`) not deleted -- pending Task 2
  rewire confirmation

---

## Deferred Follow-ups

| ID | Item | Source | Priority |
|---|---|---|---|
| D-01 | SAVEPOINT conftest bypass in new Plan C integration tests -- test isolation uses nested transaction but 2 new tests do not yet use the LESSON-001 fixture pattern | Plan C R3 nit | Low |
| D-02 | Contract test coverage for 3 list schemas (BankSettlementListResponse, ReconciliationListResponse, CarryoverListResponse) -- shape tests exist but envelope/bare-array union not exercised in contract tests | Plan C R3 nit | Low |
| D-03 | TenantScopedMixin retrofit for billing models (Upload, Batch, Invoice, PaymentRun) -- currently rely on RLS-only isolation; explicit ORM-level tenant filter deferred as out-of-scope debt | Plan D R2 accepted debt | Medium |
| D-04 | qa-harness extension (RoleSwitcherChip integration, harness role-switch test flow) -- Task 4 deferred | Plan E | Medium |
| D-05 | Playwright E2E round-trip (25-step `sp1-paysync-round-trip.spec.ts`) -- Task 5 deferred | Plan E | High |
| D-06 | Plan F: BankSettlement + Reconciliation ORM models currently stubs (GET endpoints return empty lists); full ORM + migration deferred | Plan C scope note | High |
| D-07 | Plan F: Mutation methods on BankSettlementsClient + ReconciliationsClient (resolve discrepancy, finalize reconciliation) -- B3 deferral accepted in Plan C | Plan C B3 | Medium |
| D-08 | EchoClient RealImpl + MockImpl -- echo-client.ts has types + cache policies only; wire to portal/shared/lib/paysync-api.ts after confirming PAYSYNC_BASE | Plan E 6.0b | Medium |

---

## Test Counts (post-Task 7 commit)

| Layer | Files | Tests | Status |
|---|---|---|---|
| paysync module (`@infinityrx/module-paysync`) | 23 | 413 | All pass |
| contract (`@infinityrx/contract`) | 6 | 167 | All pass |
| billing backend (`modules/billing`) | ~50 | ~350 | All pass (last verified W5) |

---

## Verification Commands

```
# TypeScript
npx tsc -b packages/modules/paysync

# Module tests
npm test --workspace=@infinityrx/module-paysync

# Contract tests
npm test --workspace=@infinityrx/contract

# Manifest
npm run manifest:validate
```

All four commands pass clean on branch `wave/B10-w5-sp1-paysync` at
Task 7 commit.
