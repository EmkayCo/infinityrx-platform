# SP-0 Plan C — Status: Complete 2026-05-15

**Branch:** `wave/B10-w5-plan-c`
**Base branch:** `wave/B10-w5` (commit `984eff2`)
**Final HEAD SHA:** `0700af7`

---

## Task SHAs

| Task | Commit | Description |
|---|---|---|
| Plan B prereq | `ea78d4a` | packages/contract + packages/auth scaffolds (Plan C prerequisite — Plan B was never executed) |
| Task 1 | `5d712d2` | Scaffold packages/ui + packages/qa-harness |
| Task 2 | `e692b3e` | packages/ui: Button, Input, DataTable primitives |
| Task 3 | `32e523d` | packages/ui: Form, FormField, AppShell, DragHandle |
| Task 4 | `b62658a` | packages/ui: KPICard, LineChart, CommandPalette |
| Task 5 | `1f4621f` | packages/qa-harness: ServicesHealth + MockToggle |
| Task 6 | `bb9771e` | packages/qa-harness: CompositionViewer, FactoryBindings, CorrelationIdJump |
| Task 7 | TBD | Framework-agnostic enforcement tests + this status doc |

---

## What Ships in Plan C

### packages/ui — 10 components across 6 categories

| Category | Component | Description |
|---|---|---|
| primitives | `Button` | cva variants (default/destructive/outline/ghost), sizes (sm/md/lg), forwardRef |
| primitives | `Input` | forwardRef, react-hook-form compatible, all HTML input props passthrough |
| primitives | `DataTable` | Simple HTML table with typed columns+rows, emptyMessage slot |
| form | `Form` | react-hook-form FormProvider + zodResolver wrapper |
| form | `FormField` | Controller wrapper with label + zod error message slot |
| shells | `AppShell` | children (main) + optional header + optional nav slots |
| dnd | `DragHandle` | dnd-kit useSortable handle — foundation for SP-6 program builder |
| charts | `KPICard` | Metric display: label + value + optional delta badge |
| charts | `LineChart` | Thin recharts wrapper (single-line 80% case) |
| command | `CommandPalette` | Thin cmdk wrapper rendered as a Dialog |

### packages/qa-harness — 5 components

| Component | Description |
|---|---|
| `ServicesHealth` | Live health dashboard: fans out to `BaseClient.probeHealth()`, renders status + latency + errors |
| `MockToggle` | Per-client real/mock toggle UI with `onToggle` callback |
| `CompositionViewer` | Renders `manifest.modules[]` list from prop (framework-agnostic — fetch deferred to Plan C-shell) |
| `FactoryBindings` | Seed buttons with loading/seeded/error state; `seed(kind)` callback |
| `CorrelationIdJump` | correlation_id input + clipboard copy + log-search URL link |

### packages/contract — Plan B prerequisite

| Export | Description |
|---|---|
| `ErrorEnvelopeSchema` / `isErrorEnvelope` | Zod schema + type guard for `{ error: { code, message, field?, correlation_id } }` |
| `CachePolicySchema` / `CachePolicy` | TTL/key/tags/backend_down cache policy type |
| `BaseClient` | Interface: `name` + `cachePolicies` + `probeHealth()` |
| `ClientConfig` / `ClientFactory` | Factory + config types |

---

## What Is NOT in Plan C (Deferred)

- Full design-system component catalog (all Radix primitives, full table/form suite) — verticals build on top
- TanStack Table virtualization in DataTable — ships as simple HTML table; future when a vertical needs 7M-record tables
- Full recharts suite (AreaChart, BarChart, PieChart) — only LineChart + KPICard ship
- Tailwind design tokens — packages use irx-* class names; Tailwind config lives in Plan C-shell
- `packages/shell` — Plan C-shell (Next.js App Router host layer)
- Portal wiring (`portal/operator` consuming `@infinityrx/ui` and `@infinityrx/qa-harness`) — Plan C-shell
- QA mode toggle + request/response inspector — deferred to Plan C-shell (need Next.js route context)
- Full Plan B (`packages/auth` JWT implementation, prescriber-directory client, MSW tests) — separate wave; Plan C only needed `BaseClient`

---

## Deviations from Plan Spec

| Item | Spec | Actual | Reason |
|---|---|---|---|
| `happy-dom` version | `15.11.7` | `20.9.0` | 15.x has critical CVEs (VM context escape, RCE); 20.9.0 is clean |
| `react`/`react-dom` devDeps | Not in spec (peer only) | Added as devDeps `19.2.6` | npm workspaces don't hoist peer deps to test packages without explicit devDep; vitest needs React resolvable |
| `@testing-library/dom` | Not in spec | Added as devDep `10.4.0` | Peer of `@testing-library/react`; not auto-hoisted |
| `lib: ["ES2023", "DOM"]` | Not in spec | Added to ui + qa-harness tsconfig | Base tsconfig has `lib: ["ES2023"]`; React/navigator/DOM types require DOM lib |
| `globals: true` in vitest config | Not in spec | Added | happy-dom 20.x requires globals mode for `@testing-library/react` cleanup between tests |
| Plan B prerequisite | Not in Plan C scope | Executed minimal subset (contract only) | Plan C imports `BaseClient`; Plan B was never executed; full auth JWT implementation deferred |
| `Object.defineProperty` for clipboard mock | `Object.assign` in spec | Fixed to `Object.defineProperty` | happy-dom 20.x has `navigator.clipboard` as getter-only; `Object.assign` throws |
| `onSubmit` wrapper in Form | `handleSubmit(onSubmit)` | `handleSubmit((data) => onSubmit(data))` | `handleSubmit` passes `(data, event)` to handler; spec test expects `onSubmit` called with data only |

---

## Verification Results

```
npm run typecheck        → exit 0
npm run manifest:validate → ✓ operator-dev.yml validates clean
npm run manifest:validate:standalone → ✓ example-reclaimrx-standalone.yml validates clean
npm run test:packages:

  @infinityrx/scripts   10 tests  ✓
  @infinityrx/contract  15 tests  ✓
  @infinityrx/auth       2 tests  ✓
  @infinityrx/ui        45 tests  ✓  (includes 12 framework-agnostic: 1 count + 11 file scans)
  @infinityrx/qa-harness 31 tests  ✓  (includes 7 framework-agnostic: 1 count + 6 file scans)

  Total: 103 tests, 0 failures, 0 skips
```

Framework-agnostic ESLint enforcement (Task 7): both packages scan their src/ tree and assert zero `next/`, `next-auth/`, or `@auth/` imports. All files pass.

---

## Decision

**Plan C is complete. Ready for Plan C-shell.**

Plan C-shell scope: `packages/shell` — Next.js App Router host layer. Responsibilities:
- Next.js routing + App Router layout
- Auth integration (consuming `@infinityrx/auth` tokens + `next-auth`)
- Dynamic module nav mounted into `AppShell`'s `nav` slot
- `CommandPalette` wired to Cmd+K keyboard shortcut
- `CompositionViewer` fetching from `_generated/manifest.json` at runtime
- QA mode toggle + request/response inspector (need Next.js route context)
- `portal/operator` consuming both `@infinityrx/ui` and `@infinityrx/qa-harness`
