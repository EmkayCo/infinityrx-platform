# @infinityrx/module-paysync

PaySync is the financial-processing module for the InfinityRx operator portal.
It owns the full upload-to-payment lifecycle: CSV/Excel upload ingestion,
billing cycle management, NACHA/835 file generation, AR invoicing, AP payment
runs, bank settlement reconciliation, journal ledger, reports, and setup.

## Why a separate module

Composition isolation (SD-4): PaySync has distinct RBAC boundaries (operator /
approver / auditor roles with non-overlapping permission sets), independently
testable BFF handlers, and a contract surface that must not bleed into other
modules. Separating it prevents the billing domain from coupling to portal
shell internals and allows the module to be added or removed from any operator
manifest without touching shared code.

## Surfaces (13 total)

| Surface | Route | Description |
|---|---|---|
| uploads | /admin/paysync | Inbox + upload history; entry point |
| cycles | /admin/paysync/cycles | Billing cycle list and close workflow |
| batches | /admin/paysync/batches | Payment batch draft and release |
| carryovers | /admin/paysync/carryovers | AP carryforward records |
| invoices | /admin/paysync/invoices | AR invoice draft, send, status |
| payment-runs | /admin/paysync/payment-runs | AP payment run release + manual AP |
| files | /admin/paysync/files | NACHA/835 file generation and download |
| bank-settlements | /admin/paysync/settlements | Bank settlement entry and discrepancy |
| reconciliations | /admin/paysync/reconcile | Reconciliation finalization |
| journal | /admin/paysync/journal | Hash-chain ledger viewer and verifier |
| reports | /admin/paysync/reports | Read-only financial reporting |
| setup | /admin/paysync/setup | Approver-only configuration |
| echo | /admin/paysync/echo | Echo Spec 400 runs and candor pipeline |

## Inbox card kinds (11)

The Inbox spine presents actionable items to the right role. Each kind maps to
exactly one RBAC role via `INBOX_KIND_ROLE` in `src/inbox/types.ts`.

| Kind | Role | Trigger |
|---|---|---|
| upload_pending_review | operator | Upload parse failed or validation error |
| upload_validated_awaiting_batching | operator | Upload passed validation, not yet batched |
| cycle_pending_close | operator | Billing cycle ready to close |
| carryover_open | operator | AP carryforward item unresolved |
| cycle_close_review | approver | Cycle close submitted, awaiting approval |
| batch_drafted | approver | Payment batch drafted, awaiting release |
| ar_invoice_draft | approver | AR invoice drafted, awaiting send |
| ap_payment_run_held | approver | AP payment run held for approval |
| banking_discrepancy | approver | Bank settlement discrepancy flagged |
| reconciliation_pending | approver | Reconciliation needs finalization |
| journal_periodic_review | auditor | Hash-chain verification overdue (>7 days) |

## Provenance chain

Every financial entity traces back to the upload that produced it:

```
Upload
  -> ClaimRecord (billing.claim_records.upload_id FK)
     -> Batch / PaymentBatch (upload_id FK)
        -> InvoiceLine / Invoice (upload_id FK)
           -> PaymentRun (upload_id FK)
              -> FileArtifact NACHA/835 (references payment_run_id)
                 -> JournalEntry (hash-chained ledger)
```

`ProvenanceBreadcrumb` renders this chain on every detail page. The chain is
content-addressed: each upload has a `content_sha256`; duplicate submissions
return the existing upload ID rather than creating a new record.

## RBAC matrix

Permissions are defined in `module.config.ts` under `paysyncComposition.rbac`.

| Permission | operator | approver | auditor |
|---|:---:|:---:|:---:|
| paysync.upload | Yes | Yes | - |
| paysync.upload.view | Yes | Yes | Yes |
| paysync.batch.draft | Yes | Yes | - |
| paysync.cycle.view | Yes | Yes | - |
| paysync.carryover.view | Yes | Yes | - |
| paysync.journal.view | Yes | Yes | Yes |
| paysync.audit.view | Yes | Yes | Yes |
| paysync.cycle.close | - | Yes | - |
| paysync.invoice.send | - | Yes | - |
| paysync.payment_run.release | - | Yes | - |
| paysync.nacha.generate | - | Yes | - |
| paysync.835.generate | - | Yes | - |
| paysync.reconcile.finalize | - | Yes | - |
| paysync.discrepancy.resolve | - | Yes | - |
| paysync.manual_ap.commit | - | Yes | - |
| paysync.setup.mutate | - | Yes | - |
| paysync.read | - | - | Yes |
| paysync.journal.verify | - | - | Yes |

`RbacGate` in `src/components/RbacGate.tsx` enforces these at render time.
Backend enforcement is via `get_current_user` + role checks on every mutating
billing endpoint.

## How to run

### Prerequisites

- Node.js 20+
- `npm install` from the monorepo root

### Tests

```
npm test --workspace=@infinityrx/module-paysync
```

23 test files, 413 tests. Coverage requirements: 100% on financial
(MoneyDisplay, MoneyInput, all Decimal paths), PHI (tenant isolation, access
logging), security (RBAC on every surface); >=99% branch coverage on all other
module code (CLAUDE.md Auto-Gate).

### TypeScript

```
npx tsc -b packages/modules/paysync
```

### Fixtures

Seed data lives under `fixtures/`. The verify-w5-fixtures script confirms all
fixture routes are reachable:

```
npx tsx portal/operator/scripts/verify-w5-fixtures.ts
```

## Entry point

`module.config.ts` is read by `packages/scripts/build-manifest.ts` (SD-4 shape).
`paysyncComposition` carries the runtime composition: RBAC matrix, inbox kind
registrations with lazy card imports, route-to-surface map, nav tree, and the
qa namespace (dev-only `RoleSwitcherChip` gated behind `NODE_ENV` check).

The public module barrel is `src/index.ts`. It exports inbox types, primitives
(MoneyDisplay, MoneyInput, RbacGate, ProvenanceBreadcrumb, HashChainBadge),
and all 13 surface configs. `src/components/dev-only/` is intentionally
excluded from the barrel.

## Plan coverage

| Plans | Task IDs | Surfaces delivered |
|---|---|---|
| Plan A | A1-A7 | Module scaffold, inbox spine, 13 surface stubs, manifest wiring |
| Plan B | B1-B6c | uploads, cycles; Upload ORM + billing backend; 4 inbox cards |
| Plan C | C1-C7 | batches, invoices, payment-runs, carryovers, bank-settlements, reconciliations; 6 inbox cards |
| Plan D | D1-D7 | files, journal; FileArtifact ORM; hash-chain verifier; journal_periodic_review card |
| Plan E | E1-E7 | reports, setup; fixture seed data; portal scaffolding cleanup; manifest final state |
