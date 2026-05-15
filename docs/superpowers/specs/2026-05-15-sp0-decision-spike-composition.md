# SP-0 Decision Spike — Composition Mechanism

**Status:** v4 drafted 2026-05-15. v3 was committed `a3bb508`; codex pass-3 verified 5/7 findings CLOSED, 2 PARTIALLY-CLOSED (sibling-relative module-to-module traversal without a `modules/` segment in the path was still bypassable), plus 1 new BLOCK (the `// input_hash` header is invalid YAML for `yq`) and 1 NIT (stale opening-summary phrase about CI symlinking the matrix). v4 closes them:
- Sibling-relative imports inside `packages/modules/**` are now barred by `eslint-plugin-import`'s `no-restricted-paths` rule, declaring each module package as a zone forbidden from importing other module packages. Catches `../../other-module/src/...` traversal that has no `modules/` segment in the resolved string.
- Generated-file header syntax is now per-file-type: `// input_hash:` for TS/JS, `# input_hash:` for YAML, and a top-level `_input_hash` JSON key for `manifest.json`. `composition-matrix.yml` is valid YAML for `yq` consumption.
- Composition-matrix path: single canonical generated location `packages/shell/src/_generated/composition-matrix.yml`. The static workflow `.github/workflows/composition-matrix.yml` reads it at runtime via `fromJSON(yq)`. No symlink. The stale "CI symlinks" phrase has been deleted from this section in v4.

v3 closes (carried into v4 — no further changes needed): pairwise collision surfaces broadened beyond shellSurfaces; secret validation split into PR-CI offline + deploy/boot environment-bound; content-hash replacing mtime; server-graph vs client-bundle audit split.
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

`portal/operator/next.config.ts` adds a build-time hook that recomputes the `input_hash` from the current manifest + `module.config.ts` files and fails the build if it does not match the `input_hash` header embedded in `_generated/` artifacts (content-addressed staleness — see §5.3 for rationale). CI runs the generator explicitly; developers run via `npm run prebuild`. No mtime comparison anywhere in the pipeline.

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
    cacheKeyNamespaces: ["reclaimrx:"],               // additional pairwise collision input (see §6.1)
    redisKeyPrefixes: ["tenant:*:reclaimrx:"],
    rabbitExchanges: ["reclaimrx.events"],
  },
  surfaceKinds: ["server", "client"],                 // §5.1: drives server-trace vs client-bundle audit expectations
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
7. **Secret-reference validation (PR-CI, OFFLINE only)** — for every `secret://...` reference in `required_secrets`:
   a. URI shape passes the secret-reference grammar (`secret://<scope>/<name>` with `<scope>` ∈ enum, `<name>` matches `[a-z0-9-]+`).
   b. The scope is declared in `infrastructure/secret-catalog.yml` (committed; lists which scopes the platform owns).
   c. The (scope, name) pair is owned by at most one module's `module.config.ts` (no duplicates).
   PR-CI does NOT call the live secret manager. Live-existence is asserted at deploy / boot only (see §3.X below). This prevents PR builds from requiring production secret-manager access.

### Environment-bound secret existence check (§3.X)

`scripts/verify-instance-secrets.ts` runs in TWO non-PR contexts:
- At **deploy time** in the target environment's deploy pipeline (post-build, pre-rollout) — calls the configured secret manager for the target instance (dev / mock / prod) and asserts every `required_secrets` entry resolves to a non-empty value. Failure halts the rollout.
- At **boot time** as a pre-start hook in the container's entrypoint — same checks, refuses to start the process if any required secret is missing or empty.

Neither check is wired to PR CI. PR CI sees only the offline checks above.
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
    // Bypass paths — each must be covered for THREE specifier shapes:
    //   1. Package name      : "@infinityrx/module-<name>"
    //   2. Relative traversal: "(../)+modules/<name>/..." or "(../)+packages/modules/<name>/..."
    //   3. TS path alias     : "@/modules/<name>" or "@modules/<name>"
    // Across SEVEN node types: static ESM ImportDeclaration (incl. side-effect), ExportAllDeclaration,
    // ExportNamedDeclaration (with source), ImportExpression (dynamic import), and require() CallExpression.
    // The `no-restricted-imports` rule above covers static ESM Import/Export for shape (1).
    // The selectors below cover (1) dynamic forms + (2) and (3) for ALL forms.
    "no-restricted-syntax": ["error",
      // ── Shape 1: @infinityrx/module-* package specifier (residual dynamic forms) ──
      { selector: "ExportAllDeclaration[source.value=/^@infinityrx\\/module-/]",
        message: "Re-exporting from @infinityrx/module-* defeats composition isolation." },
      { selector: "ExportNamedDeclaration[source.value=/^@infinityrx\\/module-/]",
        message: "Named re-exports from @infinityrx/module-* defeat composition isolation." },
      { selector: "ImportExpression[source.value=/^@infinityrx\\/module-/]",
        message: "Dynamic import() of @infinityrx/module-* defeats composition isolation." },
      { selector: "CallExpression[callee.name='require'][arguments.0.value=/^@infinityrx\\/module-/]",
        message: "require() of @infinityrx/module-* defeats composition isolation." },
      { selector: "ImportDeclaration[specifiers.length=0][source.value=/^@infinityrx\\/module-/]",
        message: "Side-effect imports of @infinityrx/module-* defeat composition isolation." },

      // ── Shape 2: relative-path traversal `(../)+modules/<name>` or `(../)+packages/modules/<name>` ──
      { selector: "ImportDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Relative-path traversal into a sibling module is forbidden. Use packages/contract." },
      { selector: "ExportAllDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Relative re-export from a sibling module is forbidden." },
      { selector: "ExportNamedDeclaration[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Relative named re-export from a sibling module is forbidden." },
      { selector: "ImportExpression[source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Dynamic import() via relative traversal into a sibling module is forbidden." },
      { selector: "CallExpression[callee.name='require'][arguments.0.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "require() via relative traversal into a sibling module is forbidden." },
      { selector: "ImportDeclaration[specifiers.length=0][source.value=/(\\.\\.\\/)+(packages\\/)?modules\\//]",
        message: "Side-effect import via relative traversal into a sibling module is forbidden." },

      // ── Shape 3: TS path-alias forms `@/modules/<name>` or `@modules/<name>` ──
      { selector: "ImportDeclaration[source.value=/^@\\/?modules\\//]",
        message: "TS path-alias references to modules are forbidden. Use packages/contract." },
      { selector: "ExportAllDeclaration[source.value=/^@\\/?modules\\//]",
        message: "TS path-alias re-export from a module is forbidden." },
      { selector: "ExportNamedDeclaration[source.value=/^@\\/?modules\\//]",
        message: "TS path-alias named re-export from a module is forbidden." },
      { selector: "ImportExpression[source.value=/^@\\/?modules\\//]",
        message: "TS path-alias dynamic import() of a module is forbidden." },
      { selector: "CallExpression[callee.name='require'][arguments.0.value=/^@\\/?modules\\//]",
        message: "TS path-alias require() of a module is forbidden." },
      { selector: "ImportDeclaration[specifiers.length=0][source.value=/^@\\/?modules\\//]",
        message: "TS path-alias side-effect import of a module is forbidden." },

      // Belt-and-suspenders: a separate scripts/lint-tsconfig.ts step (see §7) refuses to even register a path
      // alias whose target resolves into `packages/modules/`, so Shape 3 cannot become valid at the compiler level.
    ],
    // Force `import type` discrimination so the audit can distinguish type-only references from runtime ones
    "@typescript-eslint/consistent-type-imports": ["error", { prefer: "type-imports", fixStyle: "separate-type-imports" }],

    // Closes pass-3 residual on BLOCK-1: sibling-relative imports inside packages/modules/**
    // that don't contain the literal `modules/` segment in the resolved path
    // (e.g., a file under packages/modules/paysync/src/foo.ts writing
    //  `import x from "../../reclaimrx/src/bar"` — resolves to packages/modules/reclaimrx/...
    //  but the string form `../../reclaimrx/...` doesn't match the (../)+modules/ regex).
    // `eslint-plugin-import`'s no-restricted-paths is path-resolution-aware (not pattern-based),
    // so it sees the resolved target and enforces zone boundaries.
    "import/no-restricted-paths": ["error", {
      zones: [
        // Each module is a zone forbidden from importing any sibling module by ANY path shape.
        // The `target` glob is every module's source, and the `from` glob is every OTHER module's source.
        // ESLint expands this dynamically via the `from: ["packages/modules/!(<self>)/**"]` pattern
        // when the rule is set up by `scripts/generate-eslint-zones.ts` (run as part of lint setup).
        {
          target: "packages/modules/*/src/**/*",
          from: "packages/modules/*/src/**/*",
          except: ["packages/modules/*/src/index.ts"],  // a module's own index re-exports stay legal within itself
          message: "Modules must not import sibling modules by ANY path shape (package, alias, or relative traversal). Use packages/contract for shared types."
        },
        // Module source may not reach into another module's package root (e.g., dist/ or non-src/ files)
        {
          target: "packages/modules/*/**/*",
          from: "packages/modules/*/**/*",
          except: ["packages/modules/*/src/**", "packages/modules/*/module.config.ts", "packages/modules/*/package.json"],
          message: "Cross-module file references are forbidden. Use the public package surface."
        },
      ],
    }],
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

`next build` is invoked with `--experimental-build-trace` (or equivalent flag for the installed Next.js version) which writes per-route trace files at `.next/server/app/**/page.js.nft.json` and a project-wide trace at `.next/trace`. The audit separates **server-graph evidence** from **client-bundle evidence** because modules can ship surfaces of either kind (or both):

Every module's `module.config.ts` MUST declare `surfaceKinds: ["server", "client"] | ["server"] | ["client"]` so the audit knows which evidence to expect. Default if unspecified is `["server", "client"]`.

#### Server-graph audit (for modules with `"server"` in surfaceKinds)

1. Loads every `.nft.json` and the `.next/trace` file — these are the authoritative module-graph manifests Next.js itself uses for serverless deploy slicing.
2. Resolves every traced file against the workspace package map (built once from `pnpm-lock.yaml` + `node_modules/.pnpm/`).
3. Computes the set of **server-traced packages** (transitive closure of imports from any compiled route + middleware + instrumentation file).
4. Asserts: `server_traced_packages ∩ omitted_modules == ∅`. If any omitted module's package shows up in *any* route's `.nft.json`, the audit fails with the exact route file that pulled it.
5. Asserts: for every manifest module M with `"server"` in `surfaceKinds`, M ∈ `server_traced_packages`. If a required server-bearing module is missing from every route's trace, the audit fails.

#### Client-bundle audit (for modules with `"client"` in surfaceKinds)

1. Reads `.next/build-manifest.json` + `.next/app-build-manifest.json` + per-page chunk manifests + SWC/webpack stats (`.next/analyze/*.json`).
2. Resolves every chunk back to source packages via stats `modules[].name`.
3. Computes `client_bundled_packages`.
4. Asserts: `client_bundled_packages ∩ omitted_modules == ∅`.
5. Asserts: for every manifest module M with `"client"` in `surfaceKinds`, M ∈ `client_bundled_packages`.

#### Both-graph absence (universal)

Regardless of `surfaceKinds`, every omitted module must be absent from BOTH the server trace AND the client bundle. Presence in either is a failure.

This is module-graph evidence, not a string heuristic. It survives minification, code-splitting, dynamic import resolution, and tree-shaking decisions made by SWC/webpack/Turbopack. The client-only / server-only split prevents false failures for modules that legitimately don't appear in one of the two evidence sources.

### 5.2 String-search backstop (cheap defense in depth)

After §5.1 passes, a final cheap pass greps `.next/server/`, `.next/static/`, `.next/build-manifest.json`, `.next/routes-manifest.json`, and `.next/required-server-files.json` for omitted-module package names and known route prefixes. This catches the long-tail case where a module's code reaches the build via a path the module graph didn't capture (e.g., a string-interpolated dynamic require evaluated at runtime). String-search-only would be insufficient (false negatives from minification, identifier mangling), but as a backstop *after* the graph audit it's a free extra check.

### 5.3 Generated-file integrity (content-hash, not mtime)

`_generated/module-imports.ts` / `route-mounts.ts` / `nav.ts` / `manifest.json` / `composition-matrix.yml` must:

1. **Exist.**
2. **Be byte-identical** to a freshly re-run of `scripts/generate-composition.ts` against the same inputs (determinism check — CI re-runs the generator into a scratch directory and diffs byte-for-byte against the checked-in artifact).
3. **Reference exactly the manifest's modules** — no more, no less.
4. **Carry a deterministic `input_hash` marker** at the top of every generated file, using the comment syntax valid for that file type:

   **TypeScript / JavaScript (`.ts`, `.js`):**
   ```ts
   // AUTO-GENERATED — do not edit.
   // input_hash: sha256:<hex>
   // inputs: <manifest-path>@<sha256>, <module.config.ts paths>@<sha256-each>
   ```

   **YAML (`.yml`, `.yaml`):**
   ```yaml
   # AUTO-GENERATED — do not edit.
   # input_hash: sha256:<hex>
   # inputs: <manifest-path>@<sha256>, <module.config.ts paths>@<sha256-each>
   matrix:
     - ...
   ```

   **JSON (`.json` — comments not legal):** embed as top-level keys:
   ```json
   {
     "_generated": true,
     "_input_hash": "sha256:<hex>",
     "_inputs": { "<manifest-path>": "<sha256>", "...": "..." },
     "modules": ["reclaimrx", "paysync"]
   }
   ```
   The validator strips `_`-prefixed keys before comparing the rest of `manifest.json` against the manifest's `modules` list.

   The hash is computed by `scripts/generate-composition.ts` over the sorted, normalized content of the manifest plus every `module.config.ts` it consumed, using a stable serializer (JSON-canonical for objects, LF line endings). CI recomputes the hash from current inputs and fails if the embedded hash does not match — this is the staleness check, with no dependency on mtime, git timestamps, CI cache restore, artifact upload/download timing, or clock skew.

   The YAML `composition-matrix.yml` is therefore valid YAML and consumable by `yq -o=json '.matrix' …` (as referenced in §6.2). The TS files are valid TypeScript. The JSON file is parseable JSON.

mtime is NOT used for staleness anywhere in the pipeline. The pre-build hook in `portal/operator/next.config.ts` (introduced in §2) is rewritten to recompute the hash and refuse the build if it differs — same content-addressed mechanism, same failure mode regardless of which environment the build runs in.

### 5.4 Wiring

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

### 6.1 Pairwise scoping (closes pass-1 CONCERN-2 + pass-2 residual on collision-class coverage)

Pairwise is NOT all-pairs, but the scoping inputs span more than `shellSurfaces`. The matrix generator computes pairs as the **union** of overlap predicates:

```
collisionSurfaces(M) = shellSurfaces(M)
                    ∪ requires.backends(M)
                    ∪ requires.schemas(M)
                    ∪ requires.queues(M)
                    ∪ requires.jobs(M)
                    ∪ requires.buckets(M)
                    ∪ requires.integrations(M)
                    ∪ requires.env(M)
                    ∪ cacheKeyNamespaces(M)         # declared in module.config.ts
                    ∪ redisKeyPrefixes(M)           # declared in module.config.ts
                    ∪ rabbitExchanges(M)            # declared in module.config.ts

pairs = { (A, B) : A != B AND collisionSurfaces(A) ∩ collisionSurfaces(B) ≠ ∅ }
```

Two modules need a pairwise build if and only if they share at least one of:
- A shell surface (nav slot, route prefix, command-palette scope, cache-tag prefix).
- A backend service (e.g., both call `core-platform`).
- A database schema (e.g., both write to `core_v1`).
- A queue, scheduled job, object-storage bucket, or external integration endpoint.
- An env var (would mean ambiguous configuration).
- A cache-key namespace, Redis key prefix, or RabbitMQ exchange.

This catches the collision classes pass-2 flagged: shared-backend interaction effects, schema migration ordering between modules, queue/job contention, bucket-name clashes, integration egress allow-list interactions, env-var conflicts, cache poisoning across modules.

In practice, with 13 modules this collapses 78 unconstrained pairs to roughly 30-45 collision-bearing pairs (more than the shellSurfaces-only count, but still far below 78). The exact set is computed and printed at PR time so the count is auditable; CI logs both the pair count and the surface-overlap reason for each pair.

The `core-platform` module is excluded from pair generation because it is universal (every composition includes it) — pairs involving it would just be `(M, core-platform)` for all M, which is already exercised by the single-module matrix entries.

### 6.2 Generator wiring

The matrix is generated from `packages/modules/*/module.config.ts` files — `scripts/generate-ci-matrix.ts` writes **a single canonical output**: `packages/shell/src/_generated/composition-matrix.yml` (checked in, content-hash header per §5.3).

GitHub Actions consumes that file via a workflow that reads it as a job input — there is no separate `.github/workflows/composition-matrix.yml` artifact (avoiding the dual-path inconsistency flagged by codex pass-2). The composition-matrix workflow at `.github/workflows/composition-matrix.yml` is a **static, checked-in workflow file** that loads its matrix dynamically from the `_generated/composition-matrix.yml`:

```yaml
# .github/workflows/composition-matrix.yml (static; do NOT regenerate)
name: composition-matrix
on: [pull_request, push]
jobs:
  compositions:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        composition: ${{ fromJSON(needs.load.outputs.matrix) }}
    needs: load
  load:
    runs-on: ubuntu-latest
    outputs:
      matrix: ${{ steps.read.outputs.matrix }}
    steps:
      - uses: actions/checkout@v4
      - id: read
        run: echo "matrix=$(yq -o=json '.matrix' packages/shell/src/_generated/composition-matrix.yml)" >> $GITHUB_OUTPUT
```

New module → `scripts/generate-ci-matrix.ts` emits new entries into `_generated/composition-matrix.yml`. The static workflow picks them up at the next run. CI fails if the generated file's `input_hash` does not match a fresh recomputation against current `module.config.ts` content (content-addressed staleness, identical to §5.3).

### 6.3 Execution policy

Run on PRs that touch `packages/modules/*`, `packages/shell/*`, `infrastructure/manifests/*`, or `schemas/instance-manifest.schema.json`. Cache by content-hash of the manifest + module configs otherwise. Nightly: full run on `main` regardless of PR touch.

This addresses codex BLOCK #5: matrix coverage is mechanically generated, scoped to collision surfaces (so it stays tractable), and catches the combinatorial cases the original `["all"]` + `["reclaimrx"]` + one-minimal set would miss.

---

## 7. What this pins for the SP-0 plan

| Pinned | Implication |
|---|---|
| `scripts/generate-composition.ts` runs pre-build | New script in SP-0 scope; `_generated/` directory in `packages/shell/src/`; deterministic output (byte-identical re-runs) |
| `scripts/validate-manifest.ts` runs in CI | Enforces transitive closure across backends, services, schemas, migrations, env, health, seed data, queues, jobs, buckets, integrations, secrets |
| `scripts/audit-composition.ts` runs post-build | Server-graph audit (.nft.json + .next/trace) + client-bundle audit (stats JSON), keyed by `surfaceKinds`, + string-search backstop + content-hash determinism check |
| `scripts/generate-ci-matrix.ts` runs on module-config changes | Writes `packages/shell/src/_generated/composition-matrix.yml`; static `.github/workflows/composition-matrix.yml` reads it via `fromJSON(yq)`; pairwise scoped to overlap on shellSurfaces ∪ backends ∪ schemas ∪ queues ∪ jobs ∪ buckets ∪ integrations ∪ env ∪ cache-key/redis/rabbit namespaces |
| `scripts/lint-tsconfig.ts` runs in CI | Rejects `@modules/*` path aliases (or any alias that resolves to a module package root) |
| `scripts/generate-eslint-zones.ts` runs at lint setup | Generates the `import/no-restricted-paths` zone array from the current set of `packages/modules/*/` directories. Catches sibling-relative traversal (`../../<sibling>/...`) that doesn't carry a `modules/` segment in the resolved string. Closes the pass-3 BLOCK-1 residual |
| Workspace-root `eslint.config.js` enforces import-boundary on six bypass paths | Static ESM, re-exports, dynamic import(), require(), relative traversal, path aliases, side-effect imports — all forbidden outside `_generated/` |
| `module.config.ts` is the per-module source of truth | Includes `requires.{backends,sharedServices,schemas,migrations,env,health,seedData,queues,jobs,buckets,integrations,secrets}` and `shellSurfaces.{navOrderSlots,cacheTagPrefixes,commandPaletteScopes,routePrefixes}` |
| `module.config.ts` purity gate | Compile-step check that each `module.config.ts` has zero imports from sibling modules, no `next/*` imports, no I/O. CI fails on violation |
| Manifest schema is YAML at `infrastructure/manifests/<instance>.yml` | New directory in SP-0 scope; existing `.env.*` pattern stays for instance-specific secret *values*; manifest holds secret *references* only |
| `schemas/instance-manifest.schema.json` published | Strict-mode JSON Schema (Ajv `additionalProperties: false`); validator runs before transitive-closure check |
| Generated artifact determinism | `scripts/generate-composition.ts` is hermetic — same inputs produce byte-identical output; CI re-runs the generator and diffs against checked-in `_generated/` |
| Generated artifact staleness | Content-addressed: every generated file embeds `// input_hash: sha256:<hex>`; pre-build hook and CI both recompute and compare. **No mtime comparisons** anywhere |
| `scripts/validate-secret-references.ts` runs in PR CI | **Offline only**: URI shape grammar + `infrastructure/secret-catalog.yml` ownership + uniqueness across `module.config.ts`. No live secret-manager calls |
| `scripts/verify-instance-secrets.ts` runs at deploy + boot | **Environment-bound**: calls the target instance's configured secret manager; halts rollout / refuses to start if any required secret is missing. Never runs in PR CI |
| Module `surfaceKinds` declaration | Each `module.config.ts` declares `surfaceKinds: ["server"|"client", ...]`; audit uses it to apply server-trace vs client-bundle expectations correctly |
| Composition matrix workflow is static | `.github/workflows/composition-matrix.yml` is a hand-written workflow that reads `packages/shell/src/_generated/composition-matrix.yml` at runtime via `fromJSON(yq)`. Single canonical generated path; no path inconsistency |
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
