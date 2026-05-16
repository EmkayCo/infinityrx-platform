# SP-1 Plan A — Module Scaffold + Inbox Spine

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution
**Depends on:** SP-0 Plans A–D (packages/contract, packages/auth, packages/ui, packages/qa-harness, packages/shell all shipped)

---

## §10 Plan-Time Decisions Resolved in This Plan

This plan resolves all six §10 plan-time decisions from the spec. Decisions that belong to
later plans are noted with the plan that owns them.

| # | Decision | Resolution | Owned by |
|---|---|---|---|
| §10.1 | Plan phasing strategy | 5 plans: A=scaffold+inbox, B=uploads+cycles, C=batches+AR/AP, D=files+journal, E=reports+setup+E2E | Plan A (this) |
| §10.2 | Upload file storage strategy | Local disk under `uploads/{tenant_id}/{upload_id}/{original_filename}` in the billing module's working dir; configurable via `PAYSYNC_UPLOAD_DIR` env var; 90-day retention policy enforced by a nightly cleanup job registered in the manifest | Plan B |
| §10.3 | CSV/Excel minimum schema | 8 mandatory columns: `ndc` (11 digits), `npi` (10 digits, Luhn), `claim_id` (string, unique within upload), `date_of_service` (YYYY-MM-DD), `quantity` (positive Decimal), `days_supply` (positive integer), `amount_billed` (Decimal, 4dp max), `member_id` (string); `source_platform` header comment optional | Plan B |
| §10.4 | Hash-chain verifier perf budget | 5 seconds for ≤10 000 entries synchronously; for chains >10 000 entries the sync endpoint returns `{verified: null, too_large: true, job_id: "<id>"}` and the UI polls the existing async job | Plan D |
| §10.5 | Inbox cache strategy | Polling at 10s interval, `revalidate-on-focus` via TanStack Query `staleTime: 10_000`; no WebSocket in SP-1; per-kind TTL: all inbox item kinds share 10s; mutation handlers call `invalidateQueries(['paysync','inbox'])` immediately | Plan A (this) |
| §10.6 | Module-extraction sequence | Extract-per-surface as each surface is wired (Plans B/C/D/E), not bulk-upfront. Plan A creates the skeleton folders with `index.ts` stubs; each subsequent plan fills its assigned surfaces | Plan A (this) |

---

## Goal

Establish `packages/modules/paysync/` as a fully typed SP-0-conformant module package with the
complete folder skeleton, `module.config.ts` entry point, the Inbox spine (typed taxonomy,
`useInboxItems` hook, `InboxQueue` component, `ItemRegistry`), all module-local shared
primitives (`ProvenanceBreadcrumb`, `MoneyDisplay`, `MoneyInput`, `HashChainBadge`, `RbacGate`,
`RoleSwitcherChip`), BFF skeleton, and fixture directory layout.

This plan delivers the structural skeleton that every subsequent SP-1 plan layers into. No
surface is wired to a real backend yet — stubs return fixture data. The Inbox is the one
exception: it is fully functional against the mock client so operators can verify the queue
renders, filters by role, and click-throughs resolve.

---

## Scope

**In:**
- `packages/modules/paysync/` package skeleton (package.json, tsconfig, vitest config)
- `module.config.ts` — full route table, RBAC matrix, Inbox kind registrations, navTree
- `src/inbox/` — `InboxItemKind` taxonomy, `InboxItem` type, `ItemRegistry`, `InboxQueue` component, `useInboxItems` hook
- `src/components/` — `ProvenanceBreadcrumb`, `MoneyDisplay`, `MoneyInput`, `HashChainBadge`, `RbacGate`, `RoleSwitcherChip`
- `src/bff/` — BFF route skeleton (`/api/paysync/inbox`, stubs for all surface routes)
- `src/surfaces/` — one folder per surface with `index.ts` stub (12 surfaces)
- `fixtures/` — directory layout + seed JSON stubs (empty arrays; real fixture data in Plan E)
- `packages/contract` extension — `UploadsClient` interface stub + `InboxClient` interface
- `infrastructure/manifests/operator-dev.yml` — add `paysync` to `modules` list
- Unit tests for Inbox taxonomy, `RbacGate`, `MoneyDisplay`/`MoneyInput` (Decimal enforcement)

**Out:**
- Any real backend wiring (Plans B–E)
- Playwright E2E (Plan E)
- Upload resource (Plan B)
- Real fixture data in seed JSON files (Plan E)
- Hash-chain verifier endpoint (Plan D)

---

## Tasks

### Task 1 — Package scaffold

| # | Subject | Files touched | Test added | Deliverable |
|---|---|---|---|---|
| 1.1 | `package.json` for `@infinityrx/module-paysync` | `packages/modules/paysync/package.json` | — | npm workspace recognised |
| 1.2 | `tsconfig.json` extending `tsconfig.base.json` | `packages/modules/paysync/tsconfig.json` | — | `tsc -b` clean |
| 1.3 | `vitest.config.ts` | `packages/modules/paysync/vitest.config.ts` | — | `npm test` runnable |
| 1.4 | Add `packages/modules/paysync` to workspace-root `tsconfig.json` references | `tsconfig.json` | — | project reference compiles |
| 1.5 | Add `paysync` to `operator-dev.yml` modules list | `infrastructure/manifests/operator-dev.yml` | manifest validator passes | manifest valid |
| 1.6 | Add `paysync` to `infrastructure/manifests/operator.yml` if it exists, else note in commit | `infrastructure/manifests/operator.yml` (if present) | — | manifest sync |

**Step 1.1 detail — `packages/modules/paysync/package.json`:**

```json
{
  "name": "@infinityrx/module-paysync",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "main": "./src/module.config.ts",
  "exports": {
    ".": "./src/module.config.ts"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@infinityrx/contract": "*",
    "@infinityrx/auth": "*",
    "@infinityrx/ui": "*",
    "@infinityrx/qa-harness": "*"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.7.5",
    "vitest": "2.1.3",
    "@testing-library/react": "16.0.0",
    "@testing-library/user-event": "14.5.2"
  }
}
```

**Step 1.2 detail — `packages/modules/paysync/tsconfig.json`:**

```json
{
  "extends": "../../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "jsx": "react-jsx",
    "lib": ["ES2023", "DOM"]
  },
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["**/*.test.ts", "**/*.test.tsx", "dist", "node_modules"]
}
```

- [ ] Step 1.1: Write `packages/modules/paysync/package.json`
- [ ] Step 1.2: Write `packages/modules/paysync/tsconfig.json`
- [ ] Step 1.3: Write `packages/modules/paysync/vitest.config.ts` (mirror `packages/scripts/vitest.config.ts` pattern with `environment: 'jsdom'`)
- [ ] Step 1.4: Add `{ "path": "./packages/modules/paysync" }` to workspace-root `tsconfig.json` references array
- [ ] Step 1.5: Edit `infrastructure/manifests/operator-dev.yml` — add `paysync` to `modules:` array
- [ ] Step 1.6: Run `npm run manifest:validate` — confirm passes
- [ ] Step 1.7: Commit — `feat(sp-1-a): scaffold @infinityrx/module-paysync package`

---

### Task 2 — Surface skeleton (12 surfaces)

Create one folder per surface under `packages/modules/paysync/src/surfaces/` with an `index.ts`
that exports a `SurfaceConfig` stub. Each stub is a typed constant that satisfies the surface
shape — no implementation yet.

| # | Surface folder | Files created | Notes |
|---|---|---|---|
| 2.1 | `uploads/` | `index.ts` | NEW surface |
| 2.2 | `cycles/` | `index.ts` | wraps `portal/operator/app/admin/paysync/cycles/` |
| 2.3 | `batches/` | `index.ts` | wraps `portal/operator/app/admin/paysync/batches/` |
| 2.4 | `carryovers/` | `index.ts` | wraps `portal/operator/app/admin/paysync/carryovers/` |
| 2.5 | `invoices/` | `index.ts` | wraps invoices + `portal/operator/app/accounting/invoices/` |
| 2.6 | `payment-runs/` | `index.ts` | wraps `portal/operator/app/payments/batches/` + manual-ap |
| 2.7 | `files/` | `index.ts` | NEW surface |
| 2.8 | `bank-settlements/` | `index.ts` | wraps `portal/operator/app/admin/paysync/bank-settlements/` |
| 2.9 | `reconciliations/` | `index.ts` | wraps `portal/operator/app/admin/paysync/reconciliations/` |
| 2.10 | `journal/` | `index.ts` | NEW surface |
| 2.11 | `reports/` | `index.ts` | wraps `portal/operator/app/accounting/` |
| 2.12 | `setup/` | `index.ts` | wraps `portal/operator/app/admin/paysync/` setup surfaces |

Each `index.ts` template:

```ts
// packages/modules/paysync/src/surfaces/<name>/index.ts
// Stub — wired in SP-1 Plan <X>. Do not add implementation here.

export const <Name>Surface = {
  id: '<name>',
  path: '/admin/paysync/<name>',
} as const;
```

- [ ] Step 2.1–2.12: Create all 12 surface stubs
- [ ] Step 2.13: Commit — `feat(sp-1-a): surface skeleton stubs (12 surfaces)`

---

### Task 3 — Inbox spine

**Files:**
- `packages/modules/paysync/src/inbox/types.ts` — `InboxItemKind`, `InboxItem`, `RbacRole`
- `packages/modules/paysync/src/inbox/ItemRegistry.ts` — registry map
- `packages/modules/paysync/src/inbox/useInboxItems.ts` — TanStack Query hook
- `packages/modules/paysync/src/inbox/InboxQueue.tsx` — virtualized list component
- `packages/modules/paysync/src/inbox/index.ts` — barrel export
- `packages/modules/paysync/src/bff/inbox.ts` — BFF handler stub returning mock fixture data
- `packages/modules/paysync/tests/unit/inbox/types.test.ts` — discriminated-union exhaustiveness
- `packages/modules/paysync/tests/unit/inbox/InboxQueue.test.tsx` — renders, filters by role, no items state

**`types.ts` content (authoritative — do not deviate):**

```ts
// Authoritative Inbox taxonomy per SP-1 spec §5.3.
// Add new kinds here first; ItemRegistry registers the card component.

export type RbacRole = 'operator' | 'approver' | 'auditor';

export type InboxItemKind =
  | 'upload_pending_review'
  | 'upload_validated_awaiting_batching'
  | 'cycle_pending_close'
  | 'cycle_close_review'
  | 'batch_drafted'
  | 'ar_invoice_draft'
  | 'ap_payment_run_held'
  | 'banking_discrepancy'
  | 'reconciliation_pending'
  | 'carryover_open'
  | 'journal_periodic_review';

export type InboxItem = {
  readonly id: string;
  readonly kind: InboxItemKind;
  readonly tenant_id: string;
  readonly upload_id: string | null;   // provenance link; null only for journal_periodic_review
  readonly rbac_required: RbacRole;
  readonly created_at: string;         // ISO 8601
  readonly priority: 'normal' | 'high';
  readonly payload: Record<string, unknown>; // typed per kind via discriminated union in Plan B+
};

/** Maps each InboxItemKind to the role that must action it. */
export const INBOX_KIND_ROLE: Record<InboxItemKind, RbacRole> = {
  upload_pending_review:              'operator',
  upload_validated_awaiting_batching: 'operator',
  cycle_pending_close:                'operator',
  carryover_open:                     'operator',
  cycle_close_review:                 'approver',
  batch_drafted:                      'approver',
  ar_invoice_draft:                   'approver',
  ap_payment_run_held:                'approver',
  banking_discrepancy:                'approver',
  reconciliation_pending:             'approver',
  journal_periodic_review:            'auditor',
};
```

**Cache strategy (§10.5 resolved):**

`useInboxItems` uses TanStack Query with `staleTime: 10_000` (10s) and
`refetchOnWindowFocus: true`. Query key: `['paysync', 'inbox', role]`. Every mutation handler
calls `queryClient.invalidateQueries({ queryKey: ['paysync', 'inbox'] })` immediately after
success. No WebSocket in SP-1.

**BFF stub** (`src/bff/inbox.ts`): returns an empty array `[]` typed as `InboxItem[]`.
Plan B replaces the stub with a real call to `GET /api/v1/billing/inbox?role=<role>`.

**Tests:**
- `types.test.ts`: assert `INBOX_KIND_ROLE` has an entry for every value in `InboxItemKind`
  (exhaustiveness via `Object.keys` comparison). Catches kind additions that forget the role map.
- `InboxQueue.test.tsx`: render with 3 items (1 operator, 1 approver, 1 auditor); assert
  role=operator shows 1, role=approver shows 1, role=auditor shows 1; assert "No items" state
  when array is empty.

- [ ] Step 3.1: Write `src/inbox/types.ts` exactly as shown
- [ ] Step 3.2: Write `src/inbox/ItemRegistry.ts` — map of kind → lazy-loaded card component + `rbac_required`
- [ ] Step 3.3: Write `src/inbox/useInboxItems.ts` — TanStack Query hook per §10.5 resolution
- [ ] Step 3.4: Write `src/inbox/InboxQueue.tsx` — TanStack Virtual list, group by kind, filter by role
- [ ] Step 3.5: Write `src/inbox/index.ts` barrel
- [ ] Step 3.6: Write `src/bff/inbox.ts` stub
- [ ] Step 3.7: Write tests (exhaustiveness + render tests)
- [ ] Step 3.8: Run `npm --workspace=@infinityrx/module-paysync test` — all pass
- [ ] Step 3.9: Commit — `feat(sp-1-a): Inbox spine — taxonomy, registry, hook, queue component`

---

### Task 4 — Module-local shared primitives

**Files:**
- `packages/modules/paysync/src/components/ProvenanceBreadcrumb.tsx`
- `packages/modules/paysync/src/components/MoneyDisplay.tsx`
- `packages/modules/paysync/src/components/MoneyInput.tsx`
- `packages/modules/paysync/src/components/HashChainBadge.tsx`
- `packages/modules/paysync/src/components/RbacGate.tsx`
- `packages/modules/paysync/src/components/RoleSwitcherChip.tsx`
- `packages/modules/paysync/src/components/index.ts` barrel
- Tests for each primitive (unit, co-located: `*.test.tsx`)

**MoneyDisplay / MoneyInput rules** (`.claude/rules/financial-precision.md`):
- `MoneyDisplay` receives a `value: string` (Decimal serialised as string per the financial rules);
  formats with `Intl.NumberFormat` using `currency: 'USD'`. Never accepts `number` or `float`.
- `MoneyInput` validates on blur: rejects input with >4 decimal places; rejects NaN; calls
  `onChange(decimalString)` only when valid; shows inline error "Max 4 decimal places" otherwise.
- Both have 100% branch coverage tests — financial path, per Auto-Gate rules.

**RbacGate rules:**
- Props: `role: RbacRole | RbacRole[]`, `currentRole: RbacRole`, `children: React.ReactNode`
- When denied: renders children wrapped in `<span aria-disabled="true" title="<Role> role required">`;
  pointer-events: none via CSS class. Never hides. Per spec §5.4.
- 100% branch coverage required (allowed, denied, array-role match, array-role deny).

**RoleSwitcherChip rules:**
- Only exported from `@infinityrx/qa-harness` re-export path, NOT from main module barrel.
  Enforced by placing it in `src/components/dev-only/RoleSwitcherChip.tsx` and only
  re-exporting from a `qa` named export in `module.config.ts`.
- Production bundle check: CI step added in Plan E asserts
  `RoleSwitcherChip` string does not appear in any `.next/static/chunks/*.js`.

**ProvenanceBreadcrumb:**
- Props: `chain: Array<{ label: string; href: string }>` — renders as `<nav aria-label="Provenance">` with `/` separators.
- Truncates middle items at >4 nodes (shows first + last 2 with `...`).

- [ ] Step 4.1: Write all 6 primitive components + barrel
- [ ] Step 4.2: Write unit tests for each (100% branch on financial + RBAC paths)
- [ ] Step 4.3: Run tests — all pass
- [ ] Step 4.4: Commit — `feat(sp-1-a): module primitives — ProvenanceBreadcrumb, Money*, HashChainBadge, RbacGate, RoleSwitcherChip`

---

### Task 5 — `module.config.ts` entry point

**File:** `packages/modules/paysync/src/module.config.ts`

This is the composition entry point consumed by SP-0's `generate-composition.ts`. It must
satisfy the `ModuleConfig` type from `packages/shell/src/types/module-config.ts` (confirmed
on disk per SP-0 Plan D).

```ts
// packages/modules/paysync/src/module.config.ts
import type { ModuleConfig } from '@infinityrx/shell/types/module-config.js';

export default {
  id: 'paysync',
  displayName: 'PaySync',
  routes: [
    { path: '/admin/paysync',              surface: 'uploads',        label: 'Inbox'           },
    { path: '/admin/paysync/uploads',      surface: 'uploads',        label: 'Uploads'         },
    { path: '/admin/paysync/cycles',       surface: 'cycles',         label: 'Cycles'          },
    { path: '/admin/paysync/batches',      surface: 'batches',        label: 'Batches'         },
    { path: '/admin/paysync/carryovers',   surface: 'carryovers',     label: 'Carryovers'      },
    { path: '/admin/paysync/invoices',     surface: 'invoices',       label: 'Invoices'        },
    { path: '/admin/paysync/payment-runs', surface: 'payment-runs',   label: 'Payment Runs'    },
    { path: '/admin/paysync/files',        surface: 'files',          label: 'Files'           },
    { path: '/admin/paysync/settlements',  surface: 'bank-settlements',label: 'Settlements'    },
    { path: '/admin/paysync/reconcile',    surface: 'reconciliations',label: 'Reconciliations' },
    { path: '/admin/paysync/journal',      surface: 'journal',        label: 'Journal'         },
    { path: '/admin/paysync/reports',      surface: 'reports',        label: 'Reports'         },
    { path: '/admin/paysync/setup',        surface: 'setup',          label: 'Setup'           },
  ],
  rbac: {
    operator: [
      'paysync.upload', 'paysync.upload.view', 'paysync.batch.draft',
      'paysync.cycle.view', 'paysync.carryover.view', 'paysync.journal.view',
      'paysync.audit.view',
    ],
    approver: [
      'paysync.upload', 'paysync.upload.view', 'paysync.batch.draft',
      'paysync.cycle.view', 'paysync.carryover.view', 'paysync.journal.view',
      'paysync.audit.view',
      'paysync.cycle.close', 'paysync.invoice.send', 'paysync.payment_run.release',
      'paysync.nacha.generate', 'paysync.835.generate', 'paysync.reconcile.finalize',
      'paysync.discrepancy.resolve', 'paysync.manual_ap.commit', 'paysync.setup.mutate',
    ],
    auditor: [
      'paysync.read', 'paysync.upload.view', 'paysync.journal.view',
      'paysync.journal.verify', 'paysync.audit.view',
    ],
  },
  inboxItemKinds: [
    { kind: 'upload_pending_review',              card: () => import('./inbox/cards/UploadPendingReviewCard.js')    },
    { kind: 'upload_validated_awaiting_batching', card: () => import('./inbox/cards/UploadValidatedCard.js')        },
    { kind: 'cycle_pending_close',                card: () => import('./inbox/cards/CyclePendingCloseCard.js')      },
    { kind: 'cycle_close_review',                 card: () => import('./inbox/cards/CycleCloseReviewCard.js')       },
    { kind: 'batch_drafted',                      card: () => import('./inbox/cards/BatchDraftedCard.js')           },
    { kind: 'ar_invoice_draft',                   card: () => import('./inbox/cards/ArInvoiceDraftCard.js')         },
    { kind: 'ap_payment_run_held',                card: () => import('./inbox/cards/ApPaymentRunHeldCard.js')       },
    { kind: 'banking_discrepancy',                card: () => import('./inbox/cards/BankingDiscrepancyCard.js')     },
    { kind: 'reconciliation_pending',             card: () => import('./inbox/cards/ReconciliationPendingCard.js')  },
    { kind: 'carryover_open',                     card: () => import('./inbox/cards/CarryoverOpenCard.js')          },
    { kind: 'journal_periodic_review',            card: () => import('./inbox/cards/JournalPeriodicReviewCard.js')  },
  ],
  navTree: {
    primary: [
      { label: 'Inbox',    path: '/admin/paysync',             icon: 'inbox'      },
      { label: 'History',  path: '/admin/paysync/uploads',     icon: 'clock'      },
      { label: 'Journal',  path: '/admin/paysync/journal',     icon: 'book-open'  },
      { label: 'Reports',  path: '/admin/paysync/reports',     icon: 'bar-chart'  },
      { label: 'Setup',    path: '/admin/paysync/setup',       icon: 'settings'   },
    ],
  },
  // qa-harness export — tree-shaken from production bundles per spec §6.6
  qa: {
    RoleSwitcherChip: () => import('./components/dev-only/RoleSwitcherChip.js'),
  },
} satisfies ModuleConfig;
```

**Inbox card stubs** (Plan A creates empty card stubs; Plans B/C/D/E replace with real components):
Create `src/inbox/cards/<Name>.tsx` for each of the 11 kinds — each renders a one-line
`<div>` with the kind name. These satisfy the dynamic import references in `module.config.ts`.

- [ ] Step 5.1: Write `src/module.config.ts` exactly as shown
- [ ] Step 5.2: Create 11 card stubs under `src/inbox/cards/`
- [ ] Step 5.3: Verify `tsc -b` clean
- [ ] Step 5.4: Commit — `feat(sp-1-a): module.config.ts entry point + 11 inbox card stubs`

---

### Task 6 — Contract extension + fixtures layout

**Contract extension** (`packages/contract`):
Add `src/paysync/uploads-client.ts` with the `UploadsClient` interface stub (methods: `list`,
`get`, `create`, `getClaims`) and `src/paysync/inbox-client.ts` with `InboxClient` interface
(`list`). Both have `RealImpl` and `MockImpl` classes — `MockImpl` returns typed empty
arrays/fixtures. Pattern mirrors existing `paysync-api.ts` in `portal/shared/lib/`.

**Fixtures layout:**
```
packages/modules/paysync/fixtures/
  uploads/
    upload-001-healthy.csv        ← 20 valid claims (real data in Plan E)
    upload-002-validation-fail.csv ← 20 invalid rows (real data in Plan E)
    upload-003-half-bad.csv       ← 30 rows mixed (real data in Plan E)
  seeds/
    tenant.json                   ← {} stub
    cycles.json                   ← [] stub
    invoices.json                 ← [] stub
    payment-runs.json             ← [] stub
    reconciliations.json          ← [] stub
    users.json                    ← [] stub
```

CSV stubs contain only header rows in Plan A. Real data populates in Plan E.

- [ ] Step 6.1: Add `UploadsClient` + `InboxClient` to `packages/contract/src/paysync/`
- [ ] Step 6.2: Create fixtures directory layout with header-only CSV stubs + empty JSON stubs
- [ ] Step 6.3: Verify contract package still typechecks (`tsc -b`)
- [ ] Step 6.4: Commit — `feat(sp-1-a): contract extensions (UploadsClient, InboxClient) + fixtures layout`

---

## Gate Criteria

Plan A is complete when ALL of the following are true:

- [ ] `npm run typecheck` exits 0 (all workspace project references compile)
- [ ] `npm --workspace=@infinityrx/module-paysync test` — all tests pass, 0 failing
- [ ] Coverage gates: 100% branch on `MoneyDisplay`, `MoneyInput`, `RbacGate` (financial + security paths); ≥95% on Inbox components
- [ ] `npm run manifest:validate` exits 0 with `paysync` in modules list
- [ ] `packages/modules/paysync/src/module.config.ts` exports a value satisfying `ModuleConfig` (tsc confirms)
- [ ] All 11 inbox card stubs exist and dynamic imports in `module.config.ts` resolve
- [ ] All 12 surface `index.ts` stubs exist
- [ ] Fixtures directory layout exists with 3 CSV stubs + 6 JSON stubs (even if stub content)
- [ ] `UploadsClient` and `InboxClient` interfaces present in `packages/contract/`
- [ ] No `RoleSwitcherChip` in module's main barrel export (checked by grep in commit hook)

---

## Deliverables

- `packages/modules/paysync/` — fully typed SP-0-conformant module package, compilable, testable
- `module.config.ts` — composition entry point consumed by `generate-composition.ts` in Plan D
- Complete Inbox taxonomy (`InboxItemKind`, `INBOX_KIND_ROLE`) — extensible without refactor
- All 6 module-local primitives — usable by Plans B–E immediately
- BFF route skeleton — Plans B–E fill in real handlers
- Contract interfaces — Plans B–E provide real implementations
- Fixtures skeleton — Plan E populates real synthetic data

---

## Dependencies

- SP-0 Plans A–D fully executed (packages/contract, packages/auth, packages/ui, packages/shell all present)
- `packages/shell/src/types/module-config.ts` exists and exports `ModuleConfig` type (SP-0 Plan D)
- `@tanstack/react-query` present in `packages/ui` or `packages/contract` (SP-0 Plan C/D)
- `@tanstack/react-virtual` present (SP-0 Plan C)

---

## Cross-references

- Spec §5.1 (layering), §5.3 (Inbox spine), §5.4 (RBAC matrix), §5.6 (SP-0 consumed), §6.1 (inbox components), §6.6 (module.config.ts), §6.6 (RoleSwitcherChip production exclusion), §10 (plan-time decisions)
- Rules: `.claude/rules/financial-precision.md` (MoneyDisplay/Input), `.claude/rules/security.md` (RbacGate), `.claude/rules/testing.md` (100% financial/security coverage), `.claude/rules/architecture.md` (module structure), `.claude/rules/code-standards.md` (dead code ban)
- SP-0 Plan D: `docs/superpowers/plans/2026-05-15-sp0-plan-d-composition-portal-wiring.md`
- SP-1 Plans B–E: depend on all deliverables above
