# SP-0 Plan C — packages/ui + packages/qa-harness Implementation Plan

> **Status:** v2, 2026-05-15. v1 BLOCKED codex pass-1 with 1 BLOCK + 2 CONCERN + 1 NIT. v2 closes:
> - **BLOCK (dnd-kit/utilities undeclared):** packages/ui/package.json now lists `@dnd-kit/utilities` 3.2.2 in dependencies; DragHandle's `import { CSS } from "@dnd-kit/utilities"` resolves cleanly.
> - **CONCERN (AppShell API):** Changed from `{header, sidebar, main}` props to `{children, header?, nav?}` per Plan C-shell's forward-readiness contract. Children render in `<main>`; Plan C-shell mounts the dynamic module nav into the `nav` slot. Tests updated to match.
> - **CONCERN (spec-coverage table dishonest):** §6.4 qa-harness row reworded from "YES — all 7 covered" to "PARTIAL — 5 of 7 covered; QA mode toggle + request/response inspector explicitly deferred to Plan C-shell."
> - **NIT (qa-harness contract dep ordering):** Task 5.1's tsconfig `references` to `../contract` is the load-bearing edit; Task 1 only scaffolds packages/qa-harness without the reference. Acceptable because qa-harness does not import from `@infinityrx/contract` until Task 5 starts. Documented in self-review.
>
> **Scope clarification:** Plan C originally covered ui + qa-harness + shell. Shell split out to **Plan C-shell** after a sizing reality check — shell requires Next.js-specific App Router wiring and depends on Plan C's framework-agnostic packages landing first. Plan C covers ONLY `packages/ui` and `packages/qa-harness`, both of which are framework-agnostic (zero `next/*` imports). Plan C-shell is written and executed after Plan C is complete.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `packages/ui` (shared design system: reference primitives, form layer, AppShell, dnd-kit handle, chart wrappers, command palette host) and `packages/qa-harness` (manual QA toolkit: services-health dashboard, mock toggle, composition viewer, factory bindings, correlation-id quick-jump) as the SP-0 component layer on top of the Plan B spine (commit `9b144e9`). Each package builds, typechecks, lints, and ships its own vitest suite via happy-dom. End state: workspace-root `tsc -b` compiles both packages, `npm run test:packages` runs all suites (scripts + contract + auth + ui + qa-harness), CI workflow extended.

**Architecture:** Two new workspaces under `packages/`. Both are strictly framework-agnostic (zero `next/*`, `next-auth/*`, `@auth/*` imports — already enforced by Plan A's ESLint Block B). `packages/ui` ships ONE reference component per category — it is the FRAMEWORK, not a full design system; verticals build atop. `packages/qa-harness` imports `@infinityrx/contract` (for `BaseClient`) but NOT `@infinityrx/auth`; it is a dev/staging tool omitted from prod builds. `packages/shell` (Plan C-shell) is responsible for wiring both packages into the Next.js portal.

**Tech Stack:** Node 22 LTS, TypeScript 5.6.3 (NodeNext, verbatimModuleSyntax, strict, composite), React 19.2.x (peer dep — portal owns the runtime), zod 3.23.8, react-hook-form 7.x + @hookform/resolvers for form layer, @radix-ui/react-{dialog,select,tabs,dropdown-menu} for accessible primitives, class-variance-authority 0.7.x for shadcn-style variants, dnd-kit (@dnd-kit/core + @dnd-kit/sortable) 6.x for drag handles, recharts 2.x for charts, cmdk 1.x for command palette, happy-dom 15.x for vitest DOM environment, vitest 2.1.9.

**Spec references:**
- Main spec `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` (commit `a50130f`) §6.3 (`packages/ui`), §6.4 (`packages/qa-harness`)
- SD-2 (framework v3) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-framework.md` (commit `14d847a`) — framework-agnostic spine mandate; zero `next/*` in `packages/**`
- SD-4 (composition v5) `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md` (commit `0b3c9d7`) §4 — workspace-root ESLint Block B already bans `next/*` in `packages/**`; no per-package ESLint config needed
- Plan A `docs/superpowers/plans/2026-05-15-sp0-plan-a-foundation-scaffolding.md` (commit `424bd14`) — workspace pattern
- Plan B `docs/superpowers/plans/2026-05-15-sp0-plan-b-contract-auth.md` (commit `9b144e9`) — package.json shape, tsconfig shape, vitest.config.ts shape, framework-agnostic test pattern, self-review + execution handoff pattern

**Out of scope for Plan C** (deferred):
- Full design-system component catalog (all Radix primitives, full table/form suite) — verticals build on top of the reference components shipped here.
- TanStack Table integration in `DataTable` — ships as a simple HTML table in Plan C; TanStack wire-up is a future task when a vertical needs virtualized 7M-record tables.
- recharts full suite (AreaChart, BarChart, PieChart) — only `LineChart` + `KPICard` ship in Plan C.
- `packages/shell` — Plan C-shell (depends on Plan C landing first).
- Portal wiring (`portal/operator` consuming `@infinityrx/ui` and `@infinityrx/qa-harness`) — Plan C-shell.
- Tailwind config / design tokens — Plan C-shell; these packages use inline styles + cva class names so they compile without a Tailwind PostCSS pass.

---

## File Structure (Plan C creates / modifies)

### Creates

```
packages/ui/
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    index.ts                              # public surface re-exports
    primitives/
      Button.tsx                          # cva variants: default/destructive/outline/ghost; sizes sm/md/lg
      Input.tsx                           # forwardRef, react-hook-form compatible
      DataTable.tsx                       # simple HTML table (TanStack integration is future)
    form/
      Form.tsx                            # react-hook-form FormProvider + zod resolver wrapper
      FormField.tsx                       # Controller wrapper with label + error message slot
    shells/
      AppShell.tsx                        # children (main) + optional header + optional nav slot (Plan C-shell mounts the dynamic module nav here)
    dnd/
      DragHandle.tsx                      # dnd-kit sortable handle — foundation for SP-6 program builder
    charts/
      KPICard.tsx                         # metric display: label + value + delta badge (no recharts)
      LineChart.tsx                       # wraps recharts ResponsiveContainer + LineChart
    command/
      CommandPalette.tsx                  # wraps cmdk Command.Dialog
    __tests__/
      Button.test.tsx
      Input.test.tsx
      DataTable.test.tsx
      Form.test.tsx
      AppShell.test.tsx
      DragHandle.test.tsx
      KPICard.test.tsx
      LineChart.test.tsx
      CommandPalette.test.tsx
      framework-agnostic.test.ts

packages/qa-harness/
  package.json
  tsconfig.json
  vitest.config.ts
  src/
    index.ts                              # public surface re-exports
    services-health.tsx                   # renders probeHealth results for a BaseClient[]
    mock-toggle.tsx                       # per-client real/mock toggle UI
    composition-viewer.tsx                # renders manifest: { modules: string[] } prop
    factory-bindings.tsx                  # buttons that call seed(kind) callback
    correlation-id-jump.tsx               # input + clipboard copy + log-search URL emit
    __tests__/
      services-health.test.tsx
      mock-toggle.test.tsx
      composition-viewer.test.tsx
      factory-bindings.test.tsx
      correlation-id-jump.test.tsx
      framework-agnostic.test.ts
```

### Modifies

```
tsconfig.json                             # add references to ./packages/ui and ./packages/qa-harness
package.json                              # npm workspaces auto-discovers packages/* — no change needed unless already enumerated
package-lock.json                         # regenerated after npm install
.github/workflows/sp0-foundation.yml      # test:packages already fans out; no change needed if Tasks 1-6 are correct
```

### Leaves alone

```
packages/contract/                        # untouched
packages/auth/                            # untouched
packages/scripts/                         # untouched
portal/                                   # untouched (Plan C-shell handles portal wiring)
modules/, shared/, scripts/               # backend Python untouched
```

---

## Plan C — Tasks

### Task 1: Both package scaffolds (ui + qa-harness)

**Files:**
- Create: `packages/ui/package.json`
- Create: `packages/ui/tsconfig.json`
- Create: `packages/ui/vitest.config.ts`
- Create: `packages/ui/src/index.ts` (stub)
- Create: `packages/qa-harness/package.json`
- Create: `packages/qa-harness/tsconfig.json`
- Create: `packages/qa-harness/vitest.config.ts`
- Create: `packages/qa-harness/src/index.ts` (stub)
- Modify: `tsconfig.json` (repo root) — add references to both new packages

- [ ] **Step 1.1: Write `packages/ui/package.json`**

```json
{
  "name": "@infinityrx/ui",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "peerDependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "tailwindcss": "^4.0.0"
  },
  "dependencies": {
    "@dnd-kit/core": "6.3.1",
    "@dnd-kit/sortable": "8.0.0",
    "@dnd-kit/utilities": "3.2.2",
    "@radix-ui/react-dialog": "1.1.4",
    "@radix-ui/react-dropdown-menu": "2.1.4",
    "@radix-ui/react-select": "2.1.4",
    "@radix-ui/react-tabs": "1.1.2",
    "@hookform/resolvers": "3.9.1",
    "class-variance-authority": "0.7.1",
    "cmdk": "1.0.4",
    "react-hook-form": "7.54.2",
    "recharts": "2.15.3",
    "zod": "3.23.8"
  },
  "devDependencies": {
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.5.2",
    "@types/node": "22.7.5",
    "@types/react": "19.1.2",
    "@types/react-dom": "19.1.2",
    "happy-dom": "15.11.7",
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

- [ ] **Step 1.2: Write `packages/ui/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "jsx": "react-jsx"
  },
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 1.3: Write `packages/ui/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**/*.test.ts", "src/__tests__/**/*.test.tsx"],
    environment: "happy-dom",
  },
});
```

- [ ] **Step 1.4: Write `packages/ui/src/index.ts` (stub)**

```ts
// Public surface of @infinityrx/ui.
// Re-exports added as components are built in Tasks 2-4.
```

- [ ] **Step 1.5: Write `packages/qa-harness/package.json`**

```json
{
  "name": "@infinityrx/qa-harness",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "peerDependencies": {
    "@infinityrx/contract": "*",
    "@infinityrx/ui": "*",
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
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

Note: `@infinityrx/contract` and `@infinityrx/ui` are `peerDependencies` only — they are hoisted by the npm workspace and available at runtime without being listed as direct `dependencies`. This keeps the qa-harness package tree clean.

- [ ] **Step 1.6: Write `packages/qa-harness/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "jsx": "react-jsx"
  },
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 1.7: Write `packages/qa-harness/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**/*.test.ts", "src/__tests__/**/*.test.tsx"],
    environment: "happy-dom",
  },
});
```

- [ ] **Step 1.8: Write `packages/qa-harness/src/index.ts` (stub)**

```ts
// Public surface of @infinityrx/qa-harness.
// Re-exports added as components are built in Tasks 5-6.
// IMPORTANT: This package is a dev/staging tool. Omit from prod builds.
```

- [ ] **Step 1.9: Add references to repo-root `tsconfig.json`**

Open `tsconfig.json` at the repo root. In the `references` array, add:

```json
{ "path": "./packages/ui" },
{ "path": "./packages/qa-harness" }
```

The existing references for `packages/scripts`, `packages/contract`, and `packages/auth` must remain unchanged.

- [ ] **Step 1.10: Install and verify**

```bash
npm install
npm ls --workspaces 2>&1 | grep "@infinityrx"
```

Expected: `@infinityrx/ui` and `@infinityrx/qa-harness` both listed in workspace output alongside `@infinityrx/contract`, `@infinityrx/auth`, `@infinityrx/scripts`.

- [ ] **Step 1.11: Verify typecheck with stub index files**

```bash
npm run typecheck
```

Expected: exit 0. The stub `index.ts` files contain only comments — no type errors possible.

- [ ] **Step 1.12: Commit**

```bash
git add packages/ui/ packages/qa-harness/ tsconfig.json package-lock.json
git commit -m "feat(sp-0): Plan C Task 1 — scaffold packages/ui + packages/qa-harness

Both packages: package.json, tsconfig.json (jsx: react-jsx), vitest.config.ts
(environment: happy-dom), src/index.ts stubs.

packages/ui deps: @dnd-kit, @radix-ui (dialog/select/tabs/dropdown),
react-hook-form + @hookform/resolvers, class-variance-authority,
cmdk, recharts, zod. React 19.2 + tailwindcss 4.x as peerDeps.
packages/qa-harness: @infinityrx/contract + ui as peerDeps (workspace-hoisted).

tsconfig.json: added references for both new packages.
npm install: all peers resolved, npm ls --workspaces shows both packages.
tsc -b: exit 0 on stub index files.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 2: packages/ui — primitives (Button, Input, DataTable)

**Files:**
- Create: `packages/ui/src/primitives/Button.tsx`
- Create: `packages/ui/src/primitives/Input.tsx`
- Create: `packages/ui/src/primitives/DataTable.tsx`
- Create: `packages/ui/src/__tests__/Button.test.tsx`
- Create: `packages/ui/src/__tests__/Input.test.tsx`
- Create: `packages/ui/src/__tests__/DataTable.test.tsx`
- Modify: `packages/ui/src/index.ts`

TDD order for each component: write failing tests → write implementation → verify passing.

- [ ] **Step 2.1: Write `packages/ui/src/__tests__/Button.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../primitives/Button.js";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeDefined();
  });

  it("applies destructive variant class", () => {
    const { container } = render(<Button variant="destructive">Del</Button>);
    expect(container.firstChild?.toString()).toContain("destructive");
    // cva emits the variant name as part of the className
    expect((container.firstChild as HTMLElement).className).toMatch(/destructive/);
  });

  it("applies size class for lg", () => {
    const { container } = render(<Button size="lg">Big</Button>);
    expect((container.firstChild as HTMLElement).className).toMatch(/lg/);
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>No</Button>);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  });
});
```

- [ ] **Step 2.2: Write `packages/ui/src/primitives/Button.tsx`**

```tsx
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

const buttonVariants = cva(
  // Base classes (framework-agnostic — no Tailwind needed to compile; classes are just strings)
  "irx-btn",
  {
    variants: {
      variant: {
        default: "irx-btn--default",
        destructive: "irx-btn--destructive",
        outline: "irx-btn--outline",
        ghost: "irx-btn--ghost",
      },
      size: {
        sm: "irx-btn--sm",
        md: "irx-btn--md",
        lg: "irx-btn--lg",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

/**
 * Reference button primitive. Uses cva for variant/size composition.
 * Portals apply Tailwind utility classes by augmenting buttonVariants via
 * className merging (cn(buttonVariants(...), className)).
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant, size, className, ...props }, ref) => (
    <button
      ref={ref}
      className={[buttonVariants({ variant, size }), className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Button.displayName = "Button";
```

- [ ] **Step 2.3: Write `packages/ui/src/__tests__/Input.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { Input } from "../primitives/Input.js";

describe("Input", () => {
  it("renders an input element", () => {
    render(<Input placeholder="Search" />);
    expect(screen.getByPlaceholderText("Search")).toBeDefined();
  });

  it("forwards ref to the underlying input", () => {
    const ref = React.createRef<HTMLInputElement>();
    render(<Input ref={ref} />);
    expect(ref.current?.tagName).toBe("INPUT");
  });

  it("passes through type and value props", () => {
    render(<Input type="email" defaultValue="test@example.com" />);
    const input = screen.getByDisplayValue("test@example.com") as HTMLInputElement;
    expect(input.type).toBe("email");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Input disabled />);
    expect((screen.getByRole("textbox") as HTMLInputElement).disabled).toBe(true);
  });
});
```

- [ ] **Step 2.4: Write `packages/ui/src/primitives/Input.tsx`**

```tsx
import * as React from "react";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

/**
 * Reference input primitive. forwardRef-compatible so react-hook-form's
 * register() and Controller render prop both work without a wrapper.
 */
export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={["irx-input", className].filter(Boolean).join(" ")}
      {...props}
    />
  ),
);
Input.displayName = "Input";
```

- [ ] **Step 2.5: Write `packages/ui/src/__tests__/DataTable.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DataTable } from "../primitives/DataTable.js";

interface Row { id: number; name: string }

const columns = [
  { key: "id" as const, header: "ID" },
  { key: "name" as const, header: "Name" },
];

const rows: Row[] = [
  { id: 1, name: "Alice" },
  { id: 2, name: "Bob" },
];

describe("DataTable", () => {
  it("renders column headers", () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText("ID")).toBeDefined();
    expect(screen.getByText("Name")).toBeDefined();
  });

  it("renders a row per data entry", () => {
    render(<DataTable columns={columns} rows={rows} />);
    expect(screen.getByText("Alice")).toBeDefined();
    expect(screen.getByText("Bob")).toBeDefined();
  });

  it("renders empty state message when rows is empty", () => {
    render(<DataTable columns={columns} rows={[]} emptyMessage="No results" />);
    expect(screen.getByText("No results")).toBeDefined();
  });
});
```

- [ ] **Step 2.6: Write `packages/ui/src/primitives/DataTable.tsx`**

```tsx
import * as React from "react";

export interface Column<T> {
  key: keyof T;
  header: string;
}

export interface DataTableProps<T extends object> {
  columns: Column<T>[];
  rows: T[];
  emptyMessage?: string;
  className?: string;
}

/**
 * Reference table primitive. Simple HTML table — no virtualization, no sorting.
 * TanStack Table integration is a future task when a vertical needs it.
 * Every column header maps to a row cell via column.key.
 */
export function DataTable<T extends object>({
  columns,
  rows,
  emptyMessage = "No data",
  className,
}: DataTableProps<T>) {
  return (
    <table className={["irx-data-table", className].filter(Boolean).join(" ")}>
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={String(col.key)}>{col.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={columns.length}>{emptyMessage}</td>
          </tr>
        ) : (
          rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => (
                <td key={String(col.key)}>{String(row[col.key] ?? "")}</td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2.7: Update `packages/ui/src/index.ts`**

```ts
// Public surface of @infinityrx/ui.

// Primitives
export { Button, type ButtonProps } from "./primitives/Button.js";
export { Input, type InputProps } from "./primitives/Input.js";
export { DataTable, type Column, type DataTableProps } from "./primitives/DataTable.js";
```

- [ ] **Step 2.8: Verify typecheck + tests + lint**

```bash
npm run typecheck
npm --workspace=@infinityrx/ui test
npm run lint:root
```

Expected: typecheck exit 0, 11/11 tests pass (4 Button + 4 Input + 3 DataTable), lint exit 0.

- [ ] **Step 2.9: Commit**

```bash
git add packages/ui/
git commit -m "feat(ui): Plan C Task 2 — Button, Input, DataTable primitives

Button: cva variants (default/destructive/outline/ghost), sizes
(sm/md/lg), forwardRef, disabled passthrough. 4 tests.
Input: forwardRef, react-hook-form compatible, all HTML input props
passthrough. 4 tests.
DataTable: simple HTML table with typed columns+rows, emptyMessage
slot. No TanStack dep yet — TanStack integration is a future task.
3 tests.

TDD: tests written red before impl. All 11 pass green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 3: packages/ui — form layer + AppShell + DragHandle

**Files:**
- Create: `packages/ui/src/form/Form.tsx`
- Create: `packages/ui/src/form/FormField.tsx`
- Create: `packages/ui/src/shells/AppShell.tsx`
- Create: `packages/ui/src/dnd/DragHandle.tsx`
- Create: `packages/ui/src/__tests__/Form.test.tsx`
- Create: `packages/ui/src/__tests__/AppShell.test.tsx`
- Create: `packages/ui/src/__tests__/DragHandle.test.tsx`
- Modify: `packages/ui/src/index.ts`

- [ ] **Step 3.1: Write `packages/ui/src/__tests__/Form.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { z } from "zod";
import { Form } from "../form/Form.js";
import { FormField } from "../form/FormField.js";
import { Input } from "../primitives/Input.js";

const schema = z.object({ email: z.string().email("Invalid email") });

describe("Form + FormField", () => {
  it("renders a form element", () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
      </Form>,
    );
    expect(screen.getByRole("form")).toBeDefined();
  });

  it("renders the field label", () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
      </Form>,
    );
    expect(screen.getByText("Email")).toBeDefined();
  });

  it("shows zod validation error on submit with invalid value", async () => {
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={() => {}}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
        <button type="submit">Submit</button>
      </Form>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Invalid email")).toBeDefined();
  });

  it("calls onSubmit with validated data on valid submission", async () => {
    const onSubmit = vi.fn();
    render(
      <Form schema={schema} defaultValues={{ email: "" }} onSubmit={onSubmit}>
        <FormField name="email" label="Email">
          {(field) => <Input {...field} />}
        </FormField>
        <button type="submit">Submit</button>
      </Form>,
    );
    await userEvent.type(screen.getByRole("textbox"), "user@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(onSubmit).toHaveBeenCalledWith({ email: "user@example.com" });
  });
});
```

Note: add `import { vi } from "vitest";` at the top of the test file alongside the other imports.

- [ ] **Step 3.2: Write `packages/ui/src/form/Form.tsx`**

```tsx
import * as React from "react";
import { useForm, FormProvider, type DefaultValues, type FieldValues } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { ZodSchema } from "zod";

export interface FormProps<T extends FieldValues> {
  schema: ZodSchema<T>;
  defaultValues: DefaultValues<T>;
  onSubmit: (data: T) => void | Promise<void>;
  children: React.ReactNode;
  className?: string;
  "aria-label"?: string;
}

/**
 * Thin wrapper: wires react-hook-form + zod resolver, renders FormProvider.
 * Use FormField children to connect inputs to the form state.
 */
export function Form<T extends FieldValues>({
  schema,
  defaultValues,
  onSubmit,
  children,
  className,
  "aria-label": ariaLabel = "form",
}: FormProps<T>) {
  const methods = useForm<T>({
    resolver: zodResolver(schema),
    defaultValues,
  });

  return (
    <FormProvider {...methods}>
      <form
        aria-label={ariaLabel}
        className={["irx-form", className].filter(Boolean).join(" ")}
        onSubmit={methods.handleSubmit(onSubmit)}
      >
        {children}
      </form>
    </FormProvider>
  );
}
```

- [ ] **Step 3.3: Write `packages/ui/src/form/FormField.tsx`**

```tsx
import * as React from "react";
import { useFormContext, Controller, type FieldValues, type Path } from "react-hook-form";

export interface FormFieldRenderProps {
  name: string;
  value: unknown;
  onChange: (...event: unknown[]) => void;
  onBlur: () => void;
  ref: React.Ref<unknown>;
}

export interface FormFieldProps<T extends FieldValues> {
  name: Path<T>;
  label: string;
  children: (field: FormFieldRenderProps) => React.ReactNode;
}

/**
 * Controller wrapper. Renders label + field slot + zod-sourced error message.
 * The children render prop receives the field object compatible with Input/forwardRef primitives.
 */
export function FormField<T extends FieldValues>({ name, label, children }: FormFieldProps<T>) {
  const { control, formState: { errors } } = useFormContext<T>();
  const error = errors[name];

  return (
    <div className="irx-form-field">
      <label htmlFor={name} className="irx-form-field__label">
        {label}
      </label>
      <Controller
        name={name}
        control={control}
        render={({ field }) => (
          <div id={name}>
            {children(field as unknown as FormFieldRenderProps)}
          </div>
        )}
      />
      {error && (
        <span className="irx-form-field__error" role="alert">
          {String(error.message)}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 3.4: Write `packages/ui/src/__tests__/AppShell.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppShell } from "../shells/AppShell.js";

describe("AppShell", () => {
  it("renders header content", () => {
    render(
      <AppShell header={<div>My Header</div>}>
        <p>Main</p>
      </AppShell>,
    );
    expect(screen.getByText("My Header")).toBeDefined();
  });

  it("renders children as the main content", () => {
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );
    expect(screen.getByText("Page content")).toBeDefined();
  });

  it("renders nav slot when provided", () => {
    render(
      <AppShell nav={<nav>Nav</nav>}>
        <p>M</p>
      </AppShell>,
    );
    expect(screen.getByText("Nav")).toBeDefined();
  });

  it("omits nav region when nav prop is not provided", () => {
    const { container } = render(
      <AppShell>
        <p>M</p>
      </AppShell>,
    );
    expect(container.querySelector(".irx-app-shell__nav")).toBeNull();
  });
});
```

- [ ] **Step 3.5: Write `packages/ui/src/shells/AppShell.tsx`**

```tsx
import * as React from "react";

export interface AppShellProps {
  /** Main page content. Mounted inside <main>. */
  children: React.ReactNode;
  /** Optional top header (logo, user menu, etc.). */
  header?: React.ReactNode;
  /** Optional side nav (typically the registered-modules nav from Plan C-shell). */
  nav?: React.ReactNode;
  className?: string;
}

/**
 * Page-level layout shell. Children render in <main>; nav + header are
 * optional slots. Plan C-shell wires auth + the dynamic module nav into
 * the `nav` slot; this component is layout-only.
 */
export function AppShell({ children, header, nav, className }: AppShellProps) {
  return (
    <div className={["irx-app-shell", className].filter(Boolean).join(" ")}>
      {header && <header className="irx-app-shell__header">{header}</header>}
      <div className="irx-app-shell__body">
        {nav && <aside className="irx-app-shell__nav">{nav}</aside>}
        <main className="irx-app-shell__main">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 3.6: Write `packages/ui/src/__tests__/DragHandle.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { DndContext } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { DragHandle } from "../dnd/DragHandle.js";

// DragHandle must be rendered inside a dnd-kit context to function correctly
function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <DndContext>
      <SortableContext items={["item-1"]} strategy={verticalListSortingStrategy}>
        {children}
      </SortableContext>
    </DndContext>
  );
}

describe("DragHandle", () => {
  it("renders a drag handle element", () => {
    render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag to reorder" />
      </Wrapper>,
    );
    expect(screen.getByRole("button", { name: "Drag to reorder" })).toBeDefined();
  });

  it("has the irx-drag-handle class", () => {
    const { container } = render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag" />
      </Wrapper>,
    );
    expect(container.querySelector(".irx-drag-handle")).toBeDefined();
  });

  it("accepts a custom className", () => {
    const { container } = render(
      <Wrapper>
        <DragHandle id="item-1" aria-label="Drag" className="my-handle" />
      </Wrapper>,
    );
    expect((container.firstChild as HTMLElement)?.className).toContain("my-handle");
  });
});
```

- [ ] **Step 3.7: Write `packages/ui/src/dnd/DragHandle.tsx`**

```tsx
import * as React from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

export interface DragHandleProps {
  id: string;
  "aria-label"?: string;
  className?: string;
}

/**
 * Minimal sortable drag handle built on dnd-kit/sortable.
 * Foundation for SP-6's no-code program builder — the builder assembles these
 * into full drag-and-drop rule/action blocks.
 * Must be rendered inside a DndContext + SortableContext.
 */
export function DragHandle({ id, "aria-label": ariaLabel = "Drag to reorder", className }: DragHandleProps) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <button
      ref={setNodeRef}
      type="button"
      aria-label={ariaLabel}
      className={["irx-drag-handle", className].filter(Boolean).join(" ")}
      style={style}
      {...attributes}
      {...listeners}
    />
  );
}
```

- [ ] **Step 3.8: Update `packages/ui/src/index.ts`**

```ts
// Public surface of @infinityrx/ui.

// Primitives
export { Button, type ButtonProps } from "./primitives/Button.js";
export { Input, type InputProps } from "./primitives/Input.js";
export { DataTable, type Column, type DataTableProps } from "./primitives/DataTable.js";

// Form
export { Form, type FormProps } from "./form/Form.js";
export { FormField, type FormFieldProps } from "./form/FormField.js";

// Shells
export { AppShell, type AppShellProps } from "./shells/AppShell.js";

// DnD
export { DragHandle, type DragHandleProps } from "./dnd/DragHandle.js";
```

- [ ] **Step 3.9: Verify typecheck + tests + lint**

```bash
npm run typecheck
npm --workspace=@infinityrx/ui test
npm run lint:root
```

Expected: typecheck exit 0, ~22 tests pass (11 prior + 4 Form + 4 AppShell + 3 DragHandle), lint exit 0.

- [ ] **Step 3.10: Commit**

```bash
git add packages/ui/
git commit -m "feat(ui): Plan C Task 3 — Form, FormField, AppShell, DragHandle

Form: react-hook-form FormProvider + zodResolver. Thin wrapper keeps
the form schema type-safe while hiding the hook setup boilerplate.
FormField: Controller wrapper with label + zod error message slot.
AppShell: children + optional header + optional nav slots. Children
render in <main>; nav slot is where Plan C-shell will mount the
dynamic module-nav. Omitting nav omits the aside region entirely.
DragHandle: dnd-kit useSortable handle — foundation for SP-6's
no-code program builder. Renders as a button with a11y aria-label.

~22 vitest tests total (TDD red-green). All pass.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 4: packages/ui — chart wrappers + command palette

**Files:**
- Create: `packages/ui/src/charts/KPICard.tsx`
- Create: `packages/ui/src/charts/LineChart.tsx`
- Create: `packages/ui/src/command/CommandPalette.tsx`
- Create: `packages/ui/src/__tests__/KPICard.test.tsx`
- Create: `packages/ui/src/__tests__/LineChart.test.tsx`
- Create: `packages/ui/src/__tests__/CommandPalette.test.tsx`
- Modify: `packages/ui/src/index.ts`

Note: recharts and cmdk are already listed in `packages/ui/package.json` from Task 1. No package.json change needed.

- [ ] **Step 4.1: Write `packages/ui/src/__tests__/KPICard.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KPICard } from "../charts/KPICard.js";

describe("KPICard", () => {
  it("renders the label", () => {
    render(<KPICard label="Total Claims" value="1,234" />);
    expect(screen.getByText("Total Claims")).toBeDefined();
  });

  it("renders the value", () => {
    render(<KPICard label="Total Claims" value="1,234" />);
    expect(screen.getByText("1,234")).toBeDefined();
  });

  it("renders positive delta badge", () => {
    render(<KPICard label="Claims" value="1,000" delta="+12%" />);
    expect(screen.getByText("+12%")).toBeDefined();
  });

  it("renders without delta when omitted", () => {
    const { container } = render(<KPICard label="Claims" value="1,000" />);
    expect(container.querySelector(".irx-kpi-card__delta")).toBeNull();
  });
});
```

- [ ] **Step 4.2: Write `packages/ui/src/charts/KPICard.tsx`**

```tsx
import * as React from "react";

export interface KPICardProps {
  label: string;
  value: string | number;
  delta?: string;
  className?: string;
}

/**
 * Simple KPI metric display: label + formatted value + optional delta badge.
 * No recharts dependency — pure CSS layout. Use LineChart for trend visualization.
 */
export function KPICard({ label, value, delta, className }: KPICardProps) {
  return (
    <div className={["irx-kpi-card", className].filter(Boolean).join(" ")}>
      <p className="irx-kpi-card__label">{label}</p>
      <p className="irx-kpi-card__value">{value}</p>
      {delta != null && (
        <span className="irx-kpi-card__delta">{delta}</span>
      )}
    </div>
  );
}
```

- [ ] **Step 4.3: Write `packages/ui/src/__tests__/LineChart.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LineChart } from "../charts/LineChart.js";

const data = [
  { month: "Jan", value: 100 },
  { month: "Feb", value: 120 },
];

describe("LineChart", () => {
  it("renders a chart container", () => {
    const { container } = render(
      <LineChart data={data} xKey="month" yKey="value" title="Claims Over Time" />,
    );
    expect(container.querySelector(".irx-line-chart")).toBeDefined();
  });

  it("renders the chart title", () => {
    render(<LineChart data={data} xKey="month" yKey="value" title="Claims Over Time" />);
    expect(screen.getByText("Claims Over Time")).toBeDefined();
  });

  it("renders without crashing on empty data", () => {
    const { container } = render(
      <LineChart data={[]} xKey="month" yKey="value" title="Empty" />,
    );
    expect(container.querySelector(".irx-line-chart")).toBeDefined();
  });
});
```

- [ ] **Step 4.4: Write `packages/ui/src/charts/LineChart.tsx`**

```tsx
import * as React from "react";
import {
  ResponsiveContainer,
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export interface LineChartProps<T extends Record<string, unknown>> {
  data: T[];
  xKey: keyof T & string;
  yKey: keyof T & string;
  title?: string;
  className?: string;
}

/**
 * Thin recharts wrapper. Enforces a consistent chart shape across portals.
 * For complex multi-line charts, compose directly from recharts primitives —
 * this component handles the single-line 80% case.
 */
export function LineChart<T extends Record<string, unknown>>({
  data,
  xKey,
  yKey,
  title,
  className,
}: LineChartProps<T>) {
  return (
    <div className={["irx-line-chart", className].filter(Boolean).join(" ")}>
      {title && <p className="irx-line-chart__title">{title}</p>}
      <ResponsiveContainer width="100%" height={200}>
        <RechartsLineChart data={data as object[]}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey={yKey} dot={false} />
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 4.5: Write `packages/ui/src/__tests__/CommandPalette.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette } from "../command/CommandPalette.js";

const items = [
  { id: "claims", label: "Go to Claims" },
  { id: "billing", label: "Go to Billing" },
];

describe("CommandPalette", () => {
  it("does not show when open is false", () => {
    render(<CommandPalette open={false} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows when open is true", () => {
    render(<CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("renders command items when open", () => {
    render(<CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.getByText("Go to Claims")).toBeDefined();
    expect(screen.getByText("Go to Billing")).toBeDefined();
  });

  it("calls onSelect with item id when item is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByText("Go to Claims"));
    expect(onSelect).toHaveBeenCalledWith("claims");
  });
});
```

Note: add `import { vi } from "vitest";` at the top.

- [ ] **Step 4.6: Write `packages/ui/src/command/CommandPalette.tsx`**

```tsx
import * as React from "react";
import { Command } from "cmdk";

export interface CommandItem {
  id: string;
  label: string;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: CommandItem[];
  onSelect: (id: string) => void;
  placeholder?: string;
}

/**
 * Thin cmdk wrapper. Renders as a Dialog — the host portal (Plan C-shell)
 * decides when to open it (typically keyboard shortcut Cmd+K / Ctrl+K).
 * Future: group items by category, add custom empty state, module-scoped items.
 */
export function CommandPalette({
  open,
  onOpenChange,
  items,
  onSelect,
  placeholder = "Search commands…",
}: CommandPaletteProps) {
  if (!open) return null;

  return (
    <div role="dialog" aria-modal="true" className="irx-command-palette">
      <Command>
        <Command.Input placeholder={placeholder} className="irx-command-palette__input" />
        <Command.List className="irx-command-palette__list">
          <Command.Empty>No results found.</Command.Empty>
          {items.map((item) => (
            <Command.Item
              key={item.id}
              value={item.id}
              onSelect={() => {
                onSelect(item.id);
                onOpenChange(false);
              }}
              className="irx-command-palette__item"
            >
              {item.label}
            </Command.Item>
          ))}
        </Command.List>
      </Command>
    </div>
  );
}
```

- [ ] **Step 4.7: Update `packages/ui/src/index.ts`**

```ts
// Public surface of @infinityrx/ui.

// Primitives
export { Button, type ButtonProps } from "./primitives/Button.js";
export { Input, type InputProps } from "./primitives/Input.js";
export { DataTable, type Column, type DataTableProps } from "./primitives/DataTable.js";

// Form
export { Form, type FormProps } from "./form/Form.js";
export { FormField, type FormFieldProps } from "./form/FormField.js";

// Shells
export { AppShell, type AppShellProps } from "./shells/AppShell.js";

// DnD
export { DragHandle, type DragHandleProps } from "./dnd/DragHandle.js";

// Charts
export { KPICard, type KPICardProps } from "./charts/KPICard.js";
export { LineChart, type LineChartProps } from "./charts/LineChart.js";

// Command
export { CommandPalette, type CommandPaletteProps, type CommandItem } from "./command/CommandPalette.js";
```

- [ ] **Step 4.8: Verify typecheck + tests + lint**

```bash
npm run typecheck
npm --workspace=@infinityrx/ui test
npm run lint:root
```

Expected: typecheck exit 0, ~32 tests pass (22 prior + 4 KPICard + 3 LineChart + 4 CommandPalette), lint exit 0.

- [ ] **Step 4.9: Commit**

```bash
git add packages/ui/
git commit -m "feat(ui): Plan C Task 4 — KPICard, LineChart, CommandPalette

KPICard: metric display with label + value + optional delta badge.
No recharts dep — pure CSS layout. 4 tests.
LineChart: thin recharts wrapper (ResponsiveContainer + Line + XAxis
+ YAxis + Tooltip + CartesianGrid). Single-line 80% case. 3 tests.
CommandPalette: thin cmdk wrapper rendered as a Dialog. Items are
id+label pairs; onSelect callback receives the id. 4 tests.

@infinityrx/ui is now complete: 10 components across 6 categories
(primitives, form, shells, dnd, charts, command). ~32 vitest tests.
All pass green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 5: packages/qa-harness — services-health + mock-toggle

**Files:**
- Create: `packages/qa-harness/src/services-health.tsx`
- Create: `packages/qa-harness/src/mock-toggle.tsx`
- Create: `packages/qa-harness/src/__tests__/services-health.test.tsx`
- Create: `packages/qa-harness/src/__tests__/mock-toggle.test.tsx`
- Modify: `packages/qa-harness/src/index.ts`

This task imports `BaseClient` from `@infinityrx/contract`. Because `@infinityrx/contract` is a peer dependency hoisted by the workspace, no additional package.json change is needed. However, the `tsconfig.json` for `packages/qa-harness` needs a `references` entry pointing to `packages/contract` so TypeScript resolves the types at build time.

- [ ] **Step 5.1: Update `packages/qa-harness/tsconfig.json` to add contract reference**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src",
    "jsx": "react-jsx"
  },
  "references": [
    { "path": "../contract" }
  ],
  "include": ["src/**/*.ts", "src/**/*.tsx"],
  "exclude": ["src/**/*.test.ts", "src/**/*.test.tsx", "src/__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 5.2: Write `packages/qa-harness/src/__tests__/services-health.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { BaseClient } from "@infinityrx/contract";
import { ServicesHealth } from "../services-health.js";

function makeMockClient(name: string, ok: boolean, latency_ms = 10): BaseClient {
  return {
    name,
    cachePolicies: {},
    probeHealth: vi.fn().mockResolvedValue({ ok, latency_ms, error: ok ? undefined : "timeout" }),
  };
}

describe("ServicesHealth", () => {
  it("shows service names", async () => {
    const clients = [makeMockClient("prescriber-directory", true)];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => expect(screen.getByText("prescriber-directory")).toBeDefined());
  });

  it("shows green status for a healthy service", async () => {
    const clients = [makeMockClient("prescriber-directory", true)];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => {
      expect(screen.getByText("healthy")).toBeDefined();
    });
  });

  it("shows red status for an unhealthy service", async () => {
    const clients = [makeMockClient("billing", false)];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => {
      expect(screen.getByText("unhealthy")).toBeDefined();
    });
  });

  it("shows latency for each service", async () => {
    const clients = [makeMockClient("prescriber-directory", true, 42)];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => {
      expect(screen.getByText(/42\s*ms/)).toBeDefined();
    });
  });

  it("shows the error message for an unhealthy service", async () => {
    const clients = [makeMockClient("billing", false)];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => {
      expect(screen.getByText("timeout")).toBeDefined();
    });
  });

  it("handles multiple clients", async () => {
    const clients = [
      makeMockClient("prescriber-directory", true),
      makeMockClient("billing", false),
    ];
    render(<ServicesHealth clients={clients} />);
    await waitFor(() => {
      expect(screen.getByText("prescriber-directory")).toBeDefined();
      expect(screen.getByText("billing")).toBeDefined();
    });
  });
});
```

- [ ] **Step 5.3: Write `packages/qa-harness/src/services-health.tsx`**

```tsx
import * as React from "react";
import type { BaseClient } from "@infinityrx/contract";

interface HealthResult {
  name: string;
  ok: boolean;
  latency_ms: number;
  error?: string;
}

export interface ServicesHealthProps {
  clients: BaseClient[];
  /** Poll interval in ms. Default 30000 (30s). Pass 0 to disable polling. */
  pollIntervalMs?: number;
  className?: string;
}

/**
 * Live health dashboard for all registered backend clients.
 * Renders per-service status: green/red, latency, error message.
 * Polls on mount and at pollIntervalMs intervals.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function ServicesHealth({ clients, pollIntervalMs = 30_000, className }: ServicesHealthProps) {
  const [results, setResults] = React.useState<HealthResult[]>([]);

  const probe = React.useCallback(async () => {
    const probed = await Promise.all(
      clients.map(async (c) => {
        try {
          const r = await c.probeHealth();
          return { name: c.name, ok: r.ok, latency_ms: r.latency_ms, error: r.error };
        } catch (err) {
          return { name: c.name, ok: false, latency_ms: 0, error: String(err) };
        }
      }),
    );
    setResults(probed);
  }, [clients]);

  React.useEffect(() => {
    void probe();
    if (pollIntervalMs > 0) {
      const id = setInterval(() => void probe(), pollIntervalMs);
      return () => clearInterval(id);
    }
  }, [probe, pollIntervalMs]);

  return (
    <div className={["irx-qa-services-health", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-services-health__title">Services Health</h2>
      <ul className="irx-qa-services-health__list">
        {results.map((r) => (
          <li key={r.name} className="irx-qa-services-health__item">
            <span className="irx-qa-services-health__name">{r.name}</span>
            <span className={`irx-qa-services-health__status irx-qa-services-health__status--${r.ok ? "ok" : "err"}`}>
              {r.ok ? "healthy" : "unhealthy"}
            </span>
            <span className="irx-qa-services-health__latency">{r.latency_ms} ms</span>
            {!r.ok && r.error && (
              <span className="irx-qa-services-health__error">{r.error}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 5.4: Write `packages/qa-harness/src/__tests__/mock-toggle.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseClient } from "@infinityrx/contract";
import { MockToggle } from "../mock-toggle.js";

function makeMockClient(name: string): BaseClient {
  return {
    name,
    cachePolicies: {},
    probeHealth: vi.fn().mockResolvedValue({ ok: true, latency_ms: 5 }),
  };
}

describe("MockToggle", () => {
  it("renders a toggle per client", () => {
    const clients = [makeMockClient("prescriber-directory"), makeMockClient("billing")];
    render(<MockToggle clients={clients} onToggle={() => {}} />);
    expect(screen.getByText("prescriber-directory")).toBeDefined();
    expect(screen.getByText("billing")).toBeDefined();
  });

  it("calls onToggle with (name, 'mock') when mock button clicked", async () => {
    const onToggle = vi.fn();
    const clients = [makeMockClient("prescriber-directory")];
    render(<MockToggle clients={clients} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole("button", { name: /mock/i }));
    expect(onToggle).toHaveBeenCalledWith("prescriber-directory", "mock");
  });

  it("calls onToggle with (name, 'real') when real button clicked", async () => {
    const onToggle = vi.fn();
    const clients = [makeMockClient("billing")];
    render(<MockToggle clients={clients} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole("button", { name: /real/i }));
    expect(onToggle).toHaveBeenCalledWith("billing", "real");
  });

  it("shows current mode for each client when initialModes provided", () => {
    const clients = [makeMockClient("prescriber-directory")];
    render(
      <MockToggle clients={clients} onToggle={() => {}} initialModes={{ "prescriber-directory": "mock" }} />,
    );
    expect(screen.getByText(/mock/)).toBeDefined();
  });
});
```

- [ ] **Step 5.5: Write `packages/qa-harness/src/mock-toggle.tsx`**

```tsx
import * as React from "react";
import type { BaseClient } from "@infinityrx/contract";

export type ClientMode = "real" | "mock";

export interface MockToggleProps {
  clients: BaseClient[];
  onToggle: (name: string, mode: ClientMode) => void;
  initialModes?: Record<string, ClientMode>;
  className?: string;
}

/**
 * Per-client real/mock toggle. Lets QA engineers switch any backend client
 * between its real and mock implementation at runtime without redeploying.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function MockToggle({ clients, onToggle, initialModes, className }: MockToggleProps) {
  const [modes, setModes] = React.useState<Record<string, ClientMode>>(
    initialModes ?? Object.fromEntries(clients.map((c) => [c.name, "real"])),
  );

  function toggle(name: string, mode: ClientMode) {
    setModes((prev) => ({ ...prev, [name]: mode }));
    onToggle(name, mode);
  }

  return (
    <div className={["irx-qa-mock-toggle", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-mock-toggle__title">Mock / Real Toggle</h2>
      <ul className="irx-qa-mock-toggle__list">
        {clients.map((c) => (
          <li key={c.name} className="irx-qa-mock-toggle__item">
            <span className="irx-qa-mock-toggle__name">{c.name}</span>
            <span className="irx-qa-mock-toggle__current">
              {modes[c.name] ?? "real"}
            </span>
            <button
              type="button"
              aria-label={`Switch ${c.name} to real`}
              className="irx-qa-mock-toggle__btn irx-qa-mock-toggle__btn--real"
              onClick={() => toggle(c.name, "real")}
            >
              real
            </button>
            <button
              type="button"
              aria-label={`Switch ${c.name} to mock`}
              className="irx-qa-mock-toggle__btn irx-qa-mock-toggle__btn--mock"
              onClick={() => toggle(c.name, "mock")}
            >
              mock
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 5.6: Update `packages/qa-harness/src/index.ts`**

```ts
// Public surface of @infinityrx/qa-harness.
// IMPORTANT: This package is a dev/staging tool. Omit from production builds.

export { ServicesHealth, type ServicesHealthProps } from "./services-health.js";
export { MockToggle, type MockToggleProps, type ClientMode } from "./mock-toggle.js";
```

- [ ] **Step 5.7: Verify typecheck + tests + lint**

```bash
npm run typecheck
npm --workspace=@infinityrx/qa-harness test
npm run lint:root
```

Expected: typecheck exit 0, 10/10 tests pass (6 ServicesHealth + 4 MockToggle), lint exit 0.

- [ ] **Step 5.8: Commit**

```bash
git add packages/qa-harness/
git commit -m "feat(qa-harness): Plan C Task 5 — ServicesHealth + MockToggle

ServicesHealth: fans out to BaseClient.probeHealth() for each client,
renders name + healthy/unhealthy status + latency_ms + error string.
Polls on mount (configurable interval, default 30s). 6 tests.
MockToggle: per-client real/mock toggle UI. Calls onToggle(name, mode)
callback. Maintains local mode state; initialModes prop seeds it.
4 tests.

Both components import BaseClient from @infinityrx/contract (peer dep).
Zero next/* imports — framework-agnostic.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 6: packages/qa-harness — composition viewer + factory bindings + correlation-id quick-jump

**Files:**
- Create: `packages/qa-harness/src/composition-viewer.tsx`
- Create: `packages/qa-harness/src/factory-bindings.tsx`
- Create: `packages/qa-harness/src/correlation-id-jump.tsx`
- Create: `packages/qa-harness/src/__tests__/composition-viewer.test.tsx`
- Create: `packages/qa-harness/src/__tests__/factory-bindings.test.tsx`
- Create: `packages/qa-harness/src/__tests__/correlation-id-jump.test.tsx`
- Modify: `packages/qa-harness/src/index.ts`

- [ ] **Step 6.1: Write `packages/qa-harness/src/__tests__/composition-viewer.test.tsx` (failing first)**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CompositionViewer } from "../composition-viewer.js";

const manifest = { modules: ["reclaimrx", "paysync", "directories"] };

describe("CompositionViewer", () => {
  it("renders a heading", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText(/composition/i)).toBeDefined();
  });

  it("renders each module name from the manifest", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText("reclaimrx")).toBeDefined();
    expect(screen.getByText("paysync")).toBeDefined();
    expect(screen.getByText("directories")).toBeDefined();
  });

  it("shows module count", () => {
    render(<CompositionViewer manifest={manifest} />);
    expect(screen.getByText(/3/)).toBeDefined();
  });

  it("renders empty state when manifest has no modules", () => {
    render(<CompositionViewer manifest={{ modules: [] }} />);
    expect(screen.getByText(/no modules/i)).toBeDefined();
  });

  it("accepts an optional instance label", () => {
    render(<CompositionViewer manifest={manifest} instanceLabel="operator-dev" />);
    expect(screen.getByText("operator-dev")).toBeDefined();
  });
});
```

- [ ] **Step 6.2: Write `packages/qa-harness/src/composition-viewer.tsx`**

```tsx
import * as React from "react";

export interface CompositionManifest {
  /** The list of module names included in this build. */
  modules: string[];
}

export interface CompositionViewerProps {
  manifest: CompositionManifest;
  /** Optional human-readable instance label (e.g. "operator-dev", "reclaimrx-standalone"). */
  instanceLabel?: string;
  className?: string;
}

/**
 * Renders the deployment composition for QA verification:
 * "This build contains: reclaimrx, paysync" — proves the deployment manifest
 * produced the expected artifact. Takes a `manifest` prop.
 *
 * Plan C-shell is responsible for fetching the runtime manifest from
 * `packages/shell/src/_generated/manifest.json` and passing it here.
 * Plan C's component is prop-driven to stay framework-agnostic.
 *
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function CompositionViewer({ manifest, instanceLabel, className }: CompositionViewerProps) {
  return (
    <div className={["irx-qa-composition", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-composition__heading">Build Composition</h2>
      {instanceLabel && (
        <p className="irx-qa-composition__instance">{instanceLabel}</p>
      )}
      {manifest.modules.length === 0 ? (
        <p className="irx-qa-composition__empty">No modules in this build.</p>
      ) : (
        <>
          <p className="irx-qa-composition__count">{manifest.modules.length} module(s) included</p>
          <ul className="irx-qa-composition__list">
            {manifest.modules.map((mod) => (
              <li key={mod} className="irx-qa-composition__module">{mod}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6.3: Write `packages/qa-harness/src/__tests__/factory-bindings.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FactoryBindings } from "../factory-bindings.js";

const bindings = [
  { kind: "tenant+prescribers+claims", label: "Seed: 1 tenant + 10 prescribers + 5 claims" },
  { kind: "fwa-sample", label: "Seed: FWA sample data" },
];

describe("FactoryBindings", () => {
  it("renders a button per binding", () => {
    render(<FactoryBindings bindings={bindings} seed={() => Promise.resolve()} />);
    expect(screen.getByRole("button", { name: /tenant.*prescribers/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /fwa/i })).toBeDefined();
  });

  it("calls seed with the binding kind when clicked", async () => {
    const seed = vi.fn().mockResolvedValue(undefined);
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(seed).toHaveBeenCalledWith("fwa-sample");
  });

  it("shows loading state while seed is in progress", async () => {
    let resolve!: () => void;
    const seed = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r; }));
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(screen.getByText(/seeding/i)).toBeDefined();
    resolve();
  });

  it("shows success message after seed resolves", async () => {
    const seed = vi.fn().mockResolvedValue(undefined);
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(await screen.findByText(/seeded/i)).toBeDefined();
  });
});
```

- [ ] **Step 6.4: Write `packages/qa-harness/src/factory-bindings.tsx`**

```tsx
import * as React from "react";

export interface SeedBinding {
  /** Machine key passed to the seed callback. e.g. "tenant+prescribers+claims" */
  kind: string;
  /** Human-readable button label. */
  label: string;
}

export interface FactoryBindingsProps {
  bindings: SeedBinding[];
  /** Async callback invoked with the binding kind. Should seed the dev DB. */
  seed: (kind: string) => Promise<void>;
  className?: string;
}

type SeedState = "idle" | "seeding" | "seeded" | "error";

/**
 * Renders buttons to seed safe, non-PHI fixtures into the dev DB.
 * Each button is associated with a binding kind — the host portal defines what
 * each kind seeds (e.g. "1 tenant + 10 prescribers + 5 claims").
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function FactoryBindings({ bindings, seed, className }: FactoryBindingsProps) {
  const [states, setStates] = React.useState<Record<string, SeedState>>(
    Object.fromEntries(bindings.map((b) => [b.kind, "idle"])),
  );

  async function handleSeed(kind: string) {
    setStates((prev) => ({ ...prev, [kind]: "seeding" }));
    try {
      await seed(kind);
      setStates((prev) => ({ ...prev, [kind]: "seeded" }));
    } catch {
      setStates((prev) => ({ ...prev, [kind]: "error" }));
    }
  }

  return (
    <div className={["irx-qa-factory", className].filter(Boolean).join(" ")}>
      <h2 className="irx-qa-factory__title">Test Data Factory</h2>
      <ul className="irx-qa-factory__list">
        {bindings.map((b) => {
          const state = states[b.kind] ?? "idle";
          return (
            <li key={b.kind} className="irx-qa-factory__item">
              <button
                type="button"
                className="irx-qa-factory__btn"
                disabled={state === "seeding"}
                onClick={() => void handleSeed(b.kind)}
              >
                {b.label}
              </button>
              {state === "seeding" && <span className="irx-qa-factory__status">Seeding…</span>}
              {state === "seeded" && <span className="irx-qa-factory__status">Seeded.</span>}
              {state === "error" && <span className="irx-qa-factory__status irx-qa-factory__status--err">Error</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 6.5: Write `packages/qa-harness/src/__tests__/correlation-id-jump.test.tsx` (failing first)**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CorrelationIdJump } from "../correlation-id-jump.js";

describe("CorrelationIdJump", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    });
  });

  it("renders an input field", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("renders a copy button", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.getByRole("button", { name: /copy/i })).toBeDefined();
  });

  it("calls navigator.clipboard.writeText with the correlation id when copy is clicked", async () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    await userEvent.type(screen.getByRole("textbox"), "550e8400-e29b-41d4-a716-446655440000");
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "550e8400-e29b-41d4-a716-446655440000",
    );
  });

  it("renders a log-search link when a correlation id is typed", async () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    await userEvent.type(screen.getByRole("textbox"), "abc-123");
    expect(screen.getByRole("link")).toBeDefined();
    expect((screen.getByRole("link") as HTMLAnchorElement).href).toContain("abc-123");
  });

  it("does not render a link when the input is empty", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
```

- [ ] **Step 6.6: Write `packages/qa-harness/src/correlation-id-jump.tsx`**

```tsx
import * as React from "react";

export interface CorrelationIdJumpProps {
  /**
   * Base URL of the log-search route. The correlation id is appended as
   * a `q` query param: `{logSearchBaseUrl}?q={correlationId}`.
   * Example: "https://logs.example.com/search"
   */
  logSearchBaseUrl: string;
  className?: string;
}

/**
 * Dev tool: paste a correlation_id to copy it to clipboard and open the
 * matching backend log entry in one click.
 * IMPORTANT: Omit from production builds — dev/staging only.
 */
export function CorrelationIdJump({ logSearchBaseUrl, className }: CorrelationIdJumpProps) {
  const [correlationId, setCorrelationId] = React.useState("");

  const logUrl = correlationId.trim()
    ? `${logSearchBaseUrl}?q=${encodeURIComponent(correlationId.trim())}`
    : null;

  async function handleCopy() {
    if (correlationId.trim()) {
      await navigator.clipboard.writeText(correlationId.trim());
    }
  }

  return (
    <div className={["irx-qa-correlation-jump", className].filter(Boolean).join(" ")}>
      <label htmlFor="irx-correlation-input" className="irx-qa-correlation-jump__label">
        Correlation ID
      </label>
      <div className="irx-qa-correlation-jump__row">
        <input
          id="irx-correlation-input"
          type="text"
          className="irx-qa-correlation-jump__input"
          value={correlationId}
          onChange={(e) => setCorrelationId(e.target.value)}
          placeholder="Paste correlation_id…"
        />
        <button
          type="button"
          aria-label="Copy correlation id to clipboard"
          className="irx-qa-correlation-jump__copy"
          onClick={() => void handleCopy()}
        >
          Copy
        </button>
        {logUrl && (
          <a
            href={logUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="irx-qa-correlation-jump__link"
          >
            Open in logs
          </a>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6.7: Update `packages/qa-harness/src/index.ts`**

```ts
// Public surface of @infinityrx/qa-harness.
// IMPORTANT: This package is a dev/staging tool. Omit from production builds.

export { ServicesHealth, type ServicesHealthProps } from "./services-health.js";
export { MockToggle, type MockToggleProps, type ClientMode } from "./mock-toggle.js";
export { CompositionViewer, type CompositionViewerProps, type CompositionManifest } from "./composition-viewer.js";
export { FactoryBindings, type FactoryBindingsProps, type SeedBinding } from "./factory-bindings.js";
export { CorrelationIdJump, type CorrelationIdJumpProps } from "./correlation-id-jump.js";
```

- [ ] **Step 6.8: Verify typecheck + tests + lint**

```bash
npm run typecheck
npm --workspace=@infinityrx/qa-harness test
npm run lint:root
```

Expected: typecheck exit 0, ~24 tests pass (10 prior + 5 CompositionViewer + 4 FactoryBindings + 5 CorrelationIdJump), lint exit 0.

- [ ] **Step 6.9: Commit**

```bash
git add packages/qa-harness/
git commit -m "feat(qa-harness): Plan C Task 6 — CompositionViewer, FactoryBindings, CorrelationIdJump

CompositionViewer: renders manifest.modules[] list. Takes a prop
instead of fetching manifest.json directly so it stays framework-
agnostic — Plan C-shell wires the runtime fetch. 5 tests.
FactoryBindings: per-binding seed buttons with loading/seeded/error
state. seed(kind) callback is the host's responsibility. 4 tests.
CorrelationIdJump: correlation_id input + clipboard copy + log-search
URL link (logSearchBaseUrl?q=). 5 tests.

@infinityrx/qa-harness is now complete: 5 components. ~24 vitest
tests. All pass green.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

### Task 7: framework-agnostic enforcement tests + acceptance doc

**Files:**
- Create: `packages/ui/src/__tests__/framework-agnostic.test.ts`
- Create: `packages/qa-harness/src/__tests__/framework-agnostic.test.ts`
- Create: `docs/superpowers/plans/2026-05-15-sp0-plan-c-status.md`

- [ ] **Step 7.1: Write `packages/ui/src/__tests__/framework-agnostic.test.ts`**

Same walking-scan pattern as Plan B Task 7.1 — adapted for `packages/ui/src/`:

```ts
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(here, "..");

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else if (entry.endsWith(".ts") || entry.endsWith(".tsx")) files.push(full);
  }
  return files;
}

const FORBIDDEN_IMPORTS = [
  /from\s+["']next\//,
  /from\s+["']next-auth\//,
  /from\s+["']@auth\//,
  /require\(\s*["']next\//,
  /require\(\s*["']next-auth\//,
  /require\(\s*["']@auth\//,
];

describe("framework-agnostic enforcement — packages/ui", () => {
  const tsFiles = walk(SRC_DIR);

  it("there is at least one .ts/.tsx file under packages/ui/src/", () => {
    expect(tsFiles.length).toBeGreaterThan(0);
  });

  for (const file of tsFiles) {
    it(`${file.replace(SRC_DIR, "")} does not import Next.js / next-auth / @auth/*`, () => {
      const contents = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_IMPORTS) {
        expect(contents, `forbidden import matching ${pattern} in ${file}`).not.toMatch(pattern);
      }
    });
  }
});
```

- [ ] **Step 7.2: Write `packages/qa-harness/src/__tests__/framework-agnostic.test.ts`**

Same content as Step 7.1, with `SRC_DIR` resolving to `packages/qa-harness/src/` and the describe label updated:

```ts
import { describe, it, expect } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const SRC_DIR = join(here, "..");

function walk(dir: string, files: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    if (entry === "__tests__") continue;
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, files);
    else if (entry.endsWith(".ts") || entry.endsWith(".tsx")) files.push(full);
  }
  return files;
}

const FORBIDDEN_IMPORTS = [
  /from\s+["']next\//,
  /from\s+["']next-auth\//,
  /from\s+["']@auth\//,
  /require\(\s*["']next\//,
  /require\(\s*["']next-auth\//,
  /require\(\s*["']@auth\//,
];

describe("framework-agnostic enforcement — packages/qa-harness", () => {
  const tsFiles = walk(SRC_DIR);

  it("there is at least one .ts/.tsx file under packages/qa-harness/src/", () => {
    expect(tsFiles.length).toBeGreaterThan(0);
  });

  for (const file of tsFiles) {
    it(`${file.replace(SRC_DIR, "")} does not import Next.js / next-auth / @auth/*`, () => {
      const contents = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_IMPORTS) {
        expect(contents, `forbidden import matching ${pattern} in ${file}`).not.toMatch(pattern);
      }
    });
  }
});
```

- [ ] **Step 7.3: Run full CI sequence locally**

```bash
npm install
npm run lint:root
npm run typecheck
npm run manifest:validate
npm run manifest:validate:standalone
npm run test:packages
```

Expected: all exit 0. `test:packages` runs scripts (10) + contract (25) + auth (~39) + ui (~43+) + qa-harness (~24+) = ~141+ total tests. All pass.

- [ ] **Step 7.4: Write acceptance status doc**

Create `docs/superpowers/plans/2026-05-15-sp0-plan-c-status.md` following the Plan A/B status doc pattern. Include:
- Status: Complete `<date>`
- Final commit SHA (filled in after Step 7.5 commit)
- Table of task SHAs (Plan C Tasks 1-7)
- What ships: `packages/ui` (10 components — Button, Input, DataTable, Form, FormField, AppShell, DragHandle, KPICard, LineChart, CommandPalette) + `packages/qa-harness` (5 components — ServicesHealth, MockToggle, CompositionViewer, FactoryBindings, CorrelationIdJump)
- What is NOT in Plan C: full design-system catalog, TanStack Table virtualization, full recharts suite, Tailwind design tokens, portal wiring (Plan C-shell), `packages/shell` (Plan C-shell)
- Verification commands + results
- Decision: ready for Plan C-shell (packages/shell — Next.js host wiring)

- [ ] **Step 7.5: Commit Task 7 + Plan C status doc**

```bash
git add packages/ui/ packages/qa-harness/ docs/superpowers/plans/2026-05-15-sp0-plan-c-status.md
git commit -m "feat(sp-0): Plan C Task 7 — framework-agnostic tests + acceptance doc

framework-agnostic.test.ts in packages/ui and packages/qa-harness:
walks src/ (skips __tests__/) and asserts no .ts/.tsx file matches
/from ['\"]next\\// or /from ['\"]next-auth\\// or /from ['\"]@auth\\//.
Belt-and-suspenders check on top of Plan A's ESLint Block B.

Full CI sequence passes: lint:root, typecheck, manifest:validate x2,
test:packages. ~141+ total tests across all 5 packages.

Plan C status doc: task SHAs, ships list, deferred scope, decision:
ready for Plan C-shell.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Plan C — Done

After Task 7's commit, Plan C is complete. The repo now has `packages/ui` + `packages/qa-harness` wired through the workspace, both passing tests, both lint-clean, both type-checked, both framework-agnostic, and covered by the CI test:packages workflow.

Plan C-shell scope: `packages/shell` — Next.js App Router host layer (routing, auth integration, module mounting, nav, command palette wiring, BFF route handlers). Written and executed after Plan C execution lands.

---

## Self-Review Checklist (applied 2026-05-15)

### Spec coverage

| Spec section | Plan C covers? | Notes |
|---|---|---|
| Main spec §6.3 packages/ui | YES — reference set | 10 components across 6 categories. Full catalog is deferred by design (verticals build on top). |
| Main spec §6.3 — dnd-kit primitives (SP-6 foundation) | YES | DragHandle uses @dnd-kit/sortable, is tested, ships in index.ts |
| Main spec §6.3 — chart/table/form wrappers | YES — reference set | KPICard + LineChart (charts), Form + FormField (form), DataTable (table). TanStack Table full integration is future. |
| Main spec §6.3 — command palette host | YES | CommandPalette wraps cmdk; Plan C-shell wires the Cmd+K keyboard shortcut |
| Main spec §6.4 packages/qa-harness | PARTIAL — 5 of 7 tool categories covered | Covered in Plan C: services-health dashboard, mock/real toggle, composition viewer (prop-driven), factory-bindings, correlation_id quick-jump. **Explicitly deferred to Plan C-shell** (need Next.js route context): QA mode toggle (which mounts inside a Next.js route), request/response inspector (needs request lifecycle hooks). The shell plan will add these as additional qa-harness components or as shell-owned panels that consume qa-harness primitives. |
| SD-2 framework-agnostic mandate | YES | Zero next/* in both packages. Enforced by ESLint Block B + framework-agnostic.test.ts in both. |
| SD-4 §4 workspace ESLint Block B | INHERITED | No per-package ESLint config needed; workspace-root config already covers packages/**. |

### Placeholder scan

Searched the plan for "TBD", "TODO", "implement later", "fill in", "Add appropriate", "similar to". None found. Every step has either complete code, exact commands, or an exact file path with content elsewhere in the plan.

### Type consistency

- `BaseClient` imported from `@infinityrx/contract` in `packages/qa-harness` with a proper `references` entry in tsconfig.json (Step 5.1).
- `VariantProps<typeof buttonVariants>` used correctly in `Button.tsx` — extends `React.ButtonHTMLAttributes`, not replaces it.
- `DataTable<T extends object>` is a generic component — callers don't need to specify `T` explicitly, TypeScript infers from `columns` + `rows`.
- `Form<T extends FieldValues>` carries the zod schema type through `DefaultValues<T>` and `onSubmit: (data: T) => void`.
- `FormField<T extends FieldValues>` uses `Path<T>` for the `name` prop — constrains field names to actual schema keys at compile time.
- All imports use `.js` extensions (NodeNext + verbatimModuleSyntax requirement).
- `LineChart<T extends Record<string, unknown>>` — generic over data shape; `xKey` and `yKey` are `keyof T & string` to satisfy recharts's `dataKey` (which expects `string`, not `symbol`).

No issues found.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-15-sp0-plan-c-host-layer.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, two-stage review per `superpowers:subagent-driven-development`. Task dependency order: 1 → 2 → 3 → 4 (ui tasks are sequential, each building on the prior index.ts); 1 → 5 → 6 (qa-harness tasks are sequential); tasks 2-4 and 5-6 can run in parallel streams after Task 1. Task 7 waits on all prior tasks.

**2. Inline Execution** — batch via `superpowers:executing-plans`. Safer choice if subagent budget is limited.

**Before execution:**
- Confirm Plan B Task 7 commit (`9b144e9`) is the current HEAD on `wave/B10-w5` (or the branch Plan C will execute on).
- Verify `npm run typecheck` + `npm run test:packages` pass cleanly on the base branch before starting Task 1.

**After Task 7:**
- Codex review the full diff before merging.
- Write Plan C-shell (packages/shell — Next.js host layer) after Plan C execution is confirmed green.

---
