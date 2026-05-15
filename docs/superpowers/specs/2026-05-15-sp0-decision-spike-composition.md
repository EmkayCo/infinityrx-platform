# SP-0 Decision Spike — Composition Mechanism

**Status:** v2 drafted 2026-05-15 incorporating codex pass-1 findings (3 BLOCK + 3 CONCERN): bypass paths in import enforcement, audit false-negatives via string-search-only, manifest gaps (seed data, queues, jobs, buckets, integrations, secrets), lint rule too narrow (dynamic import, re-exports, path aliases), pairwise matrix scoping, and missing §7 tasks. v2 closes them inline below.
**Addresses:** Codex BLOCKs **#1 (tree-shaking asserted not designed), #3 (deployment manifest underspecified), and #5 (cross-composition matrix too weak)** from the main SP-0 spec gate review. Closing this completes the spike.
**Decision:** Build a **generated composition artifact** driven by a richer deployment manifest, enforced by a no-sibling-imports lint rule, verified by a build-time audit, and exercised by a per-PR cross-composition CI matrix.

---

## 1. The three problems being solved

| Codex BLOCK | Problem statement | This spec's answer |
|---|---|---|
| **#1** | "Tree-shaking is asserted not designed." Next.js App Router doesn't naturally tree-shake server route handlers. Any central registry / barrel export / nav map / route manifest that imports all modules will leak (e.g. PaySync code into a ReclaimRx-only build) | Generated composition artifact — codegen writes static imports for selected modules only; no central registry can leak because the artifact only references chosen modules. Plus a lint rule forbidding sibling-module imports. Plus a build-time audit verifying omitted modules produce zero output bytes |
| **#3** | "Deployment manifest scope is dangerously underspecified." `{"modules":["reclaimrx"]}` doesn't derive deployable infra — modules need backends, shared services, schemas, migrations, seed data, env vars, health dependencies | Manifest schema extended to `required_backends`, `required_shared_services`, `required_schemas`, `required_migrations`, `required_env`, `required_health`, per module. CI fails if a manifest omits transitive requirements |
| **#5** | "Cross-composition coverage is too weak." `["all"]`, `["reclaimrx"]`, and one minimal subset won't catch pairwise collisions, shared-state collisions, nav/route conflicts, entitlement conflicts, cache-tag collisions | Generated matrix in CI: all single-module builds, all declared dependency bundles, pairwise combinations for modules sharing shell surfaces, plus artifact-absence checks |

---

## 2. The generated composition artifact

### Inputs

1. **Deployment manifest** — `infrastructure/manifests/<instance>.yml` (richer schema in §3).
2. **Module config registry** — auto-discovered from `packages/modules/*/module.config.ts` files. Each module declares: name, routes, nav entries, required backends, required shared services, required schemas, required migrations, required env vars, required health dependencies.

### Generator

A pre-build script `scripts/generate-composition.ts` runs *before* `next build`:

```ts
// scripts/generate-composition.ts (lives in portal/operator/scripts/)
// Inputs: $INFINITYRX_MANIFEST (path to instance manifest)
// Outputs:
//   packages/shell/src/_generated/module-imports.ts
//   packages/shell/src/_generated/route-mounts.ts
//   packages/shell/src/_generated/nav.ts
//   packages/shell/src/_generated/manifest.json (for runtime introspection)
```

Generated files contain ONLY references to the manifest's listed modules. Example:

```ts
// _generated/module-imports.ts
// AUTO-GENERATED — do not edit. Sources: <manifest>, <module.config.ts files>
import * as reclaimrx from "@infinityrx/module-reclaimrx";
import * as paysync from "@infinityrx/module-paysync";

export const MODULES = { reclaimrx, paysync } as const;
```

A `["reclaimrx"]`-only manifest produces a generated file with ONLY the `reclaimrx` import. The PaySync package is never named, never imported, never bundled.

### Generator's pre-build hook

`portal/operator/next.config.ts` adds a build-time hook that fails the build if `_generated/` is stale relative to manifest mtime or any `module.config.ts` mtime. CI runs the generator explicitly; developers run via `npm run prebuild`.

### What the generator does NOT do

- Does NOT scan source files to "find" modules — only consumes the explicit manifest and module configs.
- Does NOT use barrel exports or central registries that could accidentally pull every module.
- Does NOT rely on tree-shaking to drop unused modules from the bundle — modules not in the manifest are *never imported*.

This addresses codex BLOCK #1: tree-shaking is no longer asserted; selection is mechanical via codegen.

### Repo-wide import-boundary enforcement (closes pass-1 BLOCK on bypass paths)

The codegen mechanism only works if **no other code in the workspace** imports modules outside `_generated/`. Bypass paths to close:

- Static ESM imports from `portal/operator/app/*`, `portal/shared/*`, `packages/shell/src/*` referencing `@infinityrx/module-*` directly
- `require("@infinityrx/module-*")` calls
- Dynamic `import("@infinityrx/module-*")` calls
- Re-exports (`export * from "@infinityrx/module-*"`) — would pull the whole module surface
- TS path aliases that resolve to module package roots (`@/modules/<name>` pattern)
- Relative-path traversal into a sibling module's source (`../../modules/<name>/src/...`)
- Side-effect imports anywhere in the workspace

ESLint rule applied **at the workspace root** (not per-package) with `no-restricted-imports` + `no-restricted-syntax` covering all six bypass paths above. The only allowed reference to `@infinityrx/module-*` is from `packages/shell/src/_generated/*`. CI fails on violation in any workspace package.

---

## 3. Deployment manifest schema (richer)

Replaces the toy `{"modules":[...]}` from main spec §6.10.

### `infrastructure/manifests/<instance>.yml`

```yaml
# Per-customer instance manifest. Source of truth for build + deploy.
instance_name: customer-acme-prod        # human-readable; informs container labels + logs
audience: operator                       # operator | client | provider — determines which portal app builds
auth_profile: production                 # references infrastructure/auth-profiles/<name>.yml
branding:
  primary_color: "#1f2937"
  logo_url: "https://..."
modules:
  - reclaimrx
  - paysync
# Computed from modules + per-module.config.ts (validated by CI):
required_backends:                       # asserted-correct or CI fails
  - reclaimrx
  - paysync
  - core-platform                        # transitive — auth/audit/tenant
  - billing                              # transitive from paysync
required_shared_services:
  - postgres
  - redis
required_schemas:                        # database schemas to bootstrap in this instance's DB
  - reclaimrx_v1
  - paysync_v1
  - core_v1
  - billing_v1
required_migrations:                     # migration sequence to run on first boot
  - core/0001 .. core/latest
  - reclaimrx/0001 .. reclaimrx/latest
  - paysync/0001 .. paysync/latest
  - billing/0001 .. billing/latest
required_env:                            # env vars that MUST be set for this composition; build refuses with missing
  - JWT_SECRET
  - NEXTAUTH_SECRET
  - INFINITYRX_ENV
  - DATABASE_URL_CORE
  - DATABASE_URL_RECLAIMRX
  - DATABASE_URL_PAYSYNC
  - DATABASE_URL_BILLING
  - REDIS_URL
required_health:                         # health endpoints the composition must verify on boot
  - http://core-platform:8000/health
  - http://reclaimrx:8020/health
  - http://paysync:8021/health
  - http://billing:8022/health
required_seed_data:                      # seed data sets that MUST be loaded before the instance can serve traffic
  - reference/ndc                        # universal — drug master
  - reference/nppes                      # universal — prescriber master
  - reference/ncpdp-pharmacies           # universal — pharmacy master
  - reclaimrx/fwa-rules                  # module-scoped — rule library
  - paysync/fee-schedules                # module-scoped — payer fee schedules
required_queues:                         # event-bus queues (RabbitMQ local / Service Bus prod) the composition needs declared
  - paysync.claim.ingested
  - paysync.invoice.generated
  - reclaimrx.investigation.opened
  - billing.payment.settled
required_jobs:                           # scheduled jobs (APScheduler / Service Bus timers) required for steady-state operation
  - core.audit_chain_verify            # daily — HIPAA-2026 audit integrity
  - core.session_reaper                 # 5-min — expired sessions
  - reclaimrx.graph_anomaly_scan        # nightly
  - paysync.payment_run                 # tenant-configured cron
required_buckets:                        # object storage (Azure Blob / S3) containers required by modules in this composition
  - reports
  - reclaimrx-investigation-evidence
  - paysync-remittance-files
  - core-export-staging
required_integrations:                   # external network endpoints the composition must reach on boot; CI verifies egress allow-list
  - switch.relayhealth                   # NCPDP D.0 switch (paysync, claims)
  - azure.openai                         # ai-nlp (if module present)
  - clearinghouse.officeally             # medical-claims (if module present)
required_secrets:                        # secret REFERENCES (not values) that must resolve in the target instance's secret manager
  - secret://jwt/signing-key
  - secret://nextauth/secret
  - secret://db/core
  - secret://db/reclaimrx
  - secret://db/paysync
  - secret://db/billing
  - secret://switch/relayhealth-mtls-cert
migration_policy:                        # ordering + rollback discipline
  ordering: explicit                     # core first, then modules in declared dependency order
  rollback: none                         # forward-only; rollback = re-deploy prior image and restore from PITR snapshot
  pre_check: dry_run_required            # CI runs migrations against a snapshot of the instance's DB before merge
```

### Per-module `module.config.ts` is the source of truth for transitive requirements

```ts
// packages/modules/reclaimrx/module.config.ts
export const config = {
  name: "reclaimrx",
  routes: ["/reclaimrx", "/reclaimrx/investigations/:id", "/reclaimrx/leakage", ...],
  navEntry: { label: "ReclaimRx", icon: "shield", order: 4 },
  requires: {
    backends: ["reclaimrx", "core-platform"],         // core-platform is universal (auth/audit/tenant)
    sharedServices: ["postgres", "redis"],
    schemas: ["reclaimrx_v1", "core_v1"],
    migrations: ["core", "reclaimrx"],
    env: ["DATABASE_URL_RECLAIMRX"],                  // module-specific env on top of universal
    health: ["http://reclaimrx:8020/health"],
    seedData: ["reclaimrx/fwa-rules"],                // data sets that MUST be present before module serves traffic
    queues: ["reclaimrx.investigation.opened"],       // event-bus queues this module publishes to / consumes from
    jobs: ["reclaimrx.graph_anomaly_scan"],           // scheduled jobs the composition must run for this module
    buckets: ["reclaimrx-investigation-evidence"],    // object-storage containers
    integrations: [],                                 // external endpoints (e.g., "switch.relayhealth")
    secrets: ["secret://db/reclaimrx"],               // secret references this module needs resolved
  },
  shellSurfaces: {                                    // declares what shell surfaces this module occupies — drives pairwise CI matrix
    navOrderSlots: [4],
    cacheTagPrefixes: ["reclaimrx:"],
    commandPaletteScopes: ["reclaimrx.*"],
    routePrefixes: ["/reclaimrx"],
  },
  entitlements: {                                     // future: runtime entitlements when sub-tenant features land
    requiredScope: null,
  },
} as const;
```

### CI manifest validator

`scripts/validate-manifest.ts`:
1. **JSON Schema gate** — the manifest itself must validate against `schemas/instance-manifest.schema.json` (Ajv strict mode, `additionalProperties: false`). Unknown fields, missing required fields, wrong types all fail before any closure computation.
2. Loads the manifest's `modules` list.
3. For each module, reads its `module.config.ts` (must exist in `packages/modules/<name>/`).
4. Computes the **transitive closure** of every key under `requires.*` — `backends`, `sharedServices`, `schemas`, `migrations`, `env`, `health`, `seedData`, `queues`, `jobs`, `buckets`, `integrations`, `secrets`.
5. Compares against the manifest's explicit `required_*` fields. **Any mismatch (missing or extra) fails the build.**
6. Verifies `migration_policy.ordering == "explicit"` resolves a topologically valid sequence given the dependency graph.
7. Verifies every `secret://...` reference in `required_secrets` resolves at the configured secret manager URL (dry-run check, not value disclosure).
8. Verifies every `required_integrations` entry is in the platform's `infrastructure/integrations.yml` allow-list.
9. Verifies every `required_queues` and `required_jobs` entry is declared in exactly one module's `module.config.ts` (no orphans, no duplicates).
10. Verifies every `required_buckets` entry has a Terraform definition in `infrastructure/storage.tf`.
11. Also fails if a referenced module has no `module.config.ts`, or if a `module.config.ts` declares a backend not in the project's backend list.

### Manifest JSON Schema (committed under `schemas/instance-manifest.schema.json`)

Strict-mode schema published alongside this spec. Required keys: `instance_name`, `audience`, `auth_profile`, `modules`, `required_backends`, `required_shared_services`, `required_schemas`, `required_migrations`, `required_env`, `required_health`, `required_seed_data`, `required_queues`, `required_jobs`, `required_buckets`, `required_integrations`, `required_secrets`, `migration_policy`. `additionalProperties: false` at every level. `audience` is an enum (`operator | client | provider`). All `required_*` arrays have `minItems: 0` and `uniqueItems: true`.

This addresses codex BLOCK #3: manifests cannot silently produce a broken deployment because the validator enforces transitive closure across the *full* set of requirement types and a strict schema gate prevents drift.

---

## 4. The no-sibling-imports lint rule

A module package may import:
- `@infinityrx/portal-contract`
- `@infinityrx/portal-auth`
- `@infinityrx/portal-ui`
- `@infinityrx/portal-qa-harness`
- `@infinityrx/portal-shell` (for adapter types)
- Its own package contents (relative imports inside `packages/modules/<name>/`)

A module package may **NOT** import:
- `@infinityrx/module-*` (any sibling module). Direct enforcement of "modules are independent."
- `next/*`, `next-auth/*`, `@auth/*` (framework specifics — see sub-decision 2's adapter contract).

### ESLint rule (workspace root)

A single workspace-root `eslint.config.js` block enforces both the static-import patterns AND the bypass paths called out in §2:

```js
import { defineConfig } from "eslint/config";

export default defineConfig({
  // Applies to ALL workspace packages — modules, packages/*, portal/*, scripts/*.
  files: ["**/*.{ts,tsx,js,jsx}"],
  ignores: ["packages/shell/src/_generated/**"],     // only allowed referrer of @infinityrx/module-*
  rules: {
    "no-restricted-imports": ["error", {
      patterns: [
        // Bypass path 1: static ESM import (also covers `import type` via verbatimModuleSyntax)
        { group: ["@infinityrx/module-*"], message: "Modules are referenced ONLY from packages/shell/src/_generated/. Direct imports break composition isolation." },
        // Framework-agnostic enforcement for module + shared packages
        { group: ["next/*", "next-auth/*", "@auth/*"], message: "Framework-specific imports are forbidden outside portal/operator/app/. Move usage into a thin adapter." },
      ],
    }],
    // Bypass path 2: re-exports (export * from "@infinityrx/module-*") — would smuggle the whole surface
    // Bypass path 3: dynamic import("@infinityrx/module-*")
    // Bypass path 4: require("@infinityrx/module-*")
    // Bypass path 5: relative-path traversal into a sibling module's source
    // Bypass path 6: TS path aliases that resolve to a module package root
    "no-restricted-syntax": ["error",
      {
        selector: "ExportAllDeclaration[source.value=/^@infinityrx\\/module-/]",
        message: "Re-exporting from @infinityrx/module-* defeats composition isolation.",
      },
      {
        selector: "ExportNamedDeclaration[source.value=/^@infinityrx\\/module-/]",
        message: "Named re-exports from @infinityrx/module-* defeat composition isolation.",
      },
      {
        selector: "ImportExpression[source.value=/^@infinityrx\\/module-/]",
        message: "Dynamic import() of @infinityrx/module-* defeats composition isolation.",
      },
      {
        selector: "CallExpression[callee.name='require'][arguments.0.value=/^@infinityrx\\/module-/]",
        message: "require() of @infinityrx/module-* defeats composition isolation.",
      },
      {
        // Relative-path traversal: importing from `../../modules/<name>/...` or `../../../packages/modules/<name>/...`
        selector: "ImportDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Relative-path traversal into a sibling module is forbidden. Use packages/contract for shared types.",
      },
      {
        // Path-alias bypass: `@/modules/<name>` or `@modules/<name>` (configured in tsconfig)
        selector: "ImportDeclaration[source.value=/^@\\/?modules\\//]",
        message: "TS path-alias references to modules are forbidden. Use packages/contract for shared types.",
      },
      {
        // Side-effect imports: `import "@infinityrx/module-foo";`
        selector: "ImportDeclaration[specifiers.length=0][source.value=/^@infinityrx\\/module-/]",
        message: "Side-effect imports of @infinityrx/module-* defeat composition isolation.",
      },
    ],
    // Force `import type` discrimination so the audit can distinguish type-only references from runtime ones
    "@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports", fixStyle: "separate-type-imports" }],
  },
});
```

Plus `tsconfig.base.json` sets `verbatimModuleSyntax: true` so type-only imports are stripped from emit (preventing a runtime bundle leak via a misclassified type import).

Plus `tsconfig.base.json` strips problem path aliases — there is no `@modules/*` alias defined; any attempt to add one fails a separate config-lint check (`scripts/lint-tsconfig.ts`).

Same shape (without `@infinityrx/module-*`) applies to `packages/contract`, `packages/auth`, `packages/ui`, `packages/qa-harness` — they MUST also be framework-agnostic per sub-decision 2's mandate.

---

## 5. Build-time composition audit

After `next build`, a verification step asserts:

### 5.1 Module-graph audit (primary mechanism, not string-search)

`next build` is invoked with `--experimental-build-trace` (or equivalent flag for the installed Next.js version) which writes per-route trace files at `.next/server/app/**/page.js.nft.json` and a project-wide trace at `.next/trace`. These declare *every file in every server route's module graph*. The audit:

1. Loads every `.nft.json` and the `.next/trace` file — these are the authoritative module-graph manifests Next.js itself uses for serverless deploy slicing.
2. Resolves every traced file against the workspace package map (built once from `pnpm-lock.yaml` + `node_modules/.pnpm/`).
3. Computes the set of **packages actually traced into the build** (transitive closure of imports from any compiled route + middleware + instrumentation file).
4. Asserts: `packages_in_build ∩ omitted_modules == ∅`. If any omitted module's package shows up in *any* route's `.nft.json`, the audit fails with the exact route file that pulled it.
5. Asserts: `packages_in_build ⊇ manifest_modules`. If a required module is missing from every route's trace, the audit fails.

This is a module-graph fact, not a string heuristic. It survives minification, code-splitting, dynamic import resolution, and tree-shaking decisions made by SWC/webpack/Turbopack.

### 5.2 Bundle-graph supplement (catches client-bundle leakage)

For the client-side bundle, the audit reads `.next/build-manifest.json` + `.next/app-build-manifest.json` + the per-page chunk manifests, plus the SWC/webpack stats JSON (`next build --profile` writes `.next/analyze/*.json`). The audit:

1. Resolves every chunk back to source modules via stats `modules[].name`.
2. Asserts no chunk's modules include any omitted module's package.

### 5.3 String-search backstop (cheap defense in depth)

After 5.1 and 5.2 pass, a final cheap pass greps `.next/server/`, `.next/static/`, `.next/build-manifest.json`, `.next/routes-manifest.json`, and `.next/required-server-files.json` for omitted-module package names and known route prefixes. This catches the long-tail case where a module's code reaches the build via a path the module graph didn't capture (e.g., a string-interpolated dynamic require evaluated at runtime). String-search-only would be insufficient (false negatives from minification, identifier mangling), but as a backstop *after* the graph audit it's a free extra check.

### 5.4 Generated-file integrity

`_generated/module-imports.ts` / `route-mounts.ts` / `nav.ts` / `manifest.json` must:

1. Exist.
2. Be byte-identical to a freshly re-run of `scripts/generate-composition.ts` against the same inputs (determinism check).
3. Reference exactly the manifest's modules — no more, no less.
4. Have an mtime newer than the manifest and every referenced `module.config.ts` (staleness check).

### 5.5 Wiring

`scripts/audit-composition.ts` runs as the `postbuild` script in `portal/operator/package.json`. CI fails if any check fails. The audit is the second mechanical enforcement of codex BLOCK #1 — graph-level evidence, not string-level inference.

---

## 6. Cross-composition CI matrix

CI runs `next build` + audit for these compositions on every PR:

| Composition | Why |
|---|---|
| `["all"]` — operator full | Reference build; baseline for regression |
| `[]` — empty (just shell) | Catches accidental shell-level imports of modules |
| Each single module: `["reclaimrx"]`, `["paysync"]`, `["claims"]`, `["billing"]`, `["directories"]`, etc. | Catches modules that don't actually build standalone |
| Every declared dependency bundle | E.g., `["paysync", "billing"]` if PaySync's `module.config.ts` declares billing in `requires` |
| **Scoped pairwise** for modules that share shell surfaces | Catches nav-route conflicts, cache-tag collisions, shared-state collisions |
| Minimal: `["directories"]` (smallest realistic standalone product) | Ergonomic smoke test |

### 6.1 Pairwise scoping (closes pass-1 CONCERN on N*(N-1)/2 blow-up)

Pairwise is NOT all-pairs. The matrix generator computes pairs from `module.config.ts.shellSurfaces`:

```
pairs = { (A, B) : A != B AND shellSurfaces(A) ∩ shellSurfaces(B) ≠ ∅ }
```

Where the intersection considers `navOrderSlots`, `cacheTagPrefixes`, `commandPaletteScopes`, `routePrefixes`. Two modules that touch zero shared surfaces (e.g., reclaimrx + ai-nlp have disjoint nav slots, distinct cache prefixes, distinct route prefixes) do not need a pairwise build — there is no collision surface to test.

In practice, with 13 modules this collapses 78 unconstrained pairs to roughly 15-25 surface-sharing pairs. The exact set is computed and printed at PR time so the count is auditable.

### 6.2 Generator wiring

The matrix is generated from `packages/modules/*/module.config.ts` files — `scripts/generate-ci-matrix.ts` writes `.github/workflows/composition-matrix.yml` from the module registry. New module → new matrix entries automatically. The generated matrix file is checked in; CI fails if `_generated/composition-matrix.yml` is stale vs. any `module.config.ts` mtime (same staleness pattern as §2).

### 6.3 Execution policy

Run on PRs that touch `packages/modules/*`, `packages/shell/*`, `infrastructure/manifests/*`, or `schemas/instance-manifest.schema.json`. Cache by content-hash of the manifest + module configs otherwise. Nightly: full run on `main` regardless of PR touch.

This addresses codex BLOCK #5: matrix coverage is mechanically generated, scoped to collision surfaces (so it stays tractable), and catches the combinatorial cases the original `["all"]` + `["reclaimrx"]` + one-minimal set would miss.

---

## 7. What this pins for the SP-0 plan

| Pinned | Implication |
|---|---|
| `scripts/generate-composition.ts` runs pre-build | New script in SP-0 scope; `_generated/` directory in `packages/shell/src/`; deterministic output (byte-identical re-runs) |
| `scripts/validate-manifest.ts` runs in CI | Enforces transitive closure across backends, services, schemas, migrations, env, health, seed data, queues, jobs, buckets, integrations, secrets |
| `scripts/audit-composition.ts` runs post-build | Module-graph audit (.nft.json + .next/trace) + bundle-graph audit (stats JSON) + string-search backstop + generated-file determinism+staleness checks |
| `scripts/generate-ci-matrix.ts` runs on module-config changes | Writes the GitHub Actions matrix file; scoped pairwise from `shellSurfaces` overlap, not all-pairs |
| `scripts/lint-tsconfig.ts` runs in CI | Rejects `@modules/*` path aliases (or any alias that resolves to a module package root) |
| Workspace-root `eslint.config.js` enforces import-boundary on six bypass paths | Static ESM, re-exports, dynamic import(), require(), relative traversal, path aliases, side-effect imports — all forbidden outside `_generated/` |
| `module.config.ts` is the per-module source of truth | Includes `requires.{backends,sharedServices,schemas,migrations,env,health,seedData,queues,jobs,buckets,integrations,secrets}` and `shellSurfaces.{navOrderSlots,cacheTagPrefixes,commandPaletteScopes,routePrefixes}` |
| `module.config.ts` purity gate | Compile-step check that each `module.config.ts` has zero imports from sibling modules, no `next/*` imports, no I/O. CI fails on violation |
| Manifest schema is YAML at `infrastructure/manifests/<instance>.yml` | New directory in SP-0 scope; existing `.env.*` pattern stays for instance-specific secret *values*; manifest holds secret *references* only |
| `schemas/instance-manifest.schema.json` published | Strict-mode JSON Schema (Ajv `additionalProperties: false`); validator runs before transitive-closure check |
| Generated artifact determinism | `scripts/generate-composition.ts` is hermetic — same inputs produce byte-identical output; CI re-runs the generator and diffs against checked-in `_generated/` |
| Generated artifact staleness | Pre-build hook fails build if `_generated/` mtime is older than manifest or any `module.config.ts` mtime; same check is repeated in CI |
| `scripts/validate-secret-references.ts` runs in CI | Confirms every `secret://...` in the manifest resolves at the configured secret manager (existence, not value disclosure); also runs at instance boot |
| Module-config orphan check | CI fails if a `module.config.ts` declares a queue/job/bucket/integration not present in the workspace's declared catalog, or if a catalog entry has no declaring module |

## 8. Closing original spec gate BLOCKs

With this artifact committed, the SP-0 decision spike has closed all five BLOCKs codex flagged in the main spec gate review:

| BLOCK | Closed by |
|---|---|
| #1 (tree-shaking) | This artifact §2 + §5 |
| #2 (framework + gateway) | Sub-decisions 2 (`14d847a`) + 3 (`daffdb0`) |
| #3 (manifest underspec) | This artifact §3 |
| #4 (auth contract) | Sub-decision 1 (`b876c3b`) |
| #5 (cross-composition matrix) | This artifact §6 |

The spike's outcome feeds into task #13 (spec revision) which folds these decisions into the main SP-0 spec, then task #7 (writing-plans) creates the implementation plan.

## 9. Cross-references

- Codex pass-1 BLOCKs #1, #3, #5 in `2026-05-14-sp0-integration-foundation-design.md`
- Sub-decision 1: `2026-05-15-sp0-decision-spike-auth-interface.md` (`b876c3b`)
- Sub-decision 2: `2026-05-15-sp0-decision-spike-framework.md` (`14d847a`)
- Sub-decision 3: `2026-05-15-sp0-decision-spike-gateway.md` (`daffdb0`)
- Main spec §5.3 (per-customer composition model)
- Main spec §6.10 (deployment manifest — to be replaced by this artifact's §3)
- Main spec §9.5 (CI composition matrix — to be replaced by this artifact's §6)
