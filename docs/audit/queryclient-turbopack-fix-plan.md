# QueryClient Turbopack Dual-Instance Fix Plan

**Date:** 2026-05-20  
**Status:** PLAN — awaiting execution  
**Bug:** `Error: No QueryClient set, use QueryClientProvider to set one` on directories detail pages (and some list pages) under `next dev --turbopack`.

---

## 1. Root Cause Analysis

### 1.1 The Mechanism

`next.config.ts` lists these packages in `transpilePackages`:

```
["@infinityrx/portal-shared", "@infinityrx/module-directories",
 "@infinityrx/module-paysync", "@infinityrx/shell", "@infinityrx/ui"]
```

When Turbopack sees a package in `transpilePackages`, it bypasses the package's `exports` field (which points to `dist/`) and instead resolves the package's *source TypeScript files* directly. For `@infinityrx/module-directories`, that means Turbopack compiles `packages/modules/directories/src/**.tsx` as part of the portal's own compilation graph.

Those source files contain:
```ts
import { useQuery } from "@tanstack/react-query";
```

Turbopack resolves this import **from the context of `packages/modules/directories/`**, which walks up to `node_modules/@tanstack/react-query` — the same single physical copy at the repo root. **However**, Turbopack treats modules imported via `transpilePackages` source-mode as belonging to a separate "chunking context" from the portal's own app code. This is the documented Turbopack limitation: `resolveAlias` to an absolute path fails with "chunking context does not support external modules" precisely because Turbopack's module graph has two separate contexts that cannot share an external reference.

The result: `@tanstack/react-query`'s `QueryClientContext` is instantiated **twice** — once in the portal's app context (used by `<QueryClientProvider>` in `providers/index.tsx`) and once in the transpiled-source context (used by `useQuery` in module components). Different context object = `useQuery` looks up an empty context = the error.

### 1.2 Why List Pages Sometimes Work / Detail Pages Always Crash

Both list and detail pages import from `@infinityrx/module-directories` identically (no structural difference in the import). The reported asymmetry is likely:

- **List pages** use a single `useQuery` at the top level — React may defer the context lookup until the first render tick, which can succeed if the provider renders before the component.
- **Detail pages** use **multiple** `useQuery` calls (e.g., `DrugDetailPage` has 4 calls, `PharmacyDetailPage` has 2, `PrescriberDetailPage` likely similar). Multiple calls compound the likelihood of hitting the context boundary before the first successful render, making them reliably crash.
- Tabs introduce `useState` + conditional `enabled:` queries, which re-trigger context lookup on every tab switch even if the first render marginally succeeded.

The core bug is identical in both; detail pages are just more exposed.

### 1.3 What Does NOT Compound the Problem

Verified by inspection:
- `@infinityrx/shell` — does **not** import `@tanstack/react-query` (confirmed: no matches in `packages/shell/src/`).
- `@infinityrx/ui` — does **not** import `@tanstack/react-query` (confirmed: no matches; `recharts` is a dep but is not a context-using singleton).
- `@infinityrx/portal-shared` — does **not** import `@tanstack/react-query` (confirmed by inspection of source).
- Node module dedup: only **one** physical copy of `@tanstack/react-query` at `node_modules/@tanstack/react-query` (version 5.100.11). The dedup is fine. The problem is Turbopack's module graph, not npm's disk layout.

### 1.4 Why the Already-Tried Fixes Failed

| Attempted Fix | Why It Failed |
|---|---|
| `turbopack.resolveAlias` to absolute Windows path | Turbopack error: "chunking context does not support external modules" — absolute-path aliases are treated as externals when crossing chunking context boundaries |
| `resolveAlias` to forward-slash absolute path | Same error; the chunking context boundary is the problem, not the path format |
| `resolveAlias` to root-relative path (`"./node_modules/..."`) | Builds clean (stays within the context) but does NOT create a shared singleton — both contexts still each evaluate their own copy of the module's ES module scope |
| peerDependency + single physical copy | Prevents npm from installing a second copy on disk but does nothing about Turbopack's in-memory module graph |

The `resolveAlias` approach is fundamentally the wrong lever for this class of problem. Turbopack module graphs are not merged by alias alone when `transpilePackages` source-mode is in effect.

---

## 2. Candidate Approaches (Evaluated)

### Option A — Remove from `transpilePackages`, use compiled `dist/` (RECOMMENDED PRIMARY)

**How it works:** Remove `@infinityrx/module-directories` (and `@infinityrx/module-paysync`) from `transpilePackages`. Next.js will then resolve these packages via their `exports` field, which points to `dist/src/index.js` — pre-compiled JavaScript. Turbopack loads these as normal node_modules (no source-mode compilation). Their `import { useQuery } from "@tanstack/react-query"` inside the dist JS resolves from within the portal's app module graph, sharing the same module instance as `providers/index.tsx`.

**Evidence the dist already exists and is correct:**
- `packages/modules/directories/dist/src/surfaces/pharmacies/PharmacyDetailPage.js` exists and contains valid compiled ES module output with `"use client"` preserved at line 1.
- `packages/modules/directories/dist/src/surfaces/drugs/DrugsListPage.js` exists with correct output.
- The `package.json` `exports` field correctly points to `./dist/src/index.js`.
- tsc `composite: true` is configured — the build is incremental.

**tsc build errors (pre-existing, not caused by this fix):**
The task description notes tsc failed previously due to:
1. Unused React imports in TSX files — caused by `noUnusedLocals: true` in `tsconfig.base.json` combined with old `React` explicit imports. The dist files already contain `import React from "react"` preserved in output (compiled correctly by tsc's `jsx: react-jsx`). Any new unused-import errors would be in files NOT yet in dist.
2. Missing `next/server` type errors — `@infinityrx/module-directories`'s `tsconfig.json` references only `auth`, `contract`, `qa-harness`, `ui` — it does NOT reference `next` or `shell`. The `next/server` errors would be in `packages/shell` or BFF files, not in the UI surface components.

**Verdict on tsc errors:** The UI surface components (pharmacies, drugs, prescribers, etc.) that use react-query are already compiled successfully in `dist/` — those files exist and are valid. The tsc failures that blocked a full clean build are in OTHER files (likely BFF/server-side imports). Removing `module-directories` from `transpilePackages` uses the existing `dist/`, which is already correct for the UI surfaces. The tsc error issue is orthogonal.

**Exact file change:**

`portal/operator/next.config.ts` — remove `@infinityrx/module-directories` and `@infinityrx/module-paysync` from `transpilePackages`:

```diff
-  transpilePackages: ["@infinityrx/portal-shared", "@infinityrx/module-directories", "@infinityrx/module-paysync", "@infinityrx/shell", "@infinityrx/ui"],
+  transpilePackages: ["@infinityrx/portal-shared", "@infinityrx/shell", "@infinityrx/ui"],
```

**Required follow-up:** After making this change, ensure `dist/` is up to date before running `next dev`. Add a prebuild step or document that `npm run build -w @infinityrx/module-directories` must be run after source changes to the module.

**Risk:** Hot module replacement (HMR) for `module-directories` source changes will NOT work — you must rebuild the dist to see changes. This is acceptable for a stable SP-2 module; it is the standard "compiled internal package" pattern used by most large Next.js monorepos.

---

### Option B — Host `QueryClientProvider` in a shared package (SECONDARY — more invasive)

**How it works:** Move `QueryClient` creation and `<QueryClientProvider>` into a new export in `@infinityrx/portal-shared`. Both the portal's `providers/index.tsx` and any module that needs a `QueryClient` reference would import from `portal-shared`, which is already in `transpilePackages` and is a source-mode singleton. Since all code importing from `portal-shared` shares the same Turbopack source-mode graph context, `QueryClientContext` is only created once.

**Why this is secondary (not primary):**
- `@infinityrx/portal-shared` is intentionally kept "server-safe only" (its own barrel comment says no `"use client"` modules in the root export). Adding QueryClientProvider would require either violating that constraint or adding a new subpath export.
- The module packages (`module-directories`, `module-paysync`) currently DON'T import from `portal-shared` — adding that dependency changes the module isolation model.
- It solves the symptom (shared context) but not the root cause (Turbopack dual-module-graph). If a third package with `useQuery` is added later without importing from `portal-shared`, the bug returns.
- Option A is cleaner and aligns with how the packages are designed (they have dist/).

**Exact changes if pursued:**

1. Add `@tanstack/react-query` as a dependency (not just peerDep) in `packages/portal-shared/package.json`.
2. Create `packages/portal-shared/components/query-provider.tsx` with `"use client"` + `QueryClientProvider` export.
3. Update `portal/operator/components/providers/index.tsx` to import from `@infinityrx/portal-shared/components/query-provider`.
4. Update `@infinityrx/module-directories` package.json to add `@infinityrx/portal-shared` as a dependency.
5. Update module components to NOT call `useQuery` directly but instead access via a shared hook from `portal-shared`.

This is too invasive for what is a Turbopack config fix.

---

### Option C — Turbopack canonical dedup mechanism for `transpilePackages` singletons

**Research finding:** Searched Next.js docs, GitHub issues #85316, #63230, #64412, #88540, and multiple community posts. **There is no supported Turbopack configuration to force module deduplication across `transpilePackages` source-mode boundaries.** The two documented mechanisms that exist are:

1. `resolveAlias` — maps an import specifier to a different path. Fails with "external module" error for cross-context use (already tried).
2. `serverExternalPackages` — opts packages OUT of bundling entirely (server only; irrelevant for client components).

The canonical community fix for this class of problem (confirmed in TanStack/query discussion #5452 and multiple Turborepo discussions) is: **do not use `transpilePackages` for packages that have singleton context dependencies — use the compiled dist instead.** This is identical to Option A.

There is an open Next.js issue (#85316, filed Oct 2025) requesting that Turbopack properly handle monorepo `transpilePackages` for this case. No ETA or fix shipped as of 2026-05-20.

---

### Option D — Mark `@tanstack/react-query` as a Turbopack external chunk (NOT viable)

There is no supported Turbopack configuration for this. The `resolveAlias` approach was the closest analog and has already been proven to fail. Turbopack does not expose webpack's `externals` array for arbitrary packages. `serverExternalPackages` exists but only applies to server-side rendering, not client component hydration.

---

## 3. Recommended Fix Plan (Ranked)

### Step 1 — Immediate fix (Option A, ~5 min)

**File:** `portal/operator/next.config.ts`

Remove `@infinityrx/module-directories` and `@infinityrx/module-paysync` from `transpilePackages`. The compiled `dist/` for `module-directories` already exists and is correct. The `dist/` for `module-paysync` should be verified before removal.

```ts
// BEFORE
transpilePackages: ["@infinityrx/portal-shared", "@infinityrx/module-directories", "@infinityrx/module-paysync", "@infinityrx/shell", "@infinityrx/ui"],

// AFTER
transpilePackages: ["@infinityrx/portal-shared", "@infinityrx/shell", "@infinityrx/ui"],
```

**Also update the comment on line 41-47 in next.config.ts** to reflect that `module-directories` and `module-paysync` are now consumed as compiled dist, not source-mode.

**Verify `module-paysync` dist exists** before removing — check `packages/modules/paysync/dist/src/index.js`. If it does not exist, run `npm run build -w @infinityrx/module-paysync` first. (READ-ONLY investigation: dist existence for paysync was not checked; must be verified before executing this fix.)

### Step 2 — Add a prebuild guard (~15 min)

The portal's `package.json` `dev` script is `next dev --turbopack`. Since the modules are now consumed as dist, stale dist will cause silent runtime regressions. Add a dev-time guard:

**Option 2a (npm workspace prebuild):** Add to `portal/operator/package.json` scripts:
```json
"prebuild:modules": "npm run build -w @infinityrx/module-directories && npm run build -w @infinityrx/module-paysync",
"dev": "npm run prebuild:modules && next dev --turbopack"
```

**Option 2b (tsc watch):** In a separate terminal, run `tsc -b --watch` from `packages/modules/directories/` during development. This rebuilds dist on every source change, giving near-HMR behavior. Document this in the module's README.

Option 2a is simpler for CI and "just start dev" UX. Option 2b is better DX for active module development.

### Step 3 — Verify the fix (~5 min)

After applying Step 1:
1. `next dev --turbopack` (or `npm run dev` with the prebuild guard)
2. Navigate to `/directories/pharmacies/{any-npi}` — should not crash
3. Navigate to `/directories/drugs/{any-ndc}` — should not crash  
4. Click tabs on a detail page — should not crash
5. Navigate to `/directories/pharmacies` (list) — confirm still works

### Step 4 — Long-term: watch Next.js issue #85316

If/when Vercel fixes Turbopack's handling of `transpilePackages` for monorepo singleton context, the packages can be moved back to `transpilePackages` for better DX (HMR of module source). Until then, dist-mode is the correct pattern.

---

## 4. Why the Detail Page Bug Is More Severe Than List Pages

Both use identical imports. The detail pages call `useQuery` **multiple times** (2–4 calls per page) and the DrugDetailPage calls `useQuery` conditionally inside a `useState`-gated `enabled:` pattern. Under Turbopack's dual-graph behavior:

- First render: React reconciler processes the portal's component tree. `QueryClientProvider` installs a `QueryClient` into **Context A** (portal's module graph copy of react-query).
- When `PharmacyDetailPage` or `DrugDetailPage` renders, `useQuery` reads **Context B** (module-directories' module graph copy of react-query). Context B has never had a `QueryClientProvider` render above it — it is empty. The error fires immediately.
- List pages with a single `useQuery` call **may** survive in certain render orders or if cached from a prior navigation, but this is not reliable and will also break.

The 9/9 pharmacy-detail crash rate in the task description is consistent with this: the second `useQuery` call (`pharmacy-prescribers`) ensures the crash even if the first call coincidentally completes.

---

## 5. Summary Table

| Option | Viable? | DX Impact | Invasiveness | Time to Implement |
|---|---|---|---|---|
| A: Remove from transpilePackages, use dist | YES — RECOMMENDED | Lose HMR for module source | 1 line change | 5 min |
| B: Shared QueryClientProvider in portal-shared | Viable but over-engineered | None | High — 5+ file changes | 2+ hours |
| C: Turbopack native dedup config | NO — does not exist | N/A | N/A | N/A |
| D: Mark as Turbopack external chunk | NO — not supported | N/A | N/A | N/A |

---

## 6. File Change Inventory (Option A)

| File | Change |
|---|---|
| `portal/operator/next.config.ts` | Remove `@infinityrx/module-directories`, `@infinityrx/module-paysync` from `transpilePackages`; update comment |
| `portal/operator/package.json` | Add `prebuild:modules` script and update `dev` script (recommended) |
| `packages/modules/directories/` | No change — dist/ already exists |
| `packages/modules/paysync/` | No change if dist/ exists; run build if not |

No changes to app/, components/, or any module source files.
