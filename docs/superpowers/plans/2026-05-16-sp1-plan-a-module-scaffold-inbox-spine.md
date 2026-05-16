# SP-1 Plan A — Module Scaffold + Inbox Spine

**Date:** 2026-05-16
**Sub-project:** SP-1 PaySync Operator Portal
**Status:** Ready for execution (R4 — addresses 3rd pre-execute codex NO-GO of 2026-05-16; 4 items resolved on top of R3)
**Depends on:** SP-0 Plans A–D (packages/contract, packages/auth, packages/ui, packages/qa-harness, packages/shell all shipped). Verified: `packages/{auth,contract,modules,qa-harness,scripts,shell,ui}/` all present at HEAD `d9c69152`.

---

## R4 Revision Summary (3rd pre-execute codex NO-GO fixes)

After R3, codex re-review returned NO-GO with 4 remaining items. R4 fixes each:

| # | Issue | Fix |
|---|---|---|
| R4.1 | R3.1 historical-reference inconsistency: Plan A's R1/R2 fix-summary table cells still cited the OLD plural `clients` form (`packages/contract/src/impls/paysync/{types,clients,real,mock}.ts` at file lines 31 & 75) while Task 6 + gates used the singular `client`. Reads as internal inconsistency. | Update both historical cells to use the singular `client` form to match the corrected Task 6 spec. The R1/R2 history now consistently describes "Plan A used `clients.ts` plural → corrected to `client.ts` singular in R3." |
| R4.2 | Task 1 vitest gate is not atomic: shown vitest config lacks `passWithNoTests: true`. Vitest fails by default when no tests are found. Task 1's "exits 0" claim is wrong. | Add `passWithNoTests: true` to `vitest.config.ts` (Task 1.3). Task 1's commit then truly is independently verifiable. Subsequent task commits add tests and the flag becomes a no-op. |
| R4.3 | Task 3 deferred-failure risk: `ItemRegistry.ts` was instructed to import card modules whose stub files only land in Task 5 — Task 3's commit had unresolved dynamic imports. Task 3 gate ran tests but not `tsc -b`. | Make Task 3's `ItemRegistry.ts` self-contained: typed registry map with inline placeholder card factories (`card: async () => ({ default: () => null })`). Task 5 replaces these with real dynamic imports + creates the 11 card stubs in the same commit. Task 3's commit now passes `tsc -b` independently. |
| R4.4 | Echo handling conflicts with inventory §200: inventory says "wrap into `packages/modules/paysync/src/surfaces/echo/` (NEW surface, add to the surface mapping in Plan A/B/E)." R3 deferred ALL echo work to Plan E. | Add `echo` as 13th surface stub in Plan A Task 2 (typed SurfaceConfig only; no implementation). Inbox kind `echo_run_status_received` + EchoClient wrapping still land in Plan E §6 (BFF returns empty in Plan A anyway, so the card stub isn't useful until Plan E wires the backend). |

## R3 Revision Summary (2nd pre-execute codex NO-GO fixes)

After R2, codex re-review returned NO-GO with 3 remaining items. R3 fixes each:

| # | Issue | Fix |
|---|---|---|
| R3.1 | Contract file naming: R2 used `impls/paysync/clients.ts` (plural); HEAD convention per PD is `client.ts` (singular). | Rename to `client.ts` holding BOTH `UploadsClient` + `InboxClient` interfaces in one file. Future plans (B/C/D/E) may append more client interfaces to the same file OR add `<domain>-client.ts` siblings. |
| R3.2 | Cross-plan path consistency: Plans B/C/D/E all reference the OLD `packages/contract/src/paysync/` path (without `impls/`). | Normalize all 4 sibling plans in the same commit: `packages/contract/src/paysync/` → `packages/contract/src/impls/paysync/` everywhere. |
| R3.3 | Task 1 atomicity: R2 added root `tsconfig.json` reference + manifest `modules:` entry in Task 1's commit, before `module.config.ts` exists at root, making both `typecheck` and `manifest:validate` fail-by-design at Task 1 boundary. That's a deferred-failure commit, not atomic. | Move Task 1.4 (root tsconfig reference) and Task 1.5 (manifest modules entry) into Task 5 (the commit that lands `module.config.ts`). Task 1's commit then only adds the new package's own files + npm install — independently verifiable (the new package's own `tsc -b` runs against just `src/` files; nothing breaks at the root). |

## R2 Revision Summary (1st pre-execute codex NO-GO fixes)

Pre-execute codex returned NO-GO with 6 items. R2 addresses each:

| # | Issue | Fix |
|---|---|---|
| 1 | `src/module.config.ts` with `export default` is incompatible with HEAD tooling (build-manifest, audit-module-graph, generate-eslint-zones all glob `packages/modules/*/module.config.ts` and import the named `config` export). | Move to root `packages/modules/paysync/module.config.ts`. Use `export const config = {...} as const;` matching `prescriber-directory/module.config.ts`. SD-4 shape from `packages/scripts/build-manifest.ts:36-77` interface `ModuleConfig`. |
| 2 | Plan A invented `packages/shell/src/types/module-config.ts` and an `@infinityrx/shell/types/module-config.js` package export that does not exist. Adding a sub-path export would require editing `packages/shell/package.json`. | DROP entirely. No shared `ModuleConfig` type needed. PD doesn't import one; `as const` on the literal is enough. Manifest tool reads the literal via dynamic import. |
| 3 | `@tanstack/react-query` and `@tanstack/react-virtual` cited by `useInboxItems`/`InboxQueue` are absent from root, `packages/ui`, `packages/contract`. Plan A's package.json did not add them. | Add `@tanstack/react-query@5.59.20` and `@tanstack/react-virtual@3.10.8` to `packages/modules/paysync/package.json` dependencies. Add React peer deps. |
| 4 | Plan A claimed "complete folder skeleton" but omitted the `echo/` surface that wraps real operational functionality (`portal/operator/app/admin/paysync/echo/`, inventory §9). | Explicitly defer `echo/` to Plan E §6 (which already wraps it). Plan A scope = 12 surfaces; gate criterion does NOT claim echo coverage. |
| 5 | Task 2.6 cited `portal/operator/app/payments/manual-ap` — does not exist. Real path is `portal/operator/app/admin/paysync/manual-ap`. | Fix Task 2.6 wrapping note. |
| 6 | Plan A's contract extension at `packages/contract/src/paysync/*` doesn't match HEAD convention (`packages/contract/src/impls/<domain>/{types,client,real,mock}.ts` + named exports from `index.ts`, per `prescriber-directory`). Gate only checked file presence, not exportability. | Restructure Task 6 to `packages/contract/src/impls/paysync/{types,client,real,mock}.ts` (singular `client.ts` per R3 fix) + add named exports to `packages/contract/src/index.ts`. Gate requires factories instantiable in test, not just files present. |

---

## §10 Plan-Time Decisions Resolved in This Plan

| # | Decision | Resolution | Owned by |
|---|---|---|---|
| §10.1 | Plan phasing strategy | 5 plans: A=scaffold+inbox, B=uploads+cycles, C=batches+AR/AP, D=files+journal, E=reports+setup+E2E+echo | Plan A (this) |
| §10.2 | Upload file storage strategy | Local disk under `{PAYSYNC_UPLOAD_DIR}/{tenant_id}/{upload_id}/{original_filename}`; configurable via env; 90-day retention via nightly cleanup job | Plan B |
| §10.3 | CSV/Excel minimum schema | 8 mandatory columns: `ndc, npi, claim_id, date_of_service, quantity, days_supply, amount_billed, member_id`; `source_platform` optional; per-row errors never abort other rows | Plan B |
| §10.4 | Hash-chain verifier perf budget | ≤10 000 entries sync (<5s); >10 000 returns `{verified: null, too_large: true, job_id}`; threshold via `PAYSYNC_HASH_CHAIN_SYNC_LIMIT` | Plan D |
| §10.5 | Inbox cache strategy | TanStack Query `staleTime: 10_000`, `refetchOnWindowFocus: true`; mutations `invalidateQueries(['paysync','inbox'])` immediately; no WebSocket in SP-1 | Plan A (this) |
| §10.6 | Module-extraction sequence | Extract-per-surface as wired (Plans B/C/D/E). Plan A creates skeleton folders with `index.ts` stubs; subsequent plans fill assigned surfaces; original portal pages deleted in Plan E after E2E passes | Plan A (this) |

---

## Goal

Establish `packages/modules/paysync/` as a fully typed SP-0-conformant module package with the
complete folder skeleton, root `module.config.ts` (SD-4 shape + paysync runtime composition),
the Inbox spine (typed taxonomy, `useInboxItems` hook, `InboxQueue` component, `ItemRegistry`),
all module-local shared primitives (`ProvenanceBreadcrumb`, `MoneyDisplay`, `MoneyInput`,
`HashChainBadge`, `RbacGate`, `RoleSwitcherChip`), BFF skeleton, and fixture directory layout.

This plan delivers the structural skeleton that every subsequent SP-1 plan layers into. No
surface is wired to a real backend yet — stubs return fixture data. The Inbox is the one
exception: it is fully functional against the mock client so operators can verify the queue
renders, filters by role, and click-throughs resolve.

---

## Scope

**In:**
- `packages/modules/paysync/` package skeleton (`package.json`, `tsconfig.json`, `vitest.config.ts`)
- `packages/modules/paysync/module.config.ts` (root, SD-4 shape) — named `config` export + sibling `paysyncComposition` export (rbac, inbox kinds, route-to-surface map, navTree, qa)
- `src/index.ts` — module public surface (Inbox types, primitives, surface configs, factory glue)
- `src/inbox/` — `InboxItemKind` taxonomy, `InboxItem` type, `ItemRegistry`, `InboxQueue` component, `useInboxItems` hook, 11 typed card stubs
- `src/components/` — `ProvenanceBreadcrumb`, `MoneyDisplay`, `MoneyInput`, `HashChainBadge`, `RbacGate`, `RoleSwitcherChip` (under `dev-only/`)
- `src/types/surface.ts` — `SurfaceConfig` type (module-local; not shared in `@infinityrx/shell`)
- `src/bff/inbox.ts` — BFF stub returning `[]` typed as `InboxItem[]` (real impl Plan B)
- `src/surfaces/` — 13 surface folders (R4: includes `echo/`) with `index.ts` stubs exporting typed `SurfaceConfig` constants
- `fixtures/` — directory layout + header-only CSV stubs + empty-array JSON stubs (real data in Plan E)
- `packages/contract/src/impls/paysync/` — `{types,client,real,mock}.ts` (singular `client.ts`) matching `prescriber-directory` pattern; named exports from `packages/contract/src/index.ts`
- `infrastructure/manifests/operator-dev.yml` — add `paysync` to `modules` list
- Root `tsconfig.json` references — add `{ "path": "./packages/modules/paysync" }`
- Root `package.json` `test:packages` — add `&& npm --workspace=@infinityrx/module-paysync test`
- Unit tests for Inbox taxonomy exhaustiveness, `InboxQueue` render, `RbacGate`, `MoneyDisplay`/`MoneyInput` (Decimal enforcement)

**Out:**
- Any real backend wiring (Plans B–E)
- `echo/` Inbox item kind (`echo_run_status_received`), `EchoClient` in contract, page wrapping — DEFERRED to Plan E §6. R4: surface folder + typed stub for `echo` IS in Plan A scope per inventory §200; only the live backend wiring is deferred.
- Playwright E2E (Plan E)
- Upload resource backend (Plan B)
- Real fixture data in seed JSON files (Plan E)
- Hash-chain verifier endpoint (Plan D)
- Any change to `packages/shell/` exports — not needed; PD doesn't, paysync doesn't

---

## Tasks

### Task 1 — Package scaffold (self-contained, independently verifiable)

R3 atomicity fix: Task 1 commits ONLY the new package's own files + workspace lockfile refresh. Root `tsconfig.json` references and manifest `modules:` entry move to Task 5 (the commit that lands `module.config.ts`), so Task 1 has no deferred-failure gates.

| # | Subject | Files touched | Deliverable |
|---|---|---|---|
| 1.1 | `package.json` for `@infinityrx/module-paysync` | `packages/modules/paysync/package.json` | npm workspace recognised on next install |
| 1.2 | `tsconfig.json` extending `tsconfig.base.json` + refs to shell/contract/auth/ui/qa-harness | `packages/modules/paysync/tsconfig.json` | new package's own `tsc -b` runs against `src/` only (no `module.config.ts` root file yet — `tsconfig.json` `include` adds it but file is empty/absent; tsc skips missing optional includes) |
| 1.3 | `vitest.config.ts` mirroring PD pattern with `environment: 'happy-dom'` + workspace aliases | `packages/modules/paysync/vitest.config.ts` | `npm --workspace=@infinityrx/module-paysync test` discoverable (returns "no tests" — no tests authored yet; that's fine for Task 1's commit) |
| 1.4 | Append `&& npm --workspace=@infinityrx/module-paysync test` to root `package.json` `test:packages` script | `package.json` | CI picks up paysync tests (script edit only; running it currently returns "no tests" gracefully) |

**Step 1.1 — `packages/modules/paysync/package.json`:**

```json
{
  "name": "@infinityrx/module-paysync",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/src/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@infinityrx/auth": "*",
    "@infinityrx/contract": "*",
    "@infinityrx/qa-harness": "*",
    "@infinityrx/shell": "*",
    "@infinityrx/ui": "*",
    "@tanstack/react-query": "5.59.20",
    "@tanstack/react-virtual": "3.10.8"
  },
  "peerDependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  },
  "devDependencies": {
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.5.2",
    "@types/node": "22.7.5",
    "@types/react": "19.1.2",
    "@types/react-dom": "19.1.2",
    "happy-dom": "15.11.7",
    "react": "19.2.6",
    "react-dom": "19.2.6",
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

Notes:
- `exports` points at `./dist/src/index.js` (compiled JS) matching PD. Tooling reads `module.config.ts` at root via file-path glob, NOT via package export.
- `@infinityrx/shell` dep is declared even though we don't import a sub-path; we use it for type-only re-exports if needed in Plan B+. Including it now prevents adding it later as a noisy edit.
- React + tanstack pinned to versions compatible with the rest of the workspace (shell uses 19.2.6 / tanstack-query not yet present elsewhere; verify no peer-dep conflicts with `npm install`).
- Co-located test files (`*.test.tsx`) and `__tests__/` are both picked up by vitest default discovery.

**Step 1.2 — `packages/modules/paysync/tsconfig.json`:**

```json
{
  "extends": "../../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": ".",
    "jsx": "react-jsx",
    "lib": ["ES2023", "DOM", "DOM.Iterable"]
  },
  "references": [
    { "path": "../../auth" },
    { "path": "../../contract" },
    { "path": "../../qa-harness" },
    { "path": "../../shell" },
    { "path": "../../ui" }
  ],
  "include": ["src/**/*.ts", "src/**/*.tsx", "module.config.ts"],
  "exclude": ["**/*.test.ts", "**/*.test.tsx", "__tests__/**", "dist", "node_modules"]
}
```

**Step 1.3 — `packages/modules/paysync/vitest.config.ts`** (mirror PD with happy-dom + workspace aliases):

```ts
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@infinityrx/contract": resolve(here, "../../contract/src/index.ts"),
      "@infinityrx/auth":     resolve(here, "../../auth/src/index.ts"),
      "@infinityrx/ui":       resolve(here, "../../ui/src/index.ts"),
      "@infinityrx/shell":    resolve(here, "../../shell/src/index.ts"),
      "@infinityrx/qa-harness": resolve(here, "../../qa-harness/src/index.ts"),
    },
  },
  test: {
    include: ["__tests__/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"],
    environment: "happy-dom",
    // R4 atomicity: Task 1's commit ships no tests yet (added in Tasks 3–6).
    // Without this flag, vitest exits non-zero on empty test discovery and
    // Task 1's gate would fail by design. Tests added later don't change behavior.
    passWithNoTests: true,
  },
});
```

- [ ] Step 1.1: Write `packages/modules/paysync/package.json` (literal content above)
- [ ] Step 1.2: Write `packages/modules/paysync/tsconfig.json` (literal content above)
- [ ] Step 1.3: Write `packages/modules/paysync/vitest.config.ts` (literal content above)
- [ ] Step 1.4: Edit root `package.json` — append `&& npm --workspace=@infinityrx/module-paysync test` to `test:packages` script
- [ ] Step 1.5: `npm install` to refresh workspace lockfile (introduces `@tanstack/react-query@5.59.20` + `@tanstack/react-virtual@3.10.8`; verify no peer-dep conflicts)
- [ ] Step 1.6: `npm --workspace=@infinityrx/module-paysync test` — exits 0 (returns "no tests" cleanly; vitest discoverable)
- [ ] Step 1.7: Commit — `feat(sp-1-a): scaffold @infinityrx/module-paysync package`

**Gate for Task 1 commit (independently verifiable):**
- New package is registered as a workspace (verify: `npm ls --workspace=@infinityrx/module-paysync` resolves).
- `package.json` parses (verify: `node -e "JSON.parse(require('fs').readFileSync('packages/modules/paysync/package.json','utf8'))"`).
- `npm install` succeeded with no peer-dep errors.
- Root `tsconfig.json` and `infrastructure/manifests/operator-dev.yml` are UNCHANGED at this commit boundary (they update in Task 5's commit when `module.config.ts` lands). This keeps Task 1's commit fully self-contained — `npm run typecheck` and `npm run manifest:validate` continue to pass against the prior baseline.

---

### Task 2 — Surface skeleton (13 surfaces)

Create one folder per surface under `packages/modules/paysync/src/surfaces/` with an `index.ts`
that exports a typed `SurfaceConfig` constant. Each stub is a typed constant that satisfies the
`SurfaceConfig` shape — no implementation yet.

| # | Surface folder | Wraps existing portal route | Notes |
|---|---|---|---|
| 2.1 | `uploads/` | — | NEW surface |
| 2.2 | `cycles/` | `portal/operator/app/admin/paysync/cycles/` | |
| 2.3 | `batches/` | `portal/operator/app/admin/paysync/batches/` | |
| 2.4 | `carryovers/` | `portal/operator/app/admin/paysync/carryovers/` | |
| 2.5 | `invoices/` | `portal/operator/app/admin/paysync/invoices/` + `portal/operator/app/accounting/invoices/` | |
| 2.6 | `payment-runs/` | `portal/operator/app/payments/batches/` + `portal/operator/app/admin/paysync/manual-ap/` | (R2 FIX — `manual-ap` is under `admin/paysync/`, not `payments/`) |
| 2.7 | `files/` | — | NEW surface |
| 2.8 | `bank-settlements/` | `portal/operator/app/admin/paysync/bank-settlements/` | |
| 2.9 | `reconciliations/` | `portal/operator/app/admin/paysync/reconciliations/` | |
| 2.10 | `journal/` | — | NEW surface |
| 2.11 | `reports/` | `portal/operator/app/accounting/` | |
| 2.12 | `setup/` | `portal/operator/app/admin/paysync/{cycle-schedules,email-recipients,email-templates,export-templates,gl-account-mappings,invoice-sequences}/` | aggregates setup surfaces |
| 2.13 | `echo/` | `portal/operator/app/admin/paysync/echo/` | **R4 FIX (inventory §200):** typed SurfaceConfig stub created in Plan A. Inbox kind `echo_run_status_received` + `EchoClient` wrapping + actual page logic land in Plan E §6 (BFF returns empty in Plan A; card stub not useful until backend wired). |

**`SurfaceConfig` type** (`src/types/surface.ts`):

```ts
// Module-local type for surface descriptors. Not shared via @infinityrx/shell —
// surfaces are an internal composition concern of paysync.
export interface SurfaceConfig {
  readonly id: string;
  readonly path: string;
}
```

Each `src/surfaces/<name>/index.ts` template:

```ts
// packages/modules/paysync/src/surfaces/<name>/index.ts
// Stub — wired in SP-1 Plan <X>. Do not add implementation here.
import type { SurfaceConfig } from "../../types/surface.js";

export const <Name>Surface: SurfaceConfig = {
  id: "<name>",
  path: "/admin/paysync/<name>",
};
```

- [ ] Step 2.0: Write `src/types/surface.ts` with `SurfaceConfig` type
- [ ] Step 2.1–2.13: Create all 13 surface stubs (each typed as `SurfaceConfig`, NOT empty objects; includes `echo/` per R4 inventory alignment)
- [ ] Step 2.14: `npm --workspace=@infinityrx/module-paysync exec tsc -b` exits 0 in module (proves all surface stubs satisfy `SurfaceConfig` shape)
- [ ] Step 2.15: Commit — `feat(sp-1-a): surface skeleton stubs (13 surfaces; echo Plan-E-wraps backend)`

---

### Task 3 — Inbox spine

**Files:**
- `packages/modules/paysync/src/inbox/types.ts` — `InboxItemKind`, `InboxItem`, `RbacRole`, `INBOX_KIND_ROLE`
- `packages/modules/paysync/src/inbox/ItemRegistry.ts` — registry map (kind → lazy card import + rbac_required)
- `packages/modules/paysync/src/inbox/useInboxItems.ts` — TanStack Query hook
- `packages/modules/paysync/src/inbox/InboxQueue.tsx` — virtualized list component
- `packages/modules/paysync/src/inbox/index.ts` — barrel export
- `packages/modules/paysync/src/bff/inbox.ts` — BFF handler STUB returning `[]: InboxItem[]`
- `packages/modules/paysync/__tests__/inbox/types.test.ts` — exhaustiveness check
- `packages/modules/paysync/__tests__/inbox/InboxQueue.test.tsx` — renders, filters by role, no-items state

**`types.ts` content (authoritative — do not deviate):**

```ts
// Authoritative Inbox taxonomy per SP-1 spec §5.3.
// Add new kinds here first; ItemRegistry registers the card component.

export type RbacRole = "operator" | "approver" | "auditor";

export type InboxItemKind =
  | "upload_pending_review"
  | "upload_validated_awaiting_batching"
  | "cycle_pending_close"
  | "cycle_close_review"
  | "batch_drafted"
  | "ar_invoice_draft"
  | "ap_payment_run_held"
  | "banking_discrepancy"
  | "reconciliation_pending"
  | "carryover_open"
  | "journal_periodic_review";

export type InboxItem = {
  readonly id: string;
  readonly kind: InboxItemKind;
  readonly tenant_id: string;
  readonly upload_id: string | null;
  readonly rbac_required: RbacRole;
  readonly created_at: string;
  readonly priority: "normal" | "high";
  readonly payload: Record<string, unknown>;
};

export const INBOX_KIND_ROLE: Record<InboxItemKind, RbacRole> = {
  upload_pending_review:              "operator",
  upload_validated_awaiting_batching: "operator",
  cycle_pending_close:                "operator",
  carryover_open:                     "operator",
  cycle_close_review:                 "approver",
  batch_drafted:                      "approver",
  ar_invoice_draft:                   "approver",
  ap_payment_run_held:                "approver",
  banking_discrepancy:                "approver",
  reconciliation_pending:             "approver",
  journal_periodic_review:            "auditor",
};
```

**Cache strategy (§10.5 resolved):**

`useInboxItems` uses TanStack Query with `staleTime: 10_000` (10s) and
`refetchOnWindowFocus: true`. Query key: `['paysync', 'inbox', role]`. Every mutation handler
calls `queryClient.invalidateQueries({ queryKey: ['paysync', 'inbox'] })` immediately after
success. No WebSocket in SP-1.

**BFF stub** (`src/bff/inbox.ts`): returns `[] as InboxItem[]`. **This is a stub — NOT a complete
Inbox implementation.** Plan B replaces it with a real call to the backend Upload + Inbox routes.
The Plan A gate criterion below explicitly accepts this as stub-scope.

**Tests:**
- `types.test.ts`: assert `Object.keys(INBOX_KIND_ROLE)` matches every value in the `InboxItemKind`
  union (literal string equality on a sorted array). Catches additions that forget the role map.
- `InboxQueue.test.tsx`: render with 3 items (1 operator, 1 approver, 1 auditor); assert
  role=operator filter shows 1, role=approver shows 1, role=auditor shows 1; assert "No items"
  state when array is empty.

- [ ] Step 3.1: Write `src/inbox/types.ts` exactly as shown
- [ ] Step 3.2: Write `src/inbox/ItemRegistry.ts` — **self-contained map** of `InboxItemKind → { card: () => Promise<{ default: React.ComponentType<{ item: InboxItem }> }>; rbac_required: RbacRole }`. Each entry uses an INLINE placeholder card factory: `card: async () => ({ default: () => null })`. R4 fix: NO imports of `../inbox/cards/*.js` at this commit boundary — those files don't exist until Task 5. Task 5 replaces the inline placeholders with real `import("./cards/<Name>Card.js")` calls in the same commit that creates the 11 stub files.
- [ ] Step 3.3: Write `src/inbox/useInboxItems.ts` — `function useInboxItems(role: RbacRole)` returns TanStack Query result; calls `fetch('/api/paysync/inbox?role=' + role)` for now (BFF route added in Plan A; real backend in Plan B)
- [ ] Step 3.4: Write `src/inbox/InboxQueue.tsx` — uses `@tanstack/react-virtual` for virtualization; props `{ items: InboxItem[]; role: RbacRole }`; filters `items.filter(i => i.rbac_required === role)`; renders via `ItemRegistry`
- [ ] Step 3.5: Write `src/inbox/index.ts` barrel (re-export types, hook, component, registry)
- [ ] Step 3.6: Write `src/bff/inbox.ts` stub returning `[] as InboxItem[]`
- [ ] Step 3.7: Write `__tests__/inbox/types.test.ts` (exhaustiveness) and `__tests__/inbox/InboxQueue.test.tsx` (render + filter + empty)
- [ ] Step 3.8: `npm --workspace=@infinityrx/module-paysync exec tsc -b` exits 0 (R4 atomicity: proves no unresolved imports in `ItemRegistry.ts`)
- [ ] Step 3.9: `npm --workspace=@infinityrx/module-paysync test` — all pass
- [ ] Step 3.10: Commit — `feat(sp-1-a): Inbox spine — taxonomy, self-contained registry, hook, queue component`

---

### Task 4 — Module-local shared primitives

**Files:**
- `packages/modules/paysync/src/components/ProvenanceBreadcrumb.tsx`
- `packages/modules/paysync/src/components/MoneyDisplay.tsx`
- `packages/modules/paysync/src/components/MoneyInput.tsx`
- `packages/modules/paysync/src/components/HashChainBadge.tsx`
- `packages/modules/paysync/src/components/RbacGate.tsx`
- `packages/modules/paysync/src/components/dev-only/RoleSwitcherChip.tsx` (qa-only)
- `packages/modules/paysync/src/components/index.ts` barrel (excludes `dev-only/`)
- Co-located unit tests (`*.test.tsx`) for each primitive — picked up by vitest default discovery

**MoneyDisplay / MoneyInput rules** (`.claude/rules/financial-precision.md`):
- `MoneyDisplay` receives `value: string` (Decimal serialised as string per financial rules);
  formats with `Intl.NumberFormat` using `currency: 'USD'`. Never accepts `number` or `float`.
- `MoneyInput` validates on blur: rejects input with >4 decimal places; rejects NaN; calls
  `onChange(decimalString)` only when valid; shows inline error "Max 4 decimal places" otherwise.
- Both: 100% branch coverage — financial path per Auto-Gate.

**RbacGate rules** (`.claude/rules/security.md`):
- Props: `role: RbacRole | RbacRole[]`, `currentRole: RbacRole`, `children: React.ReactNode`
- When denied: renders children wrapped in `<span aria-disabled="true" title="<Role> role required">`;
  `pointer-events: none` via CSS class. Never hides. Per spec §5.4.
- 100% branch coverage required (allowed, denied, array-role match, array-role deny).

**RoleSwitcherChip rules:**
- Lives under `src/components/dev-only/RoleSwitcherChip.tsx`. NOT exported from main `components/index.ts`.
- Plan A's gate has a grep check: `! grep -r "RoleSwitcherChip" packages/modules/paysync/src/components/index.ts`.
- Re-export from `paysyncComposition.qa.RoleSwitcherChip` in `module.config.ts` (Task 5) for qa-harness consumption.
- Production bundle check (CI step added in Plan E) asserts string does not appear in any `.next/static/chunks/*.js`.

**ProvenanceBreadcrumb:**
- Props: `chain: Array<{ label: string; href: string }>` — renders as `<nav aria-label="Provenance">` with `/` separators.
- Truncates middle items at >4 nodes (shows first + last 2 with `...`).

**HashChainBadge:**
- Props: `{ verified: boolean | null; tooLarge?: boolean }` — renders one of: green ✓ verified, red ✗ failed, amber ⚠ too-large-deferred, gray spinner if `verified === null && !tooLarge`.

- [ ] Step 4.1: Write 6 primitive components + barrel (barrel excludes `dev-only/`)
- [ ] Step 4.2: Write co-located unit tests (`MoneyDisplay.test.tsx`, etc.) — 100% branch on `MoneyDisplay`, `MoneyInput`, `RbacGate`
- [ ] Step 4.3: `npm --workspace=@infinityrx/module-paysync test -- --coverage` — verify 100% branch on financial + RBAC paths
- [ ] Step 4.4: `grep -r "RoleSwitcherChip" packages/modules/paysync/src/components/index.ts` — returns no matches (barrel does not export qa-only chip)
- [ ] Step 4.5: Commit — `feat(sp-1-a): module primitives — ProvenanceBreadcrumb, Money*, HashChainBadge, RbacGate, RoleSwitcherChip`

---

### Task 5 — `module.config.ts` (root) + 11 typed card stubs

**File:** `packages/modules/paysync/module.config.ts` (ROOT — not `src/`)

**R2 fix:** Plan A no longer creates `packages/shell/src/types/module-config.ts`. The SD-4
`ModuleConfig` interface lives in `packages/scripts/build-manifest.ts:36-77` and is read
structurally by tooling — no shared type import is needed; `as const` on the literal is
sufficient (matches `prescriber-directory/module.config.ts`).

**Two exports in this file:**
1. `export const config = {...} as const;` — SD-4 shape consumed by build-manifest, audit-module-graph, generate-eslint-zones
2. `export const paysyncComposition = {...} as const;` — runtime composition (rbac matrix, inbox kinds, route-to-surface map, navTree, qa) consumed by SP-1 surface mounting + qa-harness; NOT inspected by SD-4 tooling

```ts
// packages/modules/paysync/module.config.ts
// SP-1 PaySync module config.
// `config` follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts).
// `paysyncComposition` is paysync-specific runtime composition (rbac, inbox kinds, etc.).

export const config = {
  name: "paysync",
  routes: [
    "/admin/paysync",
    "/admin/paysync/uploads",
    "/admin/paysync/cycles",
    "/admin/paysync/batches",
    "/admin/paysync/carryovers",
    "/admin/paysync/invoices",
    "/admin/paysync/payment-runs",
    "/admin/paysync/files",
    "/admin/paysync/settlements",
    "/admin/paysync/reconcile",
    "/admin/paysync/journal",
    "/admin/paysync/reports",
    "/admin/paysync/setup",
  ],
  navEntry: {
    label: "PaySync",
    icon: "credit-card",
    order: 20,
  },
  requires: {
    backends: ["billing", "payment-processing", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["billing_v1", "payment_processing_v1", "core_v1"],
    migrations: ["core", "billing", "payment-processing"],
    env: [
      "DATABASE_URL_BILLING",
      "DATABASE_URL_PAYMENT_PROCESSING",
      "PAYSYNC_UPLOAD_DIR",
      "PAYSYNC_HASH_CHAIN_SYNC_LIMIT",
    ],
    health: [
      "http://billing:8040/health",
      "http://payment-processing:8050/health",
    ],
    seedData: [],
    queues: ["paysync.upload.parsed"],
    jobs: ["paysync.uploads.retention", "paysync.audit.hash-chain.verify"],
    buckets: [],
    integrations: [],
    secrets: [
      "secret://db/billing",
      "secret://db/payment-processing",
    ],
  },
  shellSurfaces: {
    navOrderSlots: [20],
    cacheTagPrefixes: ["paysync:"],
    commandPaletteScopes: ["paysync.*"],
    routePrefixes: ["/admin/paysync"],
    cacheKeyNamespaces: ["paysync:"],
    redisKeyPrefixes: ["tenant:*:paysync:"],
    rabbitExchanges: ["paysync"],
  },
  surfaceKinds: ["server", "client"] as Array<"server" | "client">,
  entitlements: { requiredScope: null },
} as const;

// Paysync-specific runtime composition. NOT read by SD-4 manifest tooling.
// Consumed by:
//   - Surface mounting (Plans B–E)
//   - Inbox card registry (Task 5 below)
//   - qa-harness role switcher chip (qa-harness only, never production)
export const paysyncComposition = {
  displayName: "PaySync",
  rbac: {
    operator: [
      "paysync.upload", "paysync.upload.view", "paysync.batch.draft",
      "paysync.cycle.view", "paysync.carryover.view", "paysync.journal.view",
      "paysync.audit.view",
    ],
    approver: [
      "paysync.upload", "paysync.upload.view", "paysync.batch.draft",
      "paysync.cycle.view", "paysync.carryover.view", "paysync.journal.view",
      "paysync.audit.view",
      "paysync.cycle.close", "paysync.invoice.send", "paysync.payment_run.release",
      "paysync.nacha.generate", "paysync.835.generate", "paysync.reconcile.finalize",
      "paysync.discrepancy.resolve", "paysync.manual_ap.commit", "paysync.setup.mutate",
    ],
    auditor: [
      "paysync.read", "paysync.upload.view", "paysync.journal.view",
      "paysync.journal.verify", "paysync.audit.view",
    ],
  },
  inboxItemKinds: [
    { kind: "upload_pending_review",              card: () => import("./src/inbox/cards/UploadPendingReviewCard.js")    },
    { kind: "upload_validated_awaiting_batching", card: () => import("./src/inbox/cards/UploadValidatedCard.js")        },
    { kind: "cycle_pending_close",                card: () => import("./src/inbox/cards/CyclePendingCloseCard.js")      },
    { kind: "cycle_close_review",                 card: () => import("./src/inbox/cards/CycleCloseReviewCard.js")       },
    { kind: "batch_drafted",                      card: () => import("./src/inbox/cards/BatchDraftedCard.js")           },
    { kind: "ar_invoice_draft",                   card: () => import("./src/inbox/cards/ArInvoiceDraftCard.js")         },
    { kind: "ap_payment_run_held",                card: () => import("./src/inbox/cards/ApPaymentRunHeldCard.js")       },
    { kind: "banking_discrepancy",                card: () => import("./src/inbox/cards/BankingDiscrepancyCard.js")     },
    { kind: "reconciliation_pending",             card: () => import("./src/inbox/cards/ReconciliationPendingCard.js")  },
    { kind: "carryover_open",                     card: () => import("./src/inbox/cards/CarryoverOpenCard.js")          },
    { kind: "journal_periodic_review",            card: () => import("./src/inbox/cards/JournalPeriodicReviewCard.js")  },
  ],
  routeSurfaces: {
    "/admin/paysync":              "uploads",        // Inbox at index
    "/admin/paysync/uploads":      "uploads",
    "/admin/paysync/cycles":       "cycles",
    "/admin/paysync/batches":      "batches",
    "/admin/paysync/carryovers":   "carryovers",
    "/admin/paysync/invoices":     "invoices",
    "/admin/paysync/payment-runs": "payment-runs",
    "/admin/paysync/files":        "files",
    "/admin/paysync/settlements":  "bank-settlements",
    "/admin/paysync/reconcile":    "reconciliations",
    "/admin/paysync/journal":      "journal",
    "/admin/paysync/reports":      "reports",
    "/admin/paysync/setup":        "setup",
  },
  navTree: {
    primary: [
      { label: "Inbox",    path: "/admin/paysync",             icon: "inbox"      },
      { label: "History",  path: "/admin/paysync/uploads",     icon: "clock"      },
      { label: "Journal",  path: "/admin/paysync/journal",     icon: "book-open"  },
      { label: "Reports",  path: "/admin/paysync/reports",     icon: "bar-chart"  },
      { label: "Setup",    path: "/admin/paysync/setup",       icon: "settings"   },
    ],
  },
  qa: {
    RoleSwitcherChip: () => import("./src/components/dev-only/RoleSwitcherChip.js"),
  },
} as const;
```

**11 typed inbox card stubs** (`src/inbox/cards/<Name>Card.tsx`):

```tsx
// packages/modules/paysync/src/inbox/cards/UploadPendingReviewCard.tsx
// Typed stub — replaced with real card in Plan B. Renders kind + data-testid only.
import type { InboxItem } from "../types.js";

export default function UploadPendingReviewCard({ item }: { item: InboxItem }) {
  return <div data-testid="inbox-card-upload_pending_review">{item.kind}</div>;
}
```

Each card stub:
- Accepts `{ item: InboxItem }` props (typed from `types.ts`)
- Renders `<div data-testid="inbox-card-{kind}">{item.kind}</div>`
- Has a co-located unit test (`<Name>Card.test.tsx`) asserting render given a minimal `InboxItem` fixture

These are not empty stubs. Plans B–E replace the body without changing the interface.

- [ ] Step 5.1: Write `packages/modules/paysync/module.config.ts` at ROOT (literal content above; both `config` and `paysyncComposition` exports)
- [ ] Step 5.2: Create 11 card stubs under `src/inbox/cards/` — each typed + data-testid + co-located test
- [ ] Step 5.3: Replace the placeholder card factories in `src/inbox/ItemRegistry.ts` (from Task 3.2) with REAL dynamic imports: `card: () => import("./cards/UploadPendingReviewCard.js")` etc. This step lands in the SAME commit as the 11 card stub files created in Step 5.2 — together they form an atomic unit (R4 fix). Registry may also import from `paysyncComposition.inboxItemKinds` as a single source of truth — either approach is acceptable as long as `tsc -b` proves all imports resolve in this commit.
- [ ] Step 5.4: Edit root `tsconfig.json` — add `{ "path": "./packages/modules/paysync" }` to references array (R3: moved here from Task 1.4 for atomicity)
- [ ] Step 5.5: Edit `infrastructure/manifests/operator-dev.yml` — add `paysync` to `modules:` array as `- paysync` line (R3: moved here from Task 1.5 for atomicity)
- [ ] Step 5.6: `npm run typecheck` — exits 0 (all workspace refs including the new paysync reference; module.config.ts root file recognized)
- [ ] Step 5.7: `npm run manifest:validate` — exits 0 (paysync in modules list AND module.config.ts exists with required SD-4 shape)
- [ ] Step 5.8: `npm --workspace=@infinityrx/module-paysync test` — all pass
- [ ] Step 5.9: Commit — `feat(sp-1-a): module.config.ts (SD-4 + paysync composition) + 11 typed inbox card stubs + wire into workspace tsconfig + operator-dev manifest`

---

### Task 6 — Contract extension (impls/paysync) + fixtures layout

**Contract extension** — match HEAD pattern at `packages/contract/src/impls/prescriber-directory/`:

Files (singular `client.ts` per PD convention; R3 fix):
- `packages/contract/src/impls/paysync/types.ts` — Zod schemas for `Upload`, `InboxItem`, `RbacRole`
- `packages/contract/src/impls/paysync/client.ts` — BOTH `UploadsClient` interface (`list`, `get`, `create`, `getClaims`) AND `InboxClient` interface (`list`); cache policies for each. Singular `client.ts` matches `packages/contract/src/impls/prescriber-directory/client.ts` convention. Subsequent plans (B/C/D/E) may append more client interfaces here OR add domain-specific `<name>-client.ts` siblings as the surface area grows.
- `packages/contract/src/impls/paysync/real.ts` — `createRealUploadsClient`, `createRealInboxClient` (return objects; HTTP impl stubbed but typed)
- `packages/contract/src/impls/paysync/mock.ts` — `createMockUploadsClient`, `createMockInboxClient` (return typed empty arrays / hard-coded fixtures)

Add to `packages/contract/src/index.ts`:

```ts
// PaySync clients — SP-1.
export {
  UploadSchema,
  InboxItemSchema,
  RbacRoleSchema,
  type Upload,
  type InboxItem as ContractInboxItem,  // alias to avoid clash with module's InboxItem
  type RbacRole as ContractRbacRole,
} from "./impls/paysync/types.js";

export {
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  type UploadsClient,
  type InboxClient,
} from "./impls/paysync/client.js";

export {
  createRealUploadsClient,
  createRealInboxClient,
} from "./impls/paysync/real.js";

export {
  createMockUploadsClient,
  createMockInboxClient,
} from "./impls/paysync/mock.js";
```

**Fixtures layout** (`packages/modules/paysync/fixtures/`):

```
fixtures/
  uploads/
    upload-001-healthy.csv        ← header row only (real data in Plan E)
    upload-002-validation-fail.csv ← header row only (real data in Plan E)
    upload-003-half-bad.csv       ← header row only (real data in Plan E)
  seeds/
    tenant.json                   ← {} stub
    cycles.json                   ← [] stub
    invoices.json                 ← [] stub
    payment-runs.json             ← [] stub
    reconciliations.json          ← [] stub
    users.json                    ← [] stub
```

CSV header (per §10.3 minimum schema):
```
ndc,npi,claim_id,date_of_service,quantity,days_supply,amount_billed,member_id
```

- [ ] Step 6.1: Write `packages/contract/src/impls/paysync/{types,client,real,mock}.ts` (singular `client.ts` holding both interfaces; R3 fix)
- [ ] Step 6.2: Add named exports to `packages/contract/src/index.ts` (literal above)
- [ ] Step 6.3: Add contract test in `packages/contract/src/__tests__/paysync.test.ts` — instantiate `createMockUploadsClient()` and `createMockInboxClient()`; assert `list()` returns typed arrays; assert schemas validate sample fixtures
- [ ] Step 6.4: Create fixtures directory layout (3 CSV stubs with headers + 6 JSON stubs)
- [ ] Step 6.5: `npm --workspace=@infinityrx/contract test` — all pass
- [ ] Step 6.6: `tsc -b` exits 0 (contract still compiles with new exports)
- [ ] Step 6.7: Commit — `feat(sp-1-a): contract impls/paysync + fixtures layout`

---

## Gate Criteria

Plan A is complete when ALL of the following are true:

- [ ] `npm run typecheck` exits 0 (all workspace project references compile, including new `packages/modules/paysync` reference)
- [ ] `npm --workspace=@infinityrx/module-paysync test` — all tests pass, 0 failing
- [ ] `npm --workspace=@infinityrx/contract test` — all tests pass (includes new paysync impl tests)
- [ ] Coverage gates: 100% branch on `MoneyDisplay`, `MoneyInput`, `RbacGate` (financial + security paths); ≥99% branch coverage on Inbox components (CLAUDE.md Auto-Gate)
- [ ] `npm run manifest:validate` exits 0 with `paysync` in modules list AND `packages/modules/paysync/module.config.ts` exporting valid `config` matching SD-4 `ModuleConfig` shape
- [ ] `packages/modules/paysync/module.config.ts` at ROOT (not src/) exports BOTH `config` (SD-4 shape) AND `paysyncComposition` (runtime fields); tsc confirms via `as const`
- [ ] All 11 inbox card stubs exist, are typed (accept `item: InboxItem` prop), render `data-testid="inbox-card-{kind}"`, have unit tests, and dynamic imports in `paysyncComposition.inboxItemKinds` resolve — zero empty-file stubs
- [ ] All 13 surface `index.ts` stubs exist (R4: includes `echo/` per inventory §200) and export a typed `SurfaceConfig` constant (not empty object) — `tsc -b` proves they satisfy the `SurfaceConfig` shape; **echo's Inbox kind, BFF wiring, and `EchoClient` are scoped to Plan E §6 — Plan A only ships the surface folder + typed stub**
- [ ] Fixtures directory exists with 3 CSV stubs (header rows only acceptable here) + 6 JSON stubs (empty arrays acceptable here — real data is Plan E)
- [ ] Contract package: `packages/contract/src/impls/paysync/{types,client,real,mock}.ts` present (singular `client.ts`); named exports added to `packages/contract/src/index.ts`; mock factories instantiable in test (NOT just files present)
- [ ] No `RoleSwitcherChip` string in `packages/modules/paysync/src/components/index.ts` (checked by grep in commit; only re-exported via `paysyncComposition.qa.RoleSwitcherChip`)
- [ ] `src/bff/inbox.ts` exists as a typed stub returning `[]: InboxItem[]` — gate explicitly accepts this as stub-scope; "real Inbox implementation" is Plan B gate criterion, not Plan A
- [ ] Root `tsconfig.json` references include `{ "path": "./packages/modules/paysync" }`
- [ ] Root `package.json` `test:packages` script appends `&& npm --workspace=@infinityrx/module-paysync test`
- [ ] NO changes to `packages/shell/` source or exports (R2 simplification — no shared `ModuleConfig` type needed; `as const` literal is sufficient)
- [ ] NO `@tanstack/react-query` / `@tanstack/react-virtual` peer-dep conflicts on `npm install`

---

## Deliverables

- `packages/modules/paysync/` — fully typed SP-0-conformant module package, compilable, testable
- `module.config.ts` at root — SD-4 `config` + paysync `paysyncComposition`; consumed by build-manifest tooling AND surface mounting layer
- Complete Inbox taxonomy (`InboxItemKind`, `INBOX_KIND_ROLE`) — extensible without refactor
- All 6 module-local primitives — usable by Plans B–E immediately
- BFF route stub — Plans B–E fill in real handlers
- Contract impls — Plans B–E provide real backend wiring; mocks usable now for dev
- Fixtures skeleton — Plan E populates real synthetic data

---

## Dependencies

- SP-0 Plans A–D fully executed: `packages/{auth,contract,modules,qa-harness,scripts,shell,ui}/` all present at HEAD `d9c69152` ✓
- `packages/scripts/build-manifest.ts:36-77` exports `ModuleConfig` interface — that is the SD-4 shape `config` must satisfy ✓
- `packages/modules/prescriber-directory/module.config.ts` — canonical template for the `as const` + `config`-named-export pattern ✓
- No changes required to `packages/shell/` exports (R2 simplification)
- `@tanstack/react-query@5.59.20`, `@tanstack/react-virtual@3.10.8` added to module package only — first introduction to workspace; verify no peer conflicts during `npm install`

---

## Cross-references

- Spec §5.1 (layering), §5.3 (Inbox spine), §5.4 (RBAC matrix), §5.6 (SP-0 consumed), §6.1 (inbox components), §6.6 (RoleSwitcherChip production exclusion), §10 (plan-time decisions)
- Rules: `.claude/rules/financial-precision.md`, `.claude/rules/security.md`, `.claude/rules/testing.md`, `.claude/rules/architecture.md`, `.claude/rules/code-standards.md`
- SP-0 Plan D: `docs/superpowers/plans/2026-05-15-sp0-plan-d-composition-portal-wiring.md`
- HEAD canonical template: `packages/modules/prescriber-directory/module.config.ts`
- HEAD SD-4 interface: `packages/scripts/build-manifest.ts:36-77`
- SP-1 Plans B–E: depend on all deliverables above
- Pre-execute codex NO-GO (resolved by this R2): the 6 items in §"R2 Revision Summary" above
