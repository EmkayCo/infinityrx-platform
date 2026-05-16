# SP-1 Plan C — Batches + AR/AP + Payment Runs + Supporting Surfaces

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution
**Depends on:** SP-1 Plan B (Upload resource + Cycles surface complete)

---

## Goal

Wire the four core financial-processing surfaces — batches, invoices (AR), payment runs (AP),
and carryovers — to the real `modules/billing/` backend, enforce the full RBAC matrix on every
mutating action, carry upload provenance through every derived entity, and deliver the remaining
seven Inbox card components. After Plan C, an Approver can take a validated upload all the way
through: batch creation → cycle close (Plan B) → AR invoice draft + send → AP payment run
release. The money path is fully wired and RBAC-gated.

This plan also wires `bank-settlements` and `reconciliations` as read-only surfaces so the
complete left-nav is functional. Mutating actions on those surfaces (finalize reconciliation,
resolve discrepancy) are wired; file generation (NACHA/835) is Plan D.

---

## Scope

**In:**
- `surfaces/batches/` — rewire existing `portal/operator/app/admin/paysync/batches/` pages; add `ProvenanceBreadcrumb`, `RbacGate` on release/hold actions; BFF handlers
- `surfaces/invoices/` — rewire existing invoice pages from `portal/operator/app/admin/paysync/invoices/` + `portal/operator/app/accounting/invoices/`; `RbacGate` on send action
- `surfaces/payment-runs/` — rewire existing `portal/operator/app/payments/batches/` + `portal/operator/app/admin/paysync/manual-ap/`; `RbacGate` on release action
- `surfaces/carryovers/` — rewire existing `portal/operator/app/admin/paysync/carryovers/`
- `surfaces/bank-settlements/` — rewire existing; read-plus-mutate (resolve discrepancy — Approver only)
- `surfaces/reconciliations/` — rewire existing; finalize mutation — Approver only
- Contract: `BatchesClient`, `InvoicesClient`, `PaymentRunsClient`, `CarryoversClient`, `BankSettlementsClient`, `ReconciliationsClient` — interface + RealImpl + MockImpl
- Backend: RBAC enforcement audit for mutating endpoints on batches, invoices, payment-runs (verify Approver gate on existing billing routes; add where missing, per spec §5.5 point 2)
- Backend: `upload_id` propagation — verify Batch, InvoiceLine, PaymentRun ORM models carry `upload_id` backward link; add FK + migration if absent
- Inbox: remaining 7 card components (`batch_drafted`, `ar_invoice_draft`, `ap_payment_run_held`, `banking_discrepancy`, `reconciliation_pending`, `carryover_open` — 6 new; `journal_periodic_review` stub remains for Plan D)
- Backend: `inbox.py` extended — add derivation logic for 6 new Inbox item kinds
- `fixtures/seeds/invoices.json` — 10 synthetic invoices
- `fixtures/seeds/payment-runs.json` — 5 payment runs in mixed states
- `fixtures/seeds/reconciliations.json` — 1 reconciliation with intentional discrepancy

**Out:**
- NACHA and 835 file generation (Plan D)
- Journal ledger viewer and hash-chain verifier (Plan D)
- Reports and setup surfaces (Plan E)
- E2E round trip (Plan E)
- `journal_periodic_review` Inbox card (Plan D)

---

## Tasks

### Task 1 — Backend: upload_id propagation onto derived entities

Verify and, where absent, add `upload_id` FK columns to the existing ORM models. All billing
ORM classes live in `modules/billing/src/models/tables.py` — there is no separate `models/`
subdirectory with per-entity files. The relevant classes and their line numbers (verified from HEAD):

| Model class | Line in tables.py | Equivalent plan term |
|---|---|---|
| `PaymentBatch` | 214 | "Batch" |
| `Payment` | 254 | individual payment within a batch |
| `Invoice` | 333 | AR invoice |
| `InvoiceLineItem` | 391 | "InvoiceLine" |

**Note on missing classes (B3 resolution):**
- `PaymentRun` — does not exist as a separate ORM class. `PaymentBatch` (line 214) is the
  equivalent. All plan references to "PaymentRun" must use `PaymentBatch`.
- `Carryover` — not present in `modules/billing/src/models/tables.py`. It exists as a
  TypeScript type in `portal/shared/lib/paysync-api.ts` but has no backend ORM model.
  **Decision:** Plan C adds a new `Carryover` ORM model to `tables.py` as part of Task 1
  (new class after `ARPayment` at line 451). This is new scope SP-1 must add, not pre-existing.
- `BankSettlement` — not in billing models. `Settlement` IS in
  `modules/payment-processing/src/models/tables.py` (line 138). Plan C surfaces read from
  the payment-processing module via its API; Plan C does NOT duplicate the ORM model.
- `Reconciliation` — not in billing. Tied to `Settlement` in payment-processing. Same
  approach: read via payment-processing API, do not duplicate ORM.

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | Audit `PaymentBatch`, `Invoice`, `InvoiceLineItem` in `tables.py` for `upload_id` FK | `modules/billing/src/models/tables.py` | — | Audit finding in commit message |
| 1.2 | Add `upload_id` FK to `PaymentBatch` (if absent) | `modules/billing/src/models/tables.py` | unit: payment_batch.upload_id set when created from upload | FK present |
| 1.3 | Add `upload_id` FK to `InvoiceLineItem` (if absent) | `modules/billing/src/models/tables.py` | unit: invoice_line_item.upload_id traces to source upload | FK present |
| 1.4 | Add new `Carryover` ORM model to `tables.py` | `modules/billing/src/models/tables.py` | unit: model fields, TenantScopedMixin inherited | New model present |
| 1.5 | Alembic migration `0012_upload_id_on_derived_entities.py` | `modules/billing/alembic/versions/` | migration upgrade + downgrade clean | Schema updated |

**Rule:** `upload_id` FKs on derived entities are NULLABLE (same rationale as `ClaimRecord` in
Plan B — existing rows have no upload; new rows must have it set at the service layer).

**Provenance chain verified by:** `ProvenanceBreadcrumb` on Batch detail page renders
`Upload #N → Cycle ... → Batch B-XXXX`. If `upload_id` is null on a `PaymentBatch` (legacy data),
breadcrumb renders `Legacy (no upload) → Cycle ... → Batch B-XXXX` — never crashes.

- [ ] Step 1.1: Read `modules/billing/src/models/tables.py` lines 214–450; confirm which FKs are absent
- [ ] Step 1.2–1.3: Add missing `upload_id` FKs to `PaymentBatch` and `InvoiceLineItem`
- [ ] Step 1.4: Add `Carryover` model class to `tables.py` (after `ARPayment`, line ~451)
- [ ] Step 1.5: Write migration `0012`; run upgrade + downgrade
- [ ] Step 1.6: Write unit tests for FK propagation + new Carryover model
- [ ] Step 1.7: Commit — `feat(sp-1-c): upload_id FK on PaymentBatch/InvoiceLineItem + new Carryover model + alembic 0012`

---

### Task 2 — Backend: RBAC enforcement audit on mutating billing endpoints

Per spec §5.5 point 2: verify Operator/Approver/Auditor gates are enforced at the server-side
on every mutating endpoint in `modules/billing/src/api/router.py`. The REAL routes (verified
from HEAD — see inventory §5) are listed below. Audit against these exact paths, not invented ones.

**Billing router actual routes** (from `modules/billing/src/api/router.py`):

| Real endpoint | Required role | Action if missing |
|---|---|---|
| `POST /claims` (line 93) | Operator or Approver | Add `require_role(['operator','approver'])` |
| `POST /routing-rules` (line 280) | Approver only | Add if missing |
| `PUT /routing-rules/{rule_id}` (line 290) | Approver only | Add if missing |
| `POST /payment-batches/generate` (line 533) | Operator or Approver | Add if missing |
| `POST /payment-batches/{batch_id}/validate` (line 592) | Operator or Approver | Add if missing |
| `POST /payment-batches/{batch_id}/approve` (line 602) | Approver only | Add if missing |
| `POST /payment-batches/{batch_id}/submit` (line 612) | Approver only | Add if missing |
| `POST /payment-batches/{batch_id}/void` (line 622) | Approver only | Add if missing |
| `POST /settlement/record` (line 686) | Approver only | Add if missing |
| `POST /invoicing-configs` (line 786) | Approver only | Add if missing |
| `PUT /invoicing-configs/{config_id}` (line 796) | Approver only | Add if missing |
| `POST /invoices/generate` (line 871) | Operator or Approver | Add if missing |
| `POST /invoices/{invoice_id}/approve` (line 951) | Approver only | Add if missing |
| `POST /invoices/{invoice_id}/send` (line 961) | Approver only | Add if missing |
| `POST /invoices/{invoice_id}/void` (line 971) | Approver only | Add if missing |

**Auditor role:** GET-only access to all billing endpoints. No mutating actions.

**RBAC matrix summary (per inventory §5):**
- Operator: GET on all; POST `/claims`, POST `/payment-batches/{id}/validate`
- Approver: all Operator permissions PLUS all approve/submit/void/send/record/generate mutations
- Auditor: GET only

**Implementation pattern** (consistent with existing billing auth pattern):
```python
# In each route handler, after get_current_user:
from shared.auth.roles import require_role  # or equivalent in billing module
require_role(current_user, ['approver'])  # raises 403 on deny
```

If `shared.auth.roles` doesn't exist, add it as a thin helper in `shared/auth/roles.py` that
checks `current_user.roles` (list of strings from JWT claim) against the required set.

**Per-endpoint cross-tenant isolation tests (mandatory):** EVERY endpoint in the billing
router (both GET and mutating) that returns tenant-scoped data MUST have a dedicated cross-tenant
test: 2 tenants, seed both, authenticate as Tenant A, assert zero Tenant B records. This applies
to all 29 billing routes listed in inventory §5.

**MFA gate tests:** add one test per new-or-modified route that confirms `mfa_verified=False`
JWT + `mfa_required=True` tenant returns 403.

**Test:** for each gated endpoint:
- Approver → 200/201
- Auditor → 403
- Operator → 403 (Approver-only) or 200/201 (Operator-or-Approver)
- Cross-tenant → 0 Tenant B rows
- MFA gate → 403 when not verified

- [ ] Step 2.1: Read `modules/billing/src/api/router.py`; list which of the 15 mutating routes lack role enforcement
- [ ] Step 2.2: Add role enforcement to each gap route
- [ ] Step 2.3: Add `shared/auth/roles.py` if it doesn't exist
- [ ] Step 2.4: Write integration tests for RBAC matrix on each mutating endpoint + cross-tenant per endpoint + MFA gate per endpoint
- [ ] Step 2.5: Run tests — 100% on security/auth paths
- [ ] Step 2.6: Commit — `feat(sp-1-c): RBAC enforcement audit — Approver gate on real billing routes per router.py`

---

### Task 3 — Contract: 6 new clients

| # | Client | File | Key methods |
|---|---|---|---|
| 3.1 | `BatchesClient` | `packages/contract/src/impls/paysync/batches-client.ts` | `list`, `get`, `create`, `release`, `hold` |
| 3.2 | `InvoicesClient` | `packages/contract/src/impls/paysync/invoices-client.ts` | `list`, `get`, `send`, `createDraft` |
| 3.3 | `PaymentRunsClient` | `packages/contract/src/impls/paysync/payment-runs-client.ts` | `list`, `get`, `release`, `hold` |
| 3.4 | `CarryoversClient` | `packages/contract/src/impls/paysync/carryovers-client.ts` | `list`, `get` |
| 3.5 | `BankSettlementsClient` | `packages/contract/src/impls/paysync/bank-settlements-client.ts` | `list`, `get`, `resolveDiscrepancy` |
| 3.6 | `ReconciliationsClient` | `packages/contract/src/impls/paysync/reconciliations-client.ts` | `list`, `get`, `finalize` |

Each follows the established RealImpl + MockImpl pattern from Plan B. Response types added to
`packages/contract/src/impls/paysync/types.ts`. All monetary amounts typed as `string` (Decimal
serialised per `.claude/rules/financial-precision.md` — no `number` for money fields).

**Financial precision in contract types** — critical:
```ts
// CORRECT — Decimal as string
type Batch = { total_amount: string; ... };

// FORBIDDEN — never use number for money
// type Batch = { total_amount: number; ... };
```

- [ ] Step 3.1–3.6: Write all 6 client files with RealImpl + MockImpl
- [ ] Step 3.7: Add response types to `packages/contract/src/impls/paysync/types.ts`
- [ ] Step 3.8: `tsc -b` clean
- [ ] Step 3.9: Commit — `feat(sp-1-c): contract clients for batches/invoices/payment-runs/carryovers/settlements/reconciliations`

---

### Task 4 — Frontend: batches surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 4.1 | Copy + rewire batches pages | `surfaces/batches/` | RTL: renders batch list, provenance breadcrumb | Pages in module |
| 4.2 | `RbacGate` on release + hold | `surfaces/batches/BatchDetailPage.tsx` | RTL: Operator sees disabled release; Approver enabled | RBAC enforced |
| 4.3 | `ProvenanceBreadcrumb` | `surfaces/batches/BatchDetailPage.tsx` | RTL: chain includes upload reference | Provenance shown |
| 4.4 | BFF handlers | `surfaces/batches/bff/` | — | Route handlers |
| 4.5 | `batch_drafted` Inbox card | `src/inbox/cards/BatchDraftedCard.tsx` | RTL: renders batch amount, click fires nav | Card functional |

Money amounts in batch pages use `MoneyDisplay` component — never raw number formatting.
`MoneyInput` on manual AP entry form — validates ≤4 decimal places, ROUND_HALF_UP.

- [ ] Step 4.1–4.4: Implement batches surface
- [ ] Step 4.5: Implement `BatchDraftedCard`
- [ ] Step 4.6: RTL tests
- [ ] Step 4.7: Commit — `feat(sp-1-c): batches surface — RBAC-gated release/hold + provenance`

---

### Task 5 — Frontend: invoices surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 5.1 | Copy + rewire invoice pages | `surfaces/invoices/` | RTL: invoice list renders, draft badge visible | Pages in module |
| 5.2 | `RbacGate` on send action | `surfaces/invoices/InvoiceDetailPage.tsx` | RTL: Operator sees disabled send; Approver enabled | RBAC enforced |
| 5.3 | `ProvenanceBreadcrumb` | `surfaces/invoices/InvoiceDetailPage.tsx` | RTL: chain shows upload → cycle → batch → invoice | Full provenance |
| 5.4 | BFF handlers | `surfaces/invoices/bff/` | — | Route handlers |
| 5.5 | `ar_invoice_draft` Inbox card | `src/inbox/cards/ArInvoiceDraftCard.tsx` | RTL: renders invoice amount as string | Card functional |

Invoice amounts must use `MoneyDisplay`. The send-invoice confirmation dialog must display
the total amount with `MoneyDisplay` and require explicit Approver confirmation (two-step:
preview → confirm → POST).

- [ ] Step 5.1–5.4: Implement invoices surface
- [ ] Step 5.5: Implement `ArInvoiceDraftCard`
- [ ] Step 5.6: RTL tests
- [ ] Step 5.7: Commit — `feat(sp-1-c): invoices surface — send-gated to Approver + full provenance chain`

---

### Task 6 — Frontend: payment-runs surface

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 6.1 | Copy + rewire payment-run pages | `surfaces/payment-runs/` | RTL: payment run list renders | Pages in module |
| 6.2 | `RbacGate` on release | `surfaces/payment-runs/PaymentRunDetailPage.tsx` | RTL: Operator disabled; Approver enabled | RBAC enforced |
| 6.3 | Manual AP entry form | `surfaces/payment-runs/ManualApForm.tsx` | RTL: `MoneyInput` rejects >4dp; Approver-only submit | Manual AP gated |
| 6.4 | `ProvenanceBreadcrumb` | `surfaces/payment-runs/PaymentRunDetailPage.tsx` | RTL: chain includes upload | Provenance shown |
| 6.5 | BFF handlers | `surfaces/payment-runs/bff/` | — | Route handlers |
| 6.6 | `ap_payment_run_held` Inbox card | `src/inbox/cards/ApPaymentRunHeldCard.tsx` | RTL: renders hold reason | Card functional |

**Write-path error handling** (spec §8): payment-run release is a money operation — always
fail-fast on backend error, never optimistic commit. Error toast must include `correlation_id`.

- [ ] Step 6.1–6.5: Implement payment-runs surface
- [ ] Step 6.6: Implement `ApPaymentRunHeldCard`
- [ ] Step 6.7: RTL tests
- [ ] Step 6.8: Commit — `feat(sp-1-c): payment-runs surface — release gated to Approver + manual AP form`

---

### Task 7 — Frontend: carryovers, bank-settlements, reconciliations + 4 Inbox cards

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 7.1 | Carryovers surface | `surfaces/carryovers/` | RTL: list renders, open badge | Wired |
| 7.2 | Bank-settlements surface | `surfaces/bank-settlements/` | RTL: discrepancy badge; Approver can resolve | Wired |
| 7.3 | Reconciliations surface | `surfaces/reconciliations/` | RTL: finalize gated to Approver | Wired |
| 7.4 | `carryover_open` card | `src/inbox/cards/CarryoverOpenCard.tsx` | RTL: renders | Card |
| 7.5 | `banking_discrepancy` card | `src/inbox/cards/BankingDiscrepancyCard.tsx` | RTL: renders amount mismatch | Card |
| 7.6 | `reconciliation_pending` card | `src/inbox/cards/ReconciliationPendingCard.tsx` | RTL: renders | Card |

**Backend inbox.py extension** — add derivation logic for:
- `batch_drafted` — batches with `status=drafted` (no BatchIds released yet)
- `ar_invoice_draft` — invoices with `status=draft`
- `ap_payment_run_held` — payment runs with `status=held`
- `banking_discrepancy` — settlements with unresolved discrepancy flag
- `reconciliation_pending` — reconciliations with `status=pending`
- `carryover_open` — carryovers with `status=open`

All carry `upload_id` where the entity chain has one; `null` for legacy records.

**Populate fixtures:**
- `fixtures/seeds/invoices.json` — 10 invoices (3 draft, 4 sent, 3 paid) with synthetic amounts as strings
- `fixtures/seeds/payment-runs.json` — 5 runs (2 held, 2 released, 1 settled)
- `fixtures/seeds/reconciliations.json` — 1 pending reconciliation with $12.34 discrepancy

- [ ] Step 7.1–7.3: Implement 3 surfaces
- [ ] Step 7.4–7.6: Implement 3 Inbox cards
- [ ] Step 7.7: Extend `modules/billing/src/api/inbox.py` with 6 new kind derivations
- [ ] Step 7.8: Populate fixture seed JSON files
- [ ] Step 7.9: RTL + backend integration tests
- [ ] Step 7.10: Commit — `feat(sp-1-c): carryovers/settlements/reconciliations surfaces + 3 inbox cards + inbox feed extended`

---

## Gate Criteria

Plan C is complete when ALL of the following are true:

- [ ] `modules/billing` full test suite passes; 100% on all RBAC/auth paths added in this plan; 100% on all financial paths (Decimal amounts, MoneyDisplay, MoneyInput); **≥99% branch coverage** on all other new active code (CLAUDE.md Auto-Gate)
- [ ] Migration `0012` runs upgrade + downgrade cleanly
- [ ] `GET /api/v1/billing/inbox?role=approver` returns items of kinds `batch_drafted`, `ar_invoice_draft`, `ap_payment_run_held` when database is seeded with plan fixtures
- [ ] `POST /api/v1/billing/payment-batches/{id}/approve` by Auditor role returns 403 (real route name per router.py line 602)
- [ ] `POST /api/v1/billing/invoices/{id}/send` by Operator role returns 403 (real route per router.py line 961)
- [ ] Cross-tenant isolation test passes for EVERY billing route (all 29 routes in router.py)
- [ ] MFA gate test passes for every new or modified route
- [ ] ORM class names used throughout plan match `tables.py`: `PaymentBatch` (not `Batch`/`PaymentRun`), `InvoiceLineItem` (not `InvoiceLine`), new `Carryover` model documented and committed
- [ ] `BankSettlement` / `Reconciliation` surfaces read from payment-processing API — no duplicate ORM model in billing
- [ ] `npm --workspace=@infinityrx/module-paysync test` passes; 100% on `MoneyDisplay`/`MoneyInput`/`RbacGate`; **≥99% branch coverage** on all 6 new surfaces
- [ ] `tsc -b` clean across workspace
- [ ] Batch detail page RTL test: Operator sees disabled release button with tooltip "Approver role required"
- [ ] Invoice send confirmation dialog RTL test: amount shown via `MoneyDisplay`, not raw number
- [ ] PaymentBatch release fail-fast test: backend 500 → error toast with correlation_id; no optimistic state change
- [ ] All 10 fixture invoices have `total_amount` as string (Decimal) not number
- [ ] 10 Inbox card components exist and are non-stub (Plan A stubs replaced for all except `journal_periodic_review`)

---

## Deliverables

- 6 financial surfaces wired to real backend with full RBAC enforcement
- `upload_id` provenance carried through Batch → InvoiceLine → PaymentRun
- 10 of 11 Inbox card components fully implemented (journal_periodic_review remains stub for Plan D)
- Inbox feed extended to all non-journal item kinds
- 6 contract clients (RealImpl + MockImpl) for Plans D/E to extend
- RBAC server-side enforcement audited and gap-filled on all billing mutating endpoints
- Populated fixture seeds for invoices, payment runs, reconciliations

---

## Dependencies

- SP-1 Plan B complete (Upload model + Cycles surface wired; `InboxClient` real impl)
- Existing billing ORM models — all in `modules/billing/src/models/tables.py`:
  - `PaymentBatch` (line 214) — the "batch" entity; no separate `Batch` or `PaymentRun` class
  - `Payment` (line 254) — individual payment row
  - `Invoice` (line 333) — AR invoice
  - `InvoiceLineItem` (line 391) — not `InvoiceLine`
  - `ARRecord` (line 416), `ARPayment` (line 451) — AR payment tracking
  - `JournalEntry` (line 478) — immutable ledger
  - `Carryover` — NEW model added by Plan C Task 1 (not pre-existing)
  - `BankSettlement` / `Reconciliation` — NOT in billing; `Settlement` is in `modules/payment-processing/src/models/tables.py` (line 138); accessed via payment-processing API
- Existing billing API routes — all in `modules/billing/src/api/router.py` (29 routes, see inventory §5)
- `shared/auth/roles.py` (may need to create — Task 2 covers this)
- `MoneyDisplay`, `MoneyInput`, `ProvenanceBreadcrumb`, `RbacGate` from Plan A (all present in `packages/modules/paysync/src/components/`)
- `modules/payment-processing/src/api/router.py` — for reading settlements/reconciliations (see inventory §6)

---

## Cross-references

- Spec §5.4 (RBAC matrix — every mutating action in this plan), §5.5 (backend posture — RBAC enforcement + upload_id propagation), §6.5 (wrapping existing surfaces), §7.1 (canonical request flow steps 10–12), §8 (error handling — write-path fail-fast, money precision), §9.3 (fixture data)
- Rules: `.claude/rules/financial-precision.md` (all monetary amounts as Decimal/string; ROUND_HALF_UP), `.claude/rules/security.md` (RBAC server-side enforcement), `.claude/rules/tenant-isolation.md`, `.claude/rules/testing.md` (100% financial + security coverage)
- SP-1 Plan B: `docs/superpowers/plans/2026-05-16-sp1-plan-b-uploads-cycles.md`
- SP-1 Plan D: consumes Batch/PaymentRun models for NACHA/835 file generation
- Existing billing models (all in `modules/billing/src/models/tables.py`): `PaymentBatch` (214), `Payment` (254), `Invoice` (333), `InvoiceLineItem` (391); `Settlement` is in payment-processing not billing
- Existing billing services: `modules/billing/src/services/{ap,ar,nacha}.py`
- Existing billing routes: `modules/billing/src/api/router.py` (all 29 routes — use these, not invented paths like `/billing/batches` or `/billing/payment-runs`)
