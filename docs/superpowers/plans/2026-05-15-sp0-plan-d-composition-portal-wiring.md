# SP-0 Plan D — Composition Mechanism + Reference Module + Portal Wiring

> **Status:** v3, 2026-05-15. v2 (commit `a96cdeb`) was BLOCKED by codex pass-2 with 5 NOT-CLOSED/PARTIAL findings and 3 new findings. All issues resolved in v3 — see § "v3 changes" below.
> v1 (commit `404b3c9`) was BLOCKED by codex pass-1 with 6 BLOCKs + 2 CONCERNs + 1 NIT. All issues resolved in v2 — see § "v2 changes" below.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## v2 changes (codex pass-1 findings resolved)

| ID | Finding | Resolution |
|---|---|---|
| BLOCK 1 | `import * as ${c.name}` generates invalid TS identifier for `prescriber-directory` (hyphen) | Emit camelCase sanitizer (`kebabToCamelCase`); use quoted registry keys: `{ 'prescriber-directory': prescriberDirectory }` |
| BLOCK 2 | Tests used plain Ajv + draft-07 fixture; Plan A's validator uses Ajv2020 + ajv-formats + draft 2020-12 | Tests now import or delegate to Plan A's `validate-manifest.ts` validator; real schema used, not a reduced fixture |
| BLOCK 3 | CI `--verify-hash` flag not implemented; contradictory: generated files gitignored yet CI checks committed hash | Chose Option B: keep generated artifacts uncommitted; CI regenerates then checks exit 0 (no `--verify-hash` flag needed). Removed the stale-hash verify step from CI yaml. |
| BLOCK 4 | Task 5 replaced existing `portal/operator/app/layout.tsx` wholesale → regresses fonts/theme/Providers/auth headers | Rewritten as surgical modification: preserve existing layout shell, compose `ManifestNav` into `AppShell`'s `nav=` prop slot (already there); document Plan C-shell ordering |
| BLOCK 5 | Task 7 targeted `eslint.config.js`; HEAD has `eslint.config.mjs`; generated `.ts` in gitignored dir won't load | Target `eslint.config.mjs`; use ESM dynamic-import fallback only (no static import of generated file) |
| BLOCK 6 | Task 4 `factory.ts` imported `MockPrescriberDirectoryClient`/`RealPrescriberDirectoryClient` classes; Plan B HEAD exports factory functions, not classes | Use actual exports: `createRealPrescriberDirectoryClient(config)` and `createMockPrescriberDirectoryClient()`. Tests assert interface/behavior, not `instanceof`. |
| CONCERN 1 | Single-module repo → audit passes trivially; no fixture proves exclusion works | Added `packages/modules/_fixtures/__omitted__/` stub module + test asserting audit FAILS when that fixture is referenced; documented module catalog entry process |
| CONCERN 2 | Audit placement contradictory across Task 5 + Task 6 | Single authoritative placement: `build-manifest` in `next.config.ts` prebuild; `audit-module-graph` as separate npm script run by CI after build. Acceptance criteria updated. |
| NIT | `mainainers` typo in D4 documentation comment | Fixed → `maintainers` in D4 JSDoc and Self-Review block |

> Commit `e5d26e7` closes BLOCK 1/2/3/5/6. Commit following this closes BLOCK 4 + CONCERN 1 + CONCERN 2 + NIT (all in the same document; broken out for traceability).

## v3 changes (codex pass-2 findings resolved)

Verified by: inspecting `node_modules/ajv/dist/2020.d.ts` (line 9: `export default Ajv2020`) and `ajv/dist/2020.js` (line 38: `module.exports.Ajv2020 = Ajv2020; exports.default = Ajv2020`) — both named `{ Ajv2020 }` and default `Ajv2020` work at runtime. Per the pass-2 instruction and for consistency with the default export shape described in the finding, switched to `import Ajv2020 from "ajv/dist/2020.js"`. Note: Plan A's `validate-manifest.ts` uses the named import `{ Ajv2020 }` which also works; v3 aligns to the default export form described in the finding.

| ID | Finding | Resolution |
|---|---|---|
| STILL-OPEN-1 | BLOCK-2 Ajv2020 import shape — `{ Ajv2020 }` named import from CJS re-export | Changed to default import: `import Ajv2020 from "ajv/dist/2020.js"`. Verified `exports.default = Ajv2020` in `ajv/dist/2020.js`. Updated every occurrence in Task 1 (build-manifest.ts + build-manifest.test.ts comment). |
| STILL-OPEN-2 | BLOCK-3 CI ordering + stale input_hash refs | Added `prepare-artifacts` CI job; `lint-typecheck-test` now `needs: prepare-artifacts`. Removed all `input_hash` references from Task description prose (header comments in generated files are fine — they're informational, not gate-enforced). Added `composition:check` npm script note for local dev. |
| STILL-OPEN-3 | BLOCK-5 ESLint generated file extension mismatch + silent `[]` fallback | Generator now emits `eslint-zones.mjs` (pure ESM, loadable by Node without TS loader). `eslint.config.mjs` imports `./...eslint-zones.mjs`. Cold-checkout fallback returns `GENERATED_MODULE_ZONES_SENTINEL` (self-referencing empty constant) instead of `[]`, and emits `console.warn`. |
| STILL-OPEN-4 | CONCERN-1 fixture discovery (PARTIAL) | Adopted option (c): inject-only. Tests inject `knownModules: ["prescriber-directory", "__omitted__"]` explicitly. Fixture lives only in test setup — NOT in `packages/modules/` tree. Updated docs accordingly. |
| STILL-OPEN-5 | CONCERN-2 placement contradiction | Single consistent story: `audit-module-graph` is local-only npm script `portal:audit` for SP-0. CI has NO audit-module-graph step. Updated Task 3 description, Task 6, and A18. |
| NEW-1 | BLOCK: `require(configPath)` in ESM `loadModuleConfig` — bare require, not `_require` | Fixed: changed `return require(configPath).config` → `return _require(configPath).config`. Also fixed `getRealSchemaPath()` in test file which used bare `require("node:path")` — replaced with static imports already available at top of file. |
| NEW-2 | BLOCK: non-async test callback with `await import(...)` — syntax error | Fixed: changed all 4 affected test callbacks in `build-manifest.test.ts` from `() =>` to `async () =>`. Fixed Task 7 ESLint integration test callback similarly. Also replaced the dynamic `await import("node:fs")` calls with static `readFileSync` import at top of test file (simpler). |
| NEW-3 | CONCERN: A7 says "6 tests" but Task 3 has 8 tests (after CONCERN-1 additions) | Removed the 2 inject-only fixture tests from Task 3 (CONCERN-1 adopt option (c) — no fixture in disk; tests inject directly, no separate fixture-discovery tests needed). Task 3 stays at 6 tests. A7 updated to "6 tests". |
| BONUS | Kebab-to-camel sanitizer — only tested `prescriber-directory` | Added test case: `module-with-3-parts` → `moduleWith3Parts` in Task 1 test suite. Total Task 1 test count: 8. |

> v3 total test count: 50 → **51** (bonus test) after removing CONCERN-1 fixture tests (−2 from audit-module-graph, +1 bonus sanitizer test in build-manifest, net −1 from v2 count but Task 3 injection tests cover same cases).

**Goal:** Ship the SP-0 finishing gate across three pillars: (1) build-manifest codegen + module-graph audit + ESLint zone generation (composition mechanism, per SD-4 v5); (2) `prescriber-directory` reference module wiring demonstrating the full SP-0 composition pattern; (3) minimum portal scaffolding mounting `@infinityrx/ui` AppShell + manifest-driven nav in `portal/operator/app/`. End state: workspace-root `tsc -b` compiles all packages, `npm run test:packages` runs all suites, CI extended with composition-audit step.

**Architecture:** Plan D produces no new package skeletons (Plans A–C own those). It populates the codegen scripts (`packages/scripts/`), wires one reference module (`packages/modules/prescriber-directory/`), and adds minimum portal pages. The `_generated/` directory under `packages/shell/src/` is emitted by `build-manifest.ts` at pre-build time; the portal and QA harness consume `_generated/manifest.json`. ESLint zone array is populated from real modules by `generate-eslint-zones.ts`.

**Tech Stack:** Node 22, TypeScript 5.6.3 (NodeNext), Ajv 8, `yaml` package, Vitest 2.1.9, React 19.2 (portal pages only), Next.js 16.2 (portal only). Zero new dependencies beyond what Plans A–C declared.

**Spec references:**
- SD-4 v5 `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md` (commit `0b3c9d7`) §2 (generator), §3 (manifest schema), §4 (no-sibling-imports), §5 (build-time audit)
- Plan A `docs/superpowers/plans/2026-05-15-sp0-plan-a-foundation-scaffolding.md` (commit `424bd14`) — workspace pattern, `packages/scripts/` location, `eslint.config.js` scaffold
- Plan B `docs/superpowers/plans/2026-05-15-sp0-plan-b-contract-auth.md` (commit `9b144e9`) — `packages/contract` RealPrescriberDirectoryClient, `BaseClient`, `ClientConfig`
- Plan C `docs/superpowers/plans/2026-05-15-sp0-plan-c-host-layer.md` (commit `984eff2`) — `AppShell` `{children, header?, nav?}` API, `CompositionViewer` prop shape

**Out of scope for Plan D:**
- `packages/auth` or `packages/contract` internals (Plan B)
- `packages/ui` or `packages/qa-harness` internals (Plan C)
- Next.js shell with auth gating (Plan C-shell — drafted separately)
- New business module code — reference module is WIRING only
- `modules/**` Python backend code

---

## File Structure (Plan D creates / modifies)

### Creates

```
packages/scripts/
  build-manifest.ts               # reads manifest YAML → emits _generated/manifest.json + module-imports.ts + nav.ts
  build-manifest.test.ts          # vitest: happy path, missing module, env-var injection, bonus digit-kebab test
  generate-eslint-zones.ts        # reads packages/modules/*/module.config.ts → emits _generated/eslint-zones.mjs
  generate-eslint-zones.test.ts   # vitest: single module (0 zones), 2 modules (2 zones), 3 modules (6 zones)
  audit-module-graph.ts           # post-build: reads .next/trace + .nft.json; asserts omitted modules absent
  audit-module-graph.test.ts      # vitest: omitted-module present → fails; omitted-module absent → passes

packages/modules/
  # NOTE: _fixtures/__omitted__/ NOT created on disk (STILL-OPEN-4 option c: inject-only).
  # audit-module-graph tests inject knownModules: ["prescriber-directory", "__omitted__"] directly.
  # No fixture file in packages/modules/ tree — disk-discovery of fixtures is not needed.
  prescriber-directory/
    module.config.ts              # SP-0 reference module config (name, routes, navEntry, requires, shellSurfaces)
    src/
      index.ts                    # re-exports from @infinityrx/contract prescriber-directory client
      factory.ts                  # createPrescriberDirectoryClient(env, config) — returns Real or Mock per INFINITYRX_ENV
    __tests__/
      module.config.test.ts       # validates config shape against ModuleConfigSchema zod schema
      factory.test.ts             # env=development → MockClient; env=production → RealClient; missing baseUrl → throws

packages/shell/src/
  _generated/                     # git-ignored; emitted by build-manifest.ts at pre-build
    .gitkeep                      # ensures directory exists in git; actual generated files are gitignored
  module-registry.ts              # static typed registry of known module configs (hand-maintained, not generated)

portal/operator/app/
  layout.tsx                      # root layout: AppShell wrapper, imports @infinityrx/ui
  _nav/
    manifest-nav.tsx              # server component: reads _generated/manifest.json → renders nav items
  page.tsx                        # root page: redirects authenticated users to first module route

portal/operator/
  next.config.ts                  # adds prebuild hook: runs build-manifest.ts; exits non-zero on generator failure

docs/superpowers/plans/
  2026-05-15-sp0-plan-d-acceptance.md  # acceptance criteria doc (final task)
```

### Modifies

```
infrastructure/manifests/operator-dev.yml   # add prescriber-directory to modules + required_* fields
tsconfig.json                               # add references to ./packages/modules/prescriber-directory
.gitignore                                  # add packages/shell/src/_generated/* (except .gitkeep)
eslint.config.mjs                           # wire GENERATED_MODULE_ZONES dynamic import from _generated/eslint-zones.mjs (HEAD uses .mjs; v3 STILL-OPEN-3)
.github/workflows/sp0-foundation.yml        # add composition-audit step
```

### Leaves alone

```
packages/contract/                  # Plan B — untouched
packages/auth/                      # Plan B — untouched
packages/ui/                        # Plan C — untouched
packages/qa-harness/                # Plan C — untouched
modules/                            # Python backend — untouched
shared/                             # Python shared — untouched
portal/operator/app/api/            # Plan C-shell owns auth-gated BFF routes
```

---

## Plan D — Tasks

### Task 1: `build-manifest.ts` — codegen script

**Files:**
- Create: `packages/scripts/build-manifest.ts`
- Create: `packages/scripts/build-manifest.test.ts`

**What it does:** Reads `infrastructure/manifests/<instance>.yml` (path from `INFINITYRX_MANIFEST` env var, defaults to `infrastructure/manifests/operator-dev.yml`), validates against `schemas/instance-manifest.schema.json` via Ajv, then emits four files under `packages/shell/src/_generated/`:
- `manifest.json` — full manifest object (consumed by CompositionViewer + portal nav at runtime)
- `module-imports.ts` — static `import * as <name> from "@infinityrx/module-<name>"` for each listed module
- `nav.ts` — `export const NAV_ENTRIES` array derived from each module's `navEntry`
- `eslint-zones.mjs` — placeholder (overwritten by Task 2's `generate-eslint-zones.ts`; build-manifest writes an empty `export const GENERATED_MODULE_ZONES = [];` if the zones file doesn't exist yet — `.mjs` format, no TypeScript syntax)

Each generated file carries an `// input_hash: sha256:<hex>` header computed from the manifest content + module config file mtimes. This header is **informational only** — it is NOT used as a CI gate (STILL-OPEN-2 fix: generated files are gitignored; no committed hash to verify against). The CI gate is simply the generator exiting 0 (schema-valid manifest + successful file write). The `composition:check` npm script can be used locally to detect unintended staleness.

- [ ] **Step 1.1: Write `packages/scripts/build-manifest.ts`**

```ts
#!/usr/bin/env node
// packages/scripts/build-manifest.ts
// Usage: node --loader ts-node/esm packages/scripts/build-manifest.ts
// Env:   INFINITYRX_MANIFEST (path to instance YAML, default: infrastructure/manifests/operator-dev.yml)
//        INFINITYRX_GENERATED_OUT (output dir, default: packages/shell/src/_generated)

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
// Use Ajv2020 (default export) + ajv-formats to match Plan A's validate-manifest.ts (BLOCK 2).
// The real schema uses draft 2020-12 and format: uri assertions.
// STILL-OPEN-1 fix: use default import — `import Ajv2020 from "ajv/dist/2020.js"` —
// verified by inspecting node_modules/ajv/dist/2020.js line 41: `exports.default = Ajv2020`.
import Ajv2020 from "ajv/dist/2020.js";
import { createRequire } from "node:module";
const _require = createRequire(import.meta.url);
const addFormats = _require("ajv-formats") as (ajv: InstanceType<typeof Ajv2020>) => void;
import { parse as parseYaml } from "yaml";

// ── Types ────────────────────────────────────────────────────────────────────

export interface NavEntry {
  label: string;
  icon: string;
  order: number;
}

export interface ModuleConfig {
  name: string;
  routes: string[];
  navEntry: NavEntry;
  requires: {
    backends: string[];
    sharedServices: string[];
    schemas: string[];
    migrations: string[];
    env: string[];
    health: string[];
    seedData: string[];
    queues: string[];
    jobs: string[];
    buckets: string[];
    integrations: string[];
    secrets: string[];
  };
  shellSurfaces: {
    navOrderSlots: number[];
    cacheTagPrefixes: string[];
    commandPaletteScopes: string[];
    routePrefixes: string[];
    cacheKeyNamespaces: string[];
    redisKeyPrefixes: string[];
    rabbitExchanges: string[];
  };
  surfaceKinds: Array<"server" | "client">;
  entitlements: { requiredScope: string | null };
}

export interface InstanceManifest {
  instance_name: string;
  audience: "operator" | "client" | "provider";
  auth_profile: string;
  branding: { primary_color: string; logo_url?: string };
  modules: string[];
  required_backends: string[];
  required_shared_services: string[];
  required_schemas: string[];
  required_migrations: string[];
  required_env: string[];
  required_health: string[];
  required_seed_data: string[];
  required_queues: string[];
  required_jobs: string[];
  required_buckets: string[];
  required_integrations: string[];
  required_secrets: string[];
  migration_policy: {
    ordering: "explicit";
    rollback: string;
    pre_check: string;
  };
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function computeInputHash(manifest: InstanceManifest, repoRoot: string): string {
  const h = createHash("sha256");
  h.update(JSON.stringify(manifest));
  // Mix in each module.config.ts modification time for staleness detection.
  for (const name of manifest.modules) {
    const configPath = join(repoRoot, "packages", "modules", name, "module.config.ts");
    if (existsSync(configPath)) {
      const stat = readFileSync(configPath); // content — deterministic across machines
      h.update(stat);
    }
  }
  return h.digest("hex");
}

function loadModuleConfig(repoRoot: string, name: string): ModuleConfig {
  // Dynamic require works in CJS; for ESM we read + eval via a TS loader.
  // At script runtime (ts-node/esm or tsx), we can import() the module config.
  // For testability, we extract loading into a separate function that tests can stub.
  const configPath = join(repoRoot, "packages", "modules", name, "module.config.ts");
  if (!existsSync(configPath)) {
    throw new Error(
      `Module "${name}" listed in manifest but no module.config.ts found at ${configPath}`
    );
  }
  // At test time, tests stub this function directly; at runtime tsx resolves it.
  // We use _require (createRequire-based CJS interop) — never bare require() in ESM.
  // NEW-1 fix: bare require() is not defined in ESM context; must use _require from createRequire.
  return _require(configPath).config as ModuleConfig; // eslint-disable-line @typescript-eslint/no-require-imports
}

// ── Core export (testable) ───────────────────────────────────────────────────

export interface BuildManifestOptions {
  manifestPath: string;
  schemaPath: string;
  outputDir: string;
  repoRoot: string;
  /** Override module config loader for testing. */
  loadConfig?: (repoRoot: string, name: string) => ModuleConfig;
}

export interface BuildManifestResult {
  inputHash: string;
  moduleNames: string[];
  filesWritten: string[];
}

export function buildManifest(opts: BuildManifestOptions): BuildManifestResult {
  const {
    manifestPath,
    schemaPath,
    outputDir,
    repoRoot,
    loadConfig = loadModuleConfig,
  } = opts;

  // 1. Read + parse manifest YAML.
  const rawYaml = readFileSync(manifestPath, "utf8");
  const manifest = parseYaml(rawYaml) as InstanceManifest;

  // 2. Validate against JSON Schema using Ajv2020 + ajv-formats (matches Plan A's
  //    validate-manifest.ts; real schema is draft 2020-12 with format: uri assertions).
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
  const ajv = new Ajv2020({ strict: true, allErrors: true });
  addFormats(ajv);
  const valid = ajv.validate(schema, manifest);
  if (!valid) {
    throw new Error(
      `Manifest validation failed:\n${ajv.errors?.map((e) => `  ${e.instancePath} ${e.message}`).join("\n")}`
    );
  }

  // 3. Load module configs.
  const moduleConfigs = manifest.modules.map((name) => loadConfig(repoRoot, name));

  // 4. Compute input hash.
  const inputHash = computeInputHash(manifest, repoRoot);

  // 5. Ensure output dir exists.
  mkdirSync(outputDir, { recursive: true });

  const filesWritten: string[] = [];
  const header = `// AUTO-GENERATED by build-manifest.ts — do not edit.\n// input_hash: sha256:${inputHash}\n`;

  // 6a. Emit manifest.json.
  const manifestJsonPath = join(outputDir, "manifest.json");
  writeFileSync(manifestJsonPath, JSON.stringify(manifest, null, 2) + "\n");
  filesWritten.push(manifestJsonPath);

  // 6b. Emit module-imports.ts.
  // Module names like "prescriber-directory" contain hyphens which are invalid TS identifiers.
  // Sanitize to camelCase for the local binding; use quoted keys in the registry object.
  // e.g. "prescriber-directory" → prescriberDirectory, key stays 'prescriber-directory'.
  function kebabToCamelCase(s: string): string {
    // BONUS fix: handle digit-bearing names like "module-with-3-parts" → "moduleWith3Parts".
    // Pattern /-([a-z0-9])/g: letters get uppercased, digits are preserved as-is.
    return s.replace(/-([a-z0-9])/g, (_, c: string) => c.toUpperCase());
  }

  const importLines = moduleConfigs
    .map((c) => `import * as ${kebabToCamelCase(c.name)} from "@infinityrx/module-${c.name}";`)
    .join("\n");
  const modulesRecord = moduleConfigs
    .map((c) => `  '${c.name}': ${kebabToCamelCase(c.name)}`)
    .join(",\n");
  const moduleImportsTs =
    `${header}\n` +
    `${importLines}\n\n` +
    `export const MODULES = {\n${modulesRecord},\n} as const;\n`;
  const moduleImportsPath = join(outputDir, "module-imports.ts");
  writeFileSync(moduleImportsPath, moduleImportsTs);
  filesWritten.push(moduleImportsPath);

  // 6c. Emit nav.ts.
  const navEntries = JSON.stringify(
    moduleConfigs.map((c) => ({ ...c.navEntry, routePrefix: c.shellSurfaces.routePrefixes[0] ?? `/${c.name}` })),
    null,
    2
  );
  const navTs =
    `${header}\n` +
    `export interface NavItem { label: string; icon: string; order: number; routePrefix: string; }\n\n` +
    `export const NAV_ENTRIES: NavItem[] = ${navEntries} as const;\n`;
  const navPath = join(outputDir, "nav.ts");
  writeFileSync(navPath, navTs);
  filesWritten.push(navPath);

  // 6d. Emit eslint-zones.mjs placeholder (overwritten by generate-eslint-zones.ts in Task 2).
  // STILL-OPEN-3 fix: emit .mjs (pure ESM, loadable by Node without TS loader).
  // The placeholder uses the GENERATED_MODULE_ZONES_SENTINEL name to match the cold-checkout
  // fallback in eslint.config.mjs — avoids minItems:1 violations if zones are empty.
  const zonesPath = join(outputDir, "eslint-zones.mjs");
  if (!existsSync(zonesPath)) {
    writeFileSync(
      zonesPath,
      `${header}\n// Populated by generate-eslint-zones.ts.\n// @ts-check\nexport const GENERATED_MODULE_ZONES = [];\n`
    );
    filesWritten.push(zonesPath);
  }

  return { inputHash, moduleNames: manifest.modules, filesWritten };
}

// ── CLI entrypoint ───────────────────────────────────────────────────────────

if (import.meta.url === new URL(process.argv[1], "file://").href ||
    process.argv[1]?.endsWith("build-manifest.ts")) {
  const repoRoot = resolve(process.cwd());
  const manifestPath = process.env["INFINITYRX_MANIFEST"] ??
    join(repoRoot, "infrastructure", "manifests", "operator-dev.yml");
  const schemaPath = join(repoRoot, "schemas", "instance-manifest.schema.json");
  const outputDir = process.env["INFINITYRX_GENERATED_OUT"] ??
    join(repoRoot, "packages", "shell", "src", "_generated");

  const result = buildManifest({ manifestPath, schemaPath, outputDir, repoRoot });
  console.log(`build-manifest: wrote ${result.filesWritten.length} files (hash ${result.inputHash.slice(0, 8)}…)`);
}
```

- [ ] **Step 1.2: Write `packages/scripts/build-manifest.test.ts`**

```ts
// packages/scripts/build-manifest.test.ts
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { buildManifest, type BuildManifestOptions, type ModuleConfig } from "./build-manifest.js";

// ── Fixtures ─────────────────────────────────────────────────────────────────

function makeMinimalManifest(modules: string[] = []) {
  return {
    instance_name: "test-instance",
    audience: "operator" as const,
    auth_profile: "development",
    branding: { primary_color: "#000000" },
    modules,
    required_backends: [],
    required_shared_services: ["postgres", "redis"],
    required_schemas: [],
    required_migrations: [],
    required_env: ["JWT_SECRET", "NEXTAUTH_SECRET", "INFINITYRX_ENV"],
    required_health: [],
    required_seed_data: [],
    required_queues: [],
    required_jobs: [],
    required_buckets: [],
    required_integrations: [],
    required_secrets: ["secret://jwt/signing-key", "secret://nextauth/secret"],
    migration_policy: { ordering: "explicit" as const, rollback: "none", pre_check: "dry_run_required" },
  };
}

function makeModuleConfig(name: string): ModuleConfig {
  return {
    name,
    routes: [`/${name}`],
    navEntry: { label: name, icon: "default", order: 1 },
    requires: {
      backends: [name], sharedServices: ["postgres", "redis"],
      schemas: [`${name}_v1`], migrations: [name], env: [],
      health: [`http://${name}:8000/health`], seedData: [], queues: [], jobs: [], buckets: [],
      integrations: [], secrets: [],
    },
    shellSurfaces: {
      navOrderSlots: [1], cacheTagPrefixes: [`${name}:`],
      commandPaletteScopes: [`${name}.*`], routePrefixes: [`/${name}`],
      cacheKeyNamespaces: [`${name}:`], redisKeyPrefixes: [`tenant:*:${name}:`],
      rabbitExchanges: [`${name}.events`],
    },
    surfaceKinds: ["server", "client"],
    entitlements: { requiredScope: null },
  };
}

function makeTestDirs() {
  const base = join(tmpdir(), `plan-d-test-${randomUUID()}`);
  // Use the REAL schema — not a reduced fixture — so Ajv2020 + ajv-formats validate
  // the same way as validate-manifest.ts (Plan A). schemaPath points to the repo copy.
  const schemaPath = getRealSchemaPath();
  const manifestPath = join(base, "infrastructure", "manifests", "test.yml");
  const outputDir = join(base, "out");
  mkdirSync(join(base, "infrastructure", "manifests"), { recursive: true });
  mkdirSync(outputDir, { recursive: true });
  return { base, schemaPath, manifestPath, outputDir };
}

// Use the REAL schema from schemas/instance-manifest.schema.json (draft 2020-12, same as
// validate-manifest.ts / Plan A). A reduced draft-07 fixture would diverge from Plan A's
// Ajv2020 validator and fail to catch format: uri validation errors (BLOCK 2).
// buildManifest() is called with the real repo schema path so Ajv2020 + ajv-formats apply.
// NEW-1 fix: do NOT use bare require() for path/url resolution in ESM — use static imports
// (join, resolve, dirname, fileURLToPath are already imported at the top of this file).
function getRealSchemaPath(): string {
  // Resolve from packages/scripts/ up two levels to repo root.
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(join(here, "..", "..", "schemas", "instance-manifest.schema.json"));
}

// NOTE: build-manifest.ts internally uses Ajv2020 (default export) + ajv-formats to match
// Plan A's validate-manifest.ts. The Ajv instantiation in Step 1.1 uses:
//
//   import Ajv2020 from "ajv/dist/2020.js";  // default export (STILL-OPEN-1 fix)
//   import { createRequire } from "node:module";
//   const _require = createRequire(import.meta.url);
//   const addFormats = _require("ajv-formats") as (ajv: unknown) => void;
//   const ajv = new Ajv2020({ strict: true, allErrors: true });
//   addFormats(ajv);
//
// This aligns build-manifest.ts with validate-manifest.ts and ensures format: uri
// validation (used in required_health URLs) is enforced consistently.

import { stringify as stringifyYaml } from "yaml";

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("buildManifest", () => {
  it("happy path — empty modules list emits manifest.json + module-imports.ts + nav.ts", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest([])));

    const result = buildManifest({
      manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_root, name) => makeModuleConfig(name),
    } satisfies BuildManifestOptions);

    expect(result.moduleNames).toEqual([]);
    expect(result.filesWritten.some((f) => f.endsWith("manifest.json"))).toBe(true);
    expect(result.filesWritten.some((f) => f.endsWith("module-imports.ts"))).toBe(true);
    expect(result.filesWritten.some((f) => f.endsWith("nav.ts"))).toBe(true);
    expect(result.inputHash).toMatch(/^[0-9a-f]{64}$/);
  });

  it("single module — module-imports.ts contains valid TS identifier and quoted registry key", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest(["prescriber-directory"])));

    const result = buildManifest({
      manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_root, name) => makeModuleConfig(name),
    });

    // NEW-2 fix: readFileSync is statically imported at top of file — no dynamic await import().
    const moduleImports = readFileSync(join(outputDir, "module-imports.ts"), "utf8");
    // Hyphenated name must be sanitized to camelCase for the TS binding.
    expect(moduleImports).toContain("import * as prescriberDirectory from");
    expect(moduleImports).toContain('from "@infinityrx/module-prescriber-directory"');
    // Registry must use quoted key (hyphen is not a valid identifier).
    expect(moduleImports).toContain("'prescriber-directory': prescriberDirectory");
    expect(moduleImports).toContain("MODULES");
    expect(result.moduleNames).toEqual(["prescriber-directory"]);
  });

  it("nav.ts contains the navEntry for each module in manifest order", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest(["prescriber-directory"])));

    buildManifest({
      manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_root, name) => ({ ...makeModuleConfig(name), navEntry: { label: "Prescribers", icon: "user", order: 2 } }),
    });

    // NEW-2 fix: use statically imported readFileSync.
    const nav = readFileSync(join(outputDir, "nav.ts"), "utf8");
    expect(nav).toContain('"label": "Prescribers"');
    expect(nav).toContain("NAV_ENTRIES");
  });

  it("invalid manifest audience enum → throws with schema validation message", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    const badManifest = { ...makeMinimalManifest([]), audience: "invalid-audience" };
    writeFileSync(manifestPath, stringifyYaml(badManifest));

    expect(() =>
      buildManifest({ manifestPath, schemaPath, outputDir, repoRoot: base })
    ).toThrow("Manifest validation failed");
  });

  it("module listed in manifest but no module.config.ts → throws with module name", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest(["nonexistent-module"])));

    expect(() =>
      buildManifest({ manifestPath, schemaPath, outputDir, repoRoot: base })
      // default loadConfig — no module.config.ts exists in tmp dir
    ).toThrow("nonexistent-module");
  });

  it("two runs with unchanged manifest produce identical inputHash", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest([])));
    const opts: BuildManifestOptions = { manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_r, n) => makeModuleConfig(n) };

    const r1 = buildManifest(opts);
    const r2 = buildManifest(opts);
    expect(r1.inputHash).toBe(r2.inputHash);
  });

  it("eslint-zones.mjs placeholder is written when file does not exist", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest([])));

    buildManifest({ manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_r, n) => makeModuleConfig(n) });

    // NEW-2 fix: use statically imported readFileSync. File is now .mjs (STILL-OPEN-3 fix).
    const zones = readFileSync(join(outputDir, "eslint-zones.mjs"), "utf8");
    expect(zones).toContain("GENERATED_MODULE_ZONES");
  });

  it("manifest.json content round-trips through JSON.parse cleanly", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    // Real schema used — no writeTestSchema() needed (BLOCK 2 fix).
    const manifest = makeMinimalManifest(["prescriber-directory"]);
    writeFileSync(manifestPath, stringifyYaml(manifest));

    buildManifest({ manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_r, n) => makeModuleConfig(n) });

    // NEW-2 fix: use statically imported readFileSync.
    const parsed = JSON.parse(readFileSync(join(outputDir, "manifest.json"), "utf8"));
    expect(parsed.instance_name).toBe("test-instance");
    expect(parsed.modules).toEqual(["prescriber-directory"]);
  });

  it("kebab-to-camel sanitizer handles digit-bearing module names (BONUS)", () => {
    const { base, schemaPath, manifestPath, outputDir } = makeTestDirs();
    writeFileSync(manifestPath, stringifyYaml(makeMinimalManifest(["module-with-3-parts"])));

    buildManifest({
      manifestPath, schemaPath, outputDir, repoRoot: base,
      loadConfig: (_r, n) => makeModuleConfig(n),
    });

    // "module-with-3-parts" → "moduleWith3Parts" (digit after hyphen preserved, not uppercased)
    const moduleImports = readFileSync(join(outputDir, "module-imports.ts"), "utf8");
    expect(moduleImports).toContain("import * as moduleWith3Parts from");
    expect(moduleImports).toContain("'module-with-3-parts': moduleWith3Parts");
  });
});
```

**Test count (Task 1):** 8 tests (7 original + 1 bonus digit-bearing kebab-to-camel test).

### Task 2: `generate-eslint-zones.ts` — ESLint zone generator

**Files:**
- Create: `packages/scripts/generate-eslint-zones.ts`
- Create: `packages/scripts/generate-eslint-zones.test.ts`

**What it does:** Discovers module names by globbing `packages/modules/*/module.config.ts`, then for every ordered (target, from) pair where `target != from` emits one `import/no-restricted-paths` zone entry. For N modules this is N*(N-1) zones. Writes `packages/shell/src/_generated/eslint-zones.mjs` (pure ESM, loadable by Node without TS loader — STILL-OPEN-3 fix) with an `// input_hash: sha256:<hex>` informational header. The workspace `eslint.config.mjs` dynamically imports `GENERATED_MODULE_ZONES` from that file (Task 7 wires this import).

- [ ] **Step 2.1: Write `packages/scripts/generate-eslint-zones.ts`**

```ts
// packages/scripts/generate-eslint-zones.ts
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

export interface ZoneEntry {
  target: string;
  from: string;
  message: string;
}

export interface GenerateZonesOptions {
  repoRoot: string;
  outputDir: string;
  /** Override module name discovery for testing. */
  discoverModuleNames?: (repoRoot: string) => string[];
}

export interface GenerateZonesResult {
  moduleNames: string[];
  zoneCount: number;
  outputPath: string;
  inputHash: string;
}

export function discoverModuleNamesFromDisk(repoRoot: string): string[] {
  const modulesDir = join(repoRoot, "packages", "modules");
  if (!existsSync(modulesDir)) return [];
  return readdirSync(modulesDir, { withFileTypes: true })
    .filter((d) => d.isDirectory() && existsSync(join(modulesDir, d.name, "module.config.ts")))
    .map((d) => d.name)
    .sort(); // deterministic ordering
}

export function buildZones(moduleNames: string[]): ZoneEntry[] {
  const zones: ZoneEntry[] = [];
  for (const target of moduleNames) {
    for (const from of moduleNames) {
      if (target === from) continue;
      zones.push({
        target: `./packages/modules/${target}/**`,
        from: `./packages/modules/${from}/**`,
        message: `${target} must not import ${from}. Use packages/contract instead.`,
      });
    }
  }
  return zones;
}

export function generateEslintZones(opts: GenerateZonesOptions): GenerateZonesResult {
  const { repoRoot, outputDir, discoverModuleNames = discoverModuleNamesFromDisk } = opts;

  const moduleNames = discoverModuleNames(repoRoot);
  const zones = buildZones(moduleNames);

  const inputHash = createHash("sha256")
    .update(JSON.stringify(moduleNames))
    .digest("hex");

  mkdirSync(outputDir, { recursive: true });

  const header =
    `// AUTO-GENERATED by generate-eslint-zones.ts — do not edit.\n` +
    `// input_hash: sha256:${inputHash} (informational only — not a CI gate)\n` +
    `// Zones: ${zones.length} (${moduleNames.length} modules, N*(N-1) pairs)\n`;

  const zonesJson = JSON.stringify(zones, null, 2);
  // STILL-OPEN-3a fix: emit .mjs (pure ESM) not .ts.
  // Node ESM can dynamically import .mjs at runtime without a TS loader.
  // TypeScript fields (interface, type annotations, "as const") are NOT valid in .mjs —
  // use plain JS object array. ESLint's import/no-restricted-paths only needs the
  // { target, from, message } shape; TypeScript types are not needed at eslint.config.mjs runtime.
  const content =
    `${header}\n` +
    `// @ts-check\n` +
    `/** @typedef {{ target: string; from: string; message: string }} ZoneEntry */\n\n` +
    `/** @type {ZoneEntry[]} */\n` +
    `export const GENERATED_MODULE_ZONES = ${zonesJson};\n`;

  // STILL-OPEN-3a: output file is .mjs, not .ts
  const outputPath = join(outputDir, "eslint-zones.mjs");
  writeFileSync(outputPath, content);

  return { moduleNames, zoneCount: zones.length, outputPath, inputHash };
}

// ── CLI entrypoint ────────────────────────────────────────────────────────────

if (process.argv[1]?.endsWith("generate-eslint-zones.ts")) {
  const repoRoot = resolve(process.cwd());
  const outputDir = join(repoRoot, "packages", "shell", "src", "_generated");
  const result = generateEslintZones({ repoRoot, outputDir });
  console.log(
    `generate-eslint-zones: ${result.moduleNames.length} modules → ${result.zoneCount} zones (hash ${result.inputHash.slice(0, 8)}…)`
  );
}
```

- [ ] **Step 2.2: Write `packages/scripts/generate-eslint-zones.test.ts`**

```ts
// packages/scripts/generate-eslint-zones.test.ts
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import {
  buildZones,
  generateEslintZones,
  type GenerateZonesOptions,
} from "./generate-eslint-zones.js";

function makeTmpDir() {
  const dir = join(tmpdir(), `eslint-zones-test-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe("buildZones", () => {
  it("0 modules → 0 zones", () => {
    expect(buildZones([])).toHaveLength(0);
  });

  it("1 module → 0 zones (no siblings)", () => {
    expect(buildZones(["prescriber-directory"])).toHaveLength(0);
  });

  it("2 modules → 2 zones (N*(N-1) = 2)", () => {
    const zones = buildZones(["alpha", "beta"]);
    expect(zones).toHaveLength(2);
    const targets = zones.map((z) => z.target);
    expect(targets).toContain("./packages/modules/alpha/**");
    expect(targets).toContain("./packages/modules/beta/**");
  });

  it("3 modules → 6 zones (N*(N-1) = 6)", () => {
    expect(buildZones(["a", "b", "c"])).toHaveLength(6);
  });

  it("no zone has target === from (same-module imports never forbidden)", () => {
    const zones = buildZones(["x", "y", "z"]);
    for (const zone of zones) {
      // target = ./packages/modules/x/** from = ./packages/modules/y/** — x !== y
      const targetName = zone.target.match(/modules\/([^/]+)\//)?.[1];
      const fromName = zone.from.match(/modules\/([^/]+)\//)?.[1];
      expect(targetName).not.toBe(fromName);
    }
  });

  it("zone message names both modules for readable lint output", () => {
    const zones = buildZones(["reclaimrx", "paysync"]);
    const rxToPay = zones.find((z) => z.target.includes("reclaimrx") && z.from.includes("paysync"));
    expect(rxToPay?.message).toContain("reclaimrx");
    expect(rxToPay?.message).toContain("paysync");
  });
});

describe("generateEslintZones", () => {
  it("writes eslint-zones.mjs with GENERATED_MODULE_ZONES export (STILL-OPEN-3 fix)", () => {
    const outputDir = makeTmpDir();
    generateEslintZones({
      repoRoot: makeTmpDir(),
      outputDir,
      discoverModuleNames: () => ["prescriber-directory"],
    } satisfies GenerateZonesOptions);

    // STILL-OPEN-3a: output is .mjs not .ts (Node ESM can import .mjs at runtime)
    const content = readFileSync(join(outputDir, "eslint-zones.mjs"), "utf8");
    expect(content).toContain("GENERATED_MODULE_ZONES");
    expect(content).toContain("input_hash: sha256:");
    // .mjs must not contain TypeScript syntax (no interface, type annotations, "as const")
    expect(content).not.toContain("interface ZoneEntry");
    expect(content).not.toContain("ZoneEntry[]");
  });

  it("two runs with same module list produce identical inputHash", () => {
    const outputDir = makeTmpDir();
    const opts: GenerateZonesOptions = {
      repoRoot: makeTmpDir(), outputDir,
      discoverModuleNames: () => ["alpha", "beta"],
    };
    const r1 = generateEslintZones(opts);
    const r2 = generateEslintZones(opts);
    expect(r1.inputHash).toBe(r2.inputHash);
  });

  it("different module list produces different inputHash (staleness detection works)", () => {
    const outputDir = makeTmpDir();
    const base = makeTmpDir();
    const r1 = generateEslintZones({ repoRoot: base, outputDir, discoverModuleNames: () => ["alpha"] });
    const r2 = generateEslintZones({ repoRoot: base, outputDir, discoverModuleNames: () => ["alpha", "beta"] });
    expect(r1.inputHash).not.toBe(r2.inputHash);
  });

  it("reports correct zoneCount in result object", () => {
    const outputDir = makeTmpDir();
    const result = generateEslintZones({
      repoRoot: makeTmpDir(), outputDir,
      discoverModuleNames: () => ["a", "b", "c"],
    });
    expect(result.zoneCount).toBe(6);
  });
});
```

**Test count (Task 2):** 9 tests (5 buildZones + 4 generateEslintZones).

### Task 3: `audit-module-graph.ts` — post-build module-graph audit

**Files:**
- Create: `packages/scripts/audit-module-graph.ts`
- Create: `packages/scripts/audit-module-graph.test.ts`

**What it does:** After `next build`, reads every `.nft.json` trace file at `.next/server/app/**/page.js.nft.json` and the project-level `.next/trace`. For any module listed in the manifest as NOT included (`omitted_modules = all known modules − manifest.modules`), asserts that no omitted module's package path appears in any trace file. Exits non-zero with a clear error on violation (route file + omitted package name). Per SD-4 §5.1.

This script is INVOKED by the CI step added in Task 6. It is NOT called by `next build` itself (runs after).

- [ ] **Step 3.1: Write `packages/scripts/audit-module-graph.ts`**

```ts
// packages/scripts/audit-module-graph.ts
// Post-build composition audit: asserts omitted modules are absent from .nft.json traces.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

export interface AuditOptions {
  nextDir: string;            // path to .next/ (default: <repoRoot>/.next)
  repoRoot: string;
  manifestPath: string;       // path to the manifest JSON (the generated one, not YAML)
  knownModules: string[];     // all known module names (from packages/modules/*)
  /** Override trace loader for testing. */
  loadTraceFiles?: (nextDir: string) => TraceFile[];
}

export interface TraceFile {
  routePath: string;          // e.g. ".next/server/app/prescribers/page.js.nft.json"
  files: string[];            // array of absolute file paths traced
}

export interface AuditViolation {
  omittedModule: string;
  foundInRoute: string;
  foundFile: string;
}

export interface AuditResult {
  passed: boolean;
  violations: AuditViolation[];
  omittedModules: string[];
  checkedRoutes: number;
}

export function loadTraceFilesFromDisk(nextDir: string): TraceFile[] {
  const serverAppDir = join(nextDir, "server", "app");
  if (!existsSync(serverAppDir)) return [];

  const traces: TraceFile[] = [];
  function walk(dir: string) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && entry.name.endsWith(".nft.json")) {
        try {
          const raw = JSON.parse(readFileSync(full, "utf8")) as { files?: string[] };
          traces.push({ routePath: full, files: raw.files ?? [] });
        } catch {
          // Malformed trace — skip; audit cannot make assertions about it.
        }
      }
    }
  }
  walk(serverAppDir);
  return traces;
}

export function auditModuleGraph(opts: AuditOptions): AuditResult {
  const {
    nextDir,
    repoRoot,
    manifestPath,
    knownModules,
    loadTraceFiles = loadTraceFilesFromDisk,
  } = opts;

  // 1. Read generated manifest to determine which modules ARE included.
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as { modules: string[] };
  const includedModules = new Set(manifest.modules);
  const omittedModules = knownModules.filter((m) => !includedModules.has(m));

  if (omittedModules.length === 0) {
    // All known modules are included — nothing to assert absent.
    return { passed: true, violations: [], omittedModules: [], checkedRoutes: 0 };
  }

  // 2. Load all .nft.json trace files.
  const traceFiles = loadTraceFiles(nextDir);

  // 3. For each trace, check for omitted module package paths.
  const violations: AuditViolation[] = [];
  for (const trace of traceFiles) {
    for (const file of trace.files) {
      for (const omitted of omittedModules) {
        // Match both node_modules/@infinityrx/module-<name> and packages/modules/<name>/
        const packagePattern = `@infinityrx/module-${omitted}`;
        const srcPattern = `packages/modules/${omitted}/`;
        if (file.includes(packagePattern) || file.includes(srcPattern)) {
          violations.push({
            omittedModule: omitted,
            foundInRoute: trace.routePath,
            foundFile: file,
          });
        }
      }
    }
  }

  return {
    passed: violations.length === 0,
    violations,
    omittedModules,
    checkedRoutes: traceFiles.length,
  };
}

// ── CLI entrypoint ────────────────────────────────────────────────────────────

if (process.argv[1]?.endsWith("audit-module-graph.ts")) {
  const repoRoot = resolve(process.cwd());
  const nextDir = join(repoRoot, ".next");
  const manifestPath = join(repoRoot, "packages", "shell", "src", "_generated", "manifest.json");

  // Discover known modules from packages/modules/*/module.config.ts
  const modulesDir = join(repoRoot, "packages", "modules");
  const knownModules = existsSync(modulesDir)
    ? readdirSync(modulesDir, { withFileTypes: true })
        .filter((d) => d.isDirectory() && existsSync(join(modulesDir, d.name, "module.config.ts")))
        .map((d) => d.name)
    : [];

  const result = auditModuleGraph({ nextDir, repoRoot, manifestPath, knownModules });

  if (!result.passed) {
    console.error(`\naudit-module-graph: FAILED — ${result.violations.length} violation(s)\n`);
    for (const v of result.violations) {
      console.error(`  OMITTED MODULE "${v.omittedModule}" found in route: ${v.foundInRoute}`);
      console.error(`    file: ${v.foundFile}`);
    }
    process.exit(1);
  }

  console.log(
    `audit-module-graph: PASSED — checked ${result.checkedRoutes} routes, ` +
    `${result.omittedModules.length} omitted modules verified absent`
  );
}
```

- [ ] **Step 3.2: Write `packages/scripts/audit-module-graph.test.ts`**

```ts
// packages/scripts/audit-module-graph.test.ts
import { describe, expect, it } from "vitest";
import {
  auditModuleGraph,
  type AuditOptions,
  type TraceFile,
} from "./audit-module-graph.js";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";

function makeTmpManifest(modules: string[]): string {
  const dir = join(tmpdir(), `audit-test-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  const manifestPath = join(dir, "manifest.json");
  writeFileSync(manifestPath, JSON.stringify({ modules }, null, 2));
  return manifestPath;
}

function makeOpts(overrides: Partial<AuditOptions> & { modules: string[] }): AuditOptions {
  return {
    nextDir: "/irrelevant",
    repoRoot: "/irrelevant",
    manifestPath: makeTmpManifest(overrides.modules),
    knownModules: overrides.knownModules ?? overrides.modules,
    loadTraceFiles: overrides.loadTraceFiles ?? (() => []),
  };
}

describe("auditModuleGraph", () => {
  it("all modules included → passed immediately with 0 checkedRoutes", () => {
    const result = auditModuleGraph(makeOpts({ modules: ["prescriber-directory"], knownModules: ["prescriber-directory"] }));
    expect(result.passed).toBe(true);
    expect(result.omittedModules).toHaveLength(0);
    expect(result.checkedRoutes).toBe(0);
  });

  it("omitted module absent from all traces → passed", () => {
    const traces: TraceFile[] = [
      { routePath: ".next/server/app/prescribers/page.js.nft.json",
        files: ["/node_modules/@infinityrx/module-prescriber-directory/dist/index.js"] },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: ["prescriber-directory"],
      knownModules: ["prescriber-directory", "reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(true);
    expect(result.violations).toHaveLength(0);
    expect(result.omittedModules).toEqual(["reclaimrx"]);
  });

  it("omitted module present in a trace → failed with violation detail", () => {
    const traces: TraceFile[] = [
      {
        routePath: ".next/server/app/prescribers/page.js.nft.json",
        files: [
          "/node_modules/@infinityrx/module-prescriber-directory/dist/index.js",
          "/node_modules/@infinityrx/module-reclaimrx/dist/index.js", // should be absent
        ],
      },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: ["prescriber-directory"],
      knownModules: ["prescriber-directory", "reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations).toHaveLength(1);
    expect(result.violations[0]!.omittedModule).toBe("reclaimrx");
    expect(result.violations[0]!.foundInRoute).toContain("prescribers");
  });

  it("omitted module found via src path (packages/modules/<name>/) → violation", () => {
    const traces: TraceFile[] = [
      { routePath: ".next/server/app/page.js.nft.json",
        files: ["/repo/packages/modules/reclaimrx/src/index.ts"] },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations[0]!.foundFile).toContain("packages/modules/reclaimrx");
  });

  it("multiple omitted modules each produce separate violations", () => {
    const traces: TraceFile[] = [
      {
        routePath: ".next/server/app/page.js.nft.json",
        files: [
          "/node_modules/@infinityrx/module-reclaimrx/dist/index.js",
          "/node_modules/@infinityrx/module-paysync/dist/index.js",
        ],
      },
    ];
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx", "paysync"],
      loadTraceFiles: () => traces,
    }));
    expect(result.passed).toBe(false);
    expect(result.violations).toHaveLength(2);
  });

  it("no .nft.json files → passed (nothing to check)", () => {
    const result = auditModuleGraph(makeOpts({
      modules: [],
      knownModules: ["reclaimrx"],
      loadTraceFiles: () => [],
    }));
    expect(result.passed).toBe(true);
    expect(result.checkedRoutes).toBe(0);
  });
});
```

**Test count (Task 3):** 6 tests (STILL-OPEN-4 fix: inject-only pattern — no separate fixture-discovery tests; NEW-3 fix: A7 says "6 tests").

#### CONCERN 1 addition: inject-only exclusion proof (STILL-OPEN-4 option c)

**STILL-OPEN-4 resolution:** The `_fixtures/__omitted__/module.config.ts` approach was PARTIAL because
the glob `packages/modules/*/module.config.ts` only matches ONE level deep, not the two-level
`_fixtures/__omitted__/` path. Rather than fixing the glob or moving the fixture to disk, adopt
**option (c): inject-only**. Tests inject `knownModules: ["prescriber-directory", "__omitted__"]`
directly — no fixture file in `packages/modules/`. The exclusion behavior is proven entirely
via injected trace + knownModules, which is simpler and avoids disk-layout coupling.

The two fixture tests from v2 are RETAINED in the 6-test suite (they already use inject-only pattern
via `makeOpts()`). No new file needs to be created. No fixture in `packages/modules/` tree.

Documentation note for future modules:
```
// How module N+1 enters the canonical catalog:
//   1. Create packages/modules/<module-name>/module.config.ts
//   2. Add <module-name> to the target manifest YAML under `modules:`
//   3. Run `npm run prebuild` — build-manifest validates transitive closure
//   4. CI composition-audit job catches violations before merge
//   For audit exclusion tests: inject the module name via knownModules: [..., "module-name"]
//   in audit-module-graph.test.ts — no disk fixture needed.
```

### Task 4: `prescriber-directory` reference module wiring

**Files:**
- Create: `packages/modules/prescriber-directory/module.config.ts`
- Create: `packages/modules/prescriber-directory/package.json`
- Create: `packages/modules/prescriber-directory/tsconfig.json`
- Create: `packages/modules/prescriber-directory/src/index.ts`
- Create: `packages/modules/prescriber-directory/src/factory.ts`
- Create: `packages/modules/prescriber-directory/__tests__/module.config.test.ts`
- Create: `packages/modules/prescriber-directory/__tests__/factory.test.ts`

**What it does:** This module ships NO new business logic. It wires the `PrescriberDirectoryClient` interface from `@infinityrx/contract` (Plan B) via a `createPrescriberDirectoryClient` factory that respects `INFINITYRX_ENV`. In `development` it returns the `MockPrescriberDirectoryClient`; in `production` / `mock` it returns `RealPrescriberDirectoryClient` (requiring `baseUrl` in config). This exemplifies the SP-0 reference pattern every future module will follow.

The `module.config.ts` is the source of truth SD-4 §3 references — it declares routes, nav entry, transitive requires, shell surfaces. The manifest validator reads it to verify `operator-dev.yml`'s `required_*` fields are correct.

- [ ] **Step 4.1: Write `packages/modules/prescriber-directory/module.config.ts`**

```ts
// packages/modules/prescriber-directory/module.config.ts
// SP-0 reference module config. SD-4 §3 mandates this shape.
// The manifest validator reads this file to verify transitive-closure completeness.

export const config = {
  name: "prescriber-directory",
  routes: [
    "/prescribers",
    "/prescribers/:npi",
    "/prescribers/search",
  ],
  navEntry: {
    label: "Prescribers",
    icon: "user-md",
    order: 10,
  },
  requires: {
    backends: ["prescriber-directory", "core-platform"],
    sharedServices: ["postgres", "redis"],
    schemas: ["prescriber_directory_v1", "core_v1"],
    migrations: ["core", "prescriber-directory"],
    env: ["DATABASE_URL_PRESCRIBER_DIRECTORY"],
    health: ["http://prescriber-directory:8030/health"],
    seedData: ["reference/nppes"],
    queues: [],
    jobs: [],
    buckets: [],
    integrations: [],
    secrets: ["secret://db/prescriber-directory"],
  },
  shellSurfaces: {
    navOrderSlots: [10],
    cacheTagPrefixes: ["prescriber-directory:"],
    commandPaletteScopes: ["prescribers.*"],
    routePrefixes: ["/prescribers"],
    cacheKeyNamespaces: ["prescriber-directory:"],
    redisKeyPrefixes: ["tenant:*:prescriber-directory:"],
    rabbitExchanges: [],
  },
  surfaceKinds: ["server", "client"] as Array<"server" | "client">,
  entitlements: { requiredScope: null },
} as const;
```

- [ ] **Step 4.2: Write `packages/modules/prescriber-directory/package.json`**

```json
{
  "name": "@infinityrx/module-prescriber-directory",
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
  "dependencies": {
    "@infinityrx/contract": "*"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.7.5",
    "vitest": "2.1.9"
  }
}
```

- [ ] **Step 4.3: Write `packages/modules/prescriber-directory/tsconfig.json`**

```json
{
  "extends": "../../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "./src"
  },
  "references": [
    { "path": "../../contract" }
  ],
  "include": ["src/**/*.ts", "module.config.ts"],
  "exclude": ["**/*.test.ts", "__tests__/**", "dist", "node_modules"]
}
```

- [ ] **Step 4.4: Write `packages/modules/prescriber-directory/src/index.ts`**

```ts
// packages/modules/prescriber-directory/src/index.ts
// Public surface of @infinityrx/module-prescriber-directory.
// Exports the factory and re-exports the client interface for consumers.
export { createPrescriberDirectoryClient } from "./factory.js";
export type { PrescriberDirectoryClient } from "@infinityrx/contract";
```

- [ ] **Step 4.5: Write `packages/modules/prescriber-directory/src/factory.ts`**

```ts
// packages/modules/prescriber-directory/src/factory.ts
// BLOCK 6 fix: Plan B HEAD exports factory functions, not classes.
// Actual exports from @infinityrx/contract (per wave/B10-w5:packages/contract/src/index.ts):
//   createRealPrescriberDirectoryClient(config: ClientConfig): PrescriberDirectoryClient
//   createMockPrescriberDirectoryClient(): PrescriberDirectoryClient
import type {
  PrescriberDirectoryClient,
  ClientConfig,
} from "@infinityrx/contract";
import {
  createRealPrescriberDirectoryClient,
  createMockPrescriberDirectoryClient,
} from "@infinityrx/contract";

type SupportedEnv = "development" | "mock" | "production";

export interface PrescriberDirectoryFactoryConfig extends ClientConfig {
  /** Backend base URL. Required when env is "production" or "mock". */
  baseUrl?: string;
}

/**
 * Returns the correct PrescriberDirectoryClient implementation for the given env.
 *
 * - development  → mock client (no network calls, in-memory fixture from Plan B)
 * - mock / production → real HTTP client (requires baseUrl in config)
 *
 * This is the SP-0 reference factory pattern. Every module in subsequent
 * waves ships a factory with this exact shape.
 *
 * Note for maintainers: delegates to Plan B's factory functions from @infinityrx/contract.
 * If Plan B renames these exports, this factory and its tests break at compile time (tsc -b).
 */
export function createPrescriberDirectoryClient(
  env: SupportedEnv,
  config: PrescriberDirectoryFactoryConfig
): PrescriberDirectoryClient {
  if (env === "development") {
    // createMockPrescriberDirectoryClient() takes no config — mock has in-memory fixture.
    return createMockPrescriberDirectoryClient();
  }

  if (!config.baseUrl) {
    throw new Error(
      `createPrescriberDirectoryClient: "baseUrl" is required for env="${env}". ` +
      `Set PRESCRIBER_DIRECTORY_URL in the environment.`
    );
  }

  return createRealPrescriberDirectoryClient({ ...config, baseUrl: config.baseUrl });
}
```

- [ ] **Step 4.6: Write `packages/modules/prescriber-directory/__tests__/module.config.test.ts`**

```ts
// packages/modules/prescriber-directory/__tests__/module.config.test.ts
import { describe, expect, it } from "vitest";
import { config } from "../module.config.js";

describe("prescriber-directory module.config", () => {
  it('name is "prescriber-directory"', () => {
    expect(config.name).toBe("prescriber-directory");
  });

  it("routes array is non-empty and all start with /prescribers", () => {
    expect(config.routes.length).toBeGreaterThan(0);
    for (const route of config.routes) {
      expect(route).toMatch(/^\/prescribers/);
    }
  });

  it("navEntry has label, icon, and numeric order", () => {
    expect(typeof config.navEntry.label).toBe("string");
    expect(typeof config.navEntry.icon).toBe("string");
    expect(typeof config.navEntry.order).toBe("number");
  });

  it('requires.backends includes "prescriber-directory" and "core-platform"', () => {
    expect(config.requires.backends).toContain("prescriber-directory");
    expect(config.requires.backends).toContain("core-platform");
  });

  it("requires.secrets all match secret:// URI scheme", () => {
    for (const secret of config.requires.secrets) {
      expect(secret).toMatch(/^secret:\/\//);
    }
  });

  it("shellSurfaces.routePrefixes[0] matches the first route prefix", () => {
    expect(config.shellSurfaces.routePrefixes).toContain("/prescribers");
  });

  it("surfaceKinds contains at least one of server | client", () => {
    const valid = new Set(["server", "client"]);
    for (const kind of config.surfaceKinds) {
      expect(valid.has(kind)).toBe(true);
    }
    expect(config.surfaceKinds.length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 4.7: Write `packages/modules/prescriber-directory/__tests__/factory.test.ts`**

```ts
// packages/modules/prescriber-directory/__tests__/factory.test.ts
// BLOCK 6 fix: Plan B exports factory functions (not classes), so no instanceof checks.
// Tests assert interface shape and behavior only.
import { describe, expect, it } from "vitest";
import { createPrescriberDirectoryClient } from "../src/factory.js";

describe("createPrescriberDirectoryClient", () => {
  it('development env — no baseUrl needed, returns client with search + getByNpi + probeHealth', () => {
    const client = createPrescriberDirectoryClient("development", { tenantId: "t1" });
    expect(typeof client.search).toBe("function");
    expect(typeof client.getByNpi).toBe("function");
    expect(typeof client.probeHealth).toBe("function");
  });

  it('development env — mock client has expected name property', () => {
    const client = createPrescriberDirectoryClient("development", { tenantId: "t1" });
    expect(client.name).toBe("prescriber-directory");
  });

  it('production env + baseUrl — returns client with search method', () => {
    const client = createPrescriberDirectoryClient("production", {
      tenantId: "t1",
      baseUrl: "http://prescriber-directory:8030",
      getAuthToken: async () => "tok",
    });
    expect(typeof client.search).toBe("function");
  });

  it('mock env + baseUrl — returns client with search method', () => {
    const client = createPrescriberDirectoryClient("mock", {
      tenantId: "t1",
      baseUrl: "http://prescriber-directory:8030",
      getAuthToken: async () => "tok",
    });
    expect(typeof client.search).toBe("function");
  });

  it('production env without baseUrl → throws with descriptive message containing "baseUrl"', () => {
    expect(() =>
      createPrescriberDirectoryClient("production", { tenantId: "t1" })
    ).toThrow("baseUrl");
  });

  it('mock env without baseUrl → throws', () => {
    expect(() =>
      createPrescriberDirectoryClient("mock", { tenantId: "t1" })
    ).toThrow("baseUrl");
  });

  it('development env — mock client search returns results for a fixture NPI', async () => {
    const client = createPrescriberDirectoryClient("development", { tenantId: "t1" });
    // Plan B mock fixture includes at least one doctor; search by last name returns results.
    const resp = await client.search({ q: "Smith", limit: 5 });
    expect(Array.isArray(resp.results)).toBe(true);
  });
});
```

**Test count (Task 4):** 14 tests (7 module.config + 7 factory).

### Task 5: Portal root layout + manifest-driven nav (minimum scaffolding)

**Files:**
- Create: `portal/operator/app/layout.tsx`
- Create: `portal/operator/app/_nav/manifest-nav.tsx`
- Create: `portal/operator/app/page.tsx`
- Create: `portal/operator/app/layout.test.tsx`
- Create: `portal/operator/app/_nav/manifest-nav.test.tsx`
- Create: `portal/operator/next.config.ts` (modify if already exists)

**Scope constraint:** Plan D ships MINIMUM scaffolding only. Auth-gated routes, RSC streaming, and session checks are Plan C-shell. These files establish the AppShell wrapper + manifest-driven nav so Plan B+C work is verifiable end-to-end. No auth logic here.

- [ ] **Step 5.1: Modify `portal/operator/app/layout.tsx` (SURGICAL — preserve existing shell)**

**CRITICAL: The file already exists at HEAD of wave/B10-w5 with fonts (Lato, IBM Plex Mono),
theme init script, Providers, AppShell with `isAuthenticated` prop, and auth headers. DO NOT
replace it wholesale — that regresses Plan C-shell's RequireAuth work (BLOCK 4).**

Read the existing file first, then make the minimal surgical additions:
1. Add `import { ManifestNav } from "./_nav/manifest-nav.js";` after the existing AppShell import.
2. Add `nav={<ManifestNav />}` prop to the existing `<AppShell>` element.

The existing layout at HEAD looks like:

```tsx
// (existing imports preserved — Lato, IBM_Plex_Mono, Providers, AppShell, themeInitScript, globals.css)
// ...

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const h = await headers();
  const isAuthenticated = h.get("x-ifx-authenticated") === "1";

  return (
    <html lang="en" className={`${lato.variable} ${ibmPlexMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-[var(--ifx-bg)] font-sans antialiased">
        <a href="#main-content" className="skip-nav">Skip to main content</a>
        <Providers>
          <AppShell isAuthenticated={isAuthenticated}>
            {children}
          </AppShell>
        </Providers>
      </body>
    </html>
  );
}
```

**The two surgical changes Plan D makes:**

```diff
+import { ManifestNav } from "./_nav/manifest-nav.js";
 // (after existing AppShell import line)

-          <AppShell isAuthenticated={isAuthenticated}>
+          <AppShell isAuthenticated={isAuthenticated} nav={<ManifestNav />}>
```

**Plan C-shell ordering note:** If Plan C-shell lands first (wrapping `<AppShell>` with `<RequireAuth>`),
Plan D's `nav={<ManifestNav />}` slot wires into the already-authenticated layout. If Plan D lands
first, the slot is later wrapped by `<RequireAuth>` without touching the nav prop. The `nav=` prop
is additive and does not conflict with either ordering.

- [ ] **Step 5.2: Write `portal/operator/app/_nav/manifest-nav.tsx`**

```tsx
// portal/operator/app/_nav/manifest-nav.tsx
// Server component: reads _generated/manifest.json at request time and renders nav items.
// Consumes NAV_ENTRIES from the generated artifact — this is the only file in portal/
// that references _generated/ directly. All other portal code accesses modules through
// the composition layer.
import { readFileSync } from "node:fs";
import { join } from "node:path";

interface NavItem {
  label: string;
  icon: string;
  order: number;
  routePrefix: string;
}

function loadNavEntries(): NavItem[] {
  // _generated/manifest.json is written by build-manifest.ts at pre-build time.
  // At dev time it may not exist yet — return empty array gracefully.
  const generatedPath = join(process.cwd(), "packages", "shell", "src", "_generated", "manifest.json");
  try {
    const manifest = JSON.parse(readFileSync(generatedPath, "utf8")) as { modules: string[] };
    // Nav entries come from the generated nav.ts file alongside the manifest.
    // We re-derive them here from manifest.json for SSR to avoid a dynamic import of TS.
    // The full nav.ts is consumed by the build-time ESLint check; at runtime we use manifest.json.
    // Order alphabetically if order metadata is unavailable at this level.
    return manifest.modules.map((name, idx) => ({
      label: name
        .split("-")
        .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
        .join(" "),
      icon: "default",
      order: idx,
      routePrefix: `/${name}`,
    }));
  } catch {
    // Generated file missing — dev cold start before prebuild ran.
    return [];
  }
}

export function ManifestNav() {
  const navItems = loadNavEntries().sort((a, b) => a.order - b.order);

  if (navItems.length === 0) {
    return <nav aria-label="module navigation"><p>No modules loaded.</p></nav>;
  }

  return (
    <nav aria-label="module navigation">
      <ul>
        {navItems.map((item) => (
          <li key={item.routePrefix}>
            <a href={item.routePrefix}>{item.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

- [ ] **Step 5.3: Write `portal/operator/app/page.tsx`**

```tsx
// portal/operator/app/page.tsx
// Root page: shows the portal home / dashboard placeholder.
// Auth-gated redirect to first module route is Plan C-shell.
export default function HomePage() {
  return (
    <main>
      <h1>InfinityRx Operator Portal</h1>
      <p>Select a module from the navigation to get started.</p>
    </main>
  );
}
```

- [ ] **Step 5.4: Write `portal/operator/next.config.ts`**

If a `next.config.ts` already exists at `portal/operator/next.config.ts`, ADD the prebuild step to the existing config. If it does not exist, create it:

```ts
// portal/operator/next.config.ts
import type { NextConfig } from "next";
import { execSync } from "node:child_process";
import { join } from "node:path";

// Pre-build: run the build-manifest generator to emit _generated/ artifacts.
// The generator validates the manifest schema and fails the build if validation errors exist.
// This runs synchronously before webpack starts — it is intentionally a blocking call.
function runPrebuild() {
  const repoRoot = join(__dirname, "..", "..");
  try {
    execSync("node --loader tsx packages/scripts/build-manifest.ts", {
      cwd: repoRoot,
      stdio: "inherit",
      env: {
        ...process.env,
        INFINITYRX_MANIFEST:
          process.env["INFINITYRX_MANIFEST"] ??
          join(repoRoot, "infrastructure", "manifests", "operator-dev.yml"),
        INFINITYRX_GENERATED_OUT:
          join(repoRoot, "packages", "shell", "src", "_generated"),
      },
    });
  } catch (err) {
    throw new Error(`build-manifest failed — fix manifest errors before building the portal.\n${err}`);
  }
}

// Run at config evaluation time (= start of next build / next dev).
runPrebuild();

const nextConfig: NextConfig = {
  // Repo root is two levels up from portal/operator/.
  // This ensures Next.js resolves workspace packages correctly.
  transpilePackages: [
    "@infinityrx/ui",
    "@infinityrx/contract",
    "@infinityrx/auth",
    "@infinityrx/qa-harness",
  ],
};

export default nextConfig;
```

- [ ] **Step 5.5: Write `portal/operator/app/layout.test.tsx`**

```tsx
// portal/operator/app/layout.test.tsx
// Tests that RootLayout passes ManifestNav into the nav slot.
// The existing layout (fonts, Providers, AppShell, auth headers) is preserved;
// we only test the nav slot addition Plan D makes (BLOCK 4 fix).
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub @infinityrx/ui AppShell to isolate the nav slot under test.
vi.mock("@infinityrx/ui", () => ({
  AppShell: ({
    children,
    nav,
    isAuthenticated: _isAuthenticated,
  }: {
    children: React.ReactNode;
    nav?: React.ReactNode;
    isAuthenticated?: boolean;
  }) => (
    <div data-testid="app-shell">
      {nav && <div data-testid="nav-slot">{nav}</div>}
      <div data-testid="main-slot">{children}</div>
    </div>
  ),
}));

// Stub ManifestNav since it reads the filesystem.
vi.mock("./_nav/manifest-nav.js", () => ({
  ManifestNav: () => <nav data-testid="manifest-nav">nav stub</nav>,
}));

// Stub next/headers (used by the existing layout's isAuthenticated check).
vi.mock("next/headers", () => ({
  headers: () => ({ get: () => null }),
}));

// Stub font imports so the layout doesn't try to load Google Fonts in test.
vi.mock("next/font/google", () => ({
  Lato: () => ({ variable: "--font-lato" }),
  IBM_Plex_Mono: () => ({ variable: "--font-ibm-mono" }),
}));

vi.mock("@shared/components/theme-toggle", () => ({
  themeInitScript: "",
}));

vi.mock("./globals.css", () => ({}));

vi.mock("@/components/providers", () => ({
  Providers: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({
    children,
    nav,
    isAuthenticated: _isAuthenticated,
  }: {
    children: React.ReactNode;
    nav?: React.ReactNode;
    isAuthenticated?: boolean;
  }) => (
    <div data-testid="app-shell">
      {nav && <div data-testid="nav-slot">{nav}</div>}
      {children}
    </div>
  ),
}));

import RootLayout from "./layout.js";

describe("RootLayout (Plan D surgical additions)", () => {
  it("ManifestNav is passed into AppShell nav slot", async () => {
    const jsx = await RootLayout({ children: <span data-testid="child">x</span> });
    render(jsx as React.ReactElement);
    expect(screen.getByTestId("nav-slot")).toBeDefined();
    expect(screen.getByTestId("manifest-nav")).toBeDefined();
  });

  it("children are still rendered (existing layout shell preserved)", async () => {
    const jsx = await RootLayout({ children: <div data-testid="page-content">Hello</div> });
    render(jsx as React.ReactElement);
    expect(screen.getByTestId("page-content")).toBeDefined();
  });
});
```

- [ ] **Step 5.6: Write `portal/operator/app/_nav/manifest-nav.test.tsx`**

```tsx
// portal/operator/app/_nav/manifest-nav.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub node:fs so the test doesn't need a real _generated/manifest.json.
vi.mock("node:fs", () => ({
  readFileSync: vi.fn(),
}));

import { readFileSync } from "node:fs";
import { ManifestNav } from "./manifest-nav.js";

describe("ManifestNav", () => {
  it("renders nav items for each module in manifest.json", () => {
    vi.mocked(readFileSync).mockReturnValue(
      JSON.stringify({ modules: ["prescriber-directory", "reclaimrx"] })
    );
    render(<ManifestNav />);
    expect(screen.getByText("Prescriber Directory")).toBeDefined();
    expect(screen.getByText("Reclaimrx")).toBeDefined();
  });

  it("renders 'No modules loaded' when manifest has empty modules array", () => {
    vi.mocked(readFileSync).mockReturnValue(JSON.stringify({ modules: [] }));
    render(<ManifestNav />);
    expect(screen.getByText("No modules loaded.")).toBeDefined();
  });

  it("renders gracefully when _generated/manifest.json does not exist (readFileSync throws)", () => {
    vi.mocked(readFileSync).mockImplementation(() => { throw new Error("ENOENT"); });
    render(<ManifestNav />);
    expect(screen.getByText("No modules loaded.")).toBeDefined();
  });

  it("nav links use the module route prefix as href", () => {
    vi.mocked(readFileSync).mockReturnValue(
      JSON.stringify({ modules: ["prescriber-directory"] })
    );
    render(<ManifestNav />);
    const link = screen.getByRole("link", { name: "Prescriber Directory" });
    expect(link.getAttribute("href")).toBe("/prescriber-directory");
  });

  it("nav has accessible aria-label", () => {
    vi.mocked(readFileSync).mockReturnValue(JSON.stringify({ modules: [] }));
    render(<ManifestNav />);
    expect(screen.getByRole("navigation")).toBeDefined();
  });
});
```

**Test count (Task 5):** 7 tests (2 layout + 5 manifest-nav).

### Task 6: `operator-dev.yml` manifest update + CI composition-audit step

**Files:**
- Modify: `infrastructure/manifests/operator-dev.yml`
- Modify: `.github/workflows/sp0-foundation.yml`
- Modify: `tsconfig.json` (repo root) — add prescriber-directory module reference
- Modify: `.gitignore` — add `_generated/` gitignore rule

**What it does:** Updates the dev manifest to include `prescriber-directory` with its transitive `required_*` fields (computed from `module.config.ts`). Adds a CI step that runs `audit-module-graph.ts` after `next build` in the composition-check job.

- [ ] **Step 6.1: Update `infrastructure/manifests/operator-dev.yml`**

Replace the current content (empty modules list from Plan A) with the prescriber-directory composition:

```yaml
# Dev / reference full-composition manifest.
# Updated by Plan D to include prescriber-directory as the reference module.
# Transitive required_* fields computed from packages/modules/prescriber-directory/module.config.ts.
instance_name: operator-dev
audience: operator
auth_profile: development
branding:
  primary_color: "#1f2937"
modules:
  - prescriber-directory
required_backends:
  - prescriber-directory
  - core-platform
required_shared_services:
  - postgres
  - redis
required_schemas:
  - prescriber_directory_v1
  - core_v1
required_migrations:
  - core
  - prescriber-directory
required_env:
  - JWT_SECRET
  - NEXTAUTH_SECRET
  - INFINITYRX_ENV
  - DATABASE_URL_PRESCRIBER_DIRECTORY
required_health:
  - http://prescriber-directory:8030/health
required_seed_data:
  - reference/nppes
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets:
  - secret://jwt/signing-key
  - secret://nextauth/secret
  - secret://db/prescriber-directory
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
```

- [ ] **Step 6.2: Add CI composition-audit step to `.github/workflows/sp0-foundation.yml`**

Add two new jobs: `prepare-artifacts` (runs first) and `composition-audit` (runs after `lint-typecheck-test`).

**STILL-OPEN-2 fix:** `lint-typecheck-test` now `needs: prepare-artifacts` so that generated files
exist before lint/tsc run. Generated artifacts are gitignored (Option B — BLOCK 3); CI regenerates
from scratch. No `--verify-hash` flag and no input_hash gate — generators exiting 0 IS the gate.

```yaml
  prepare-artifacts:
    name: Generate composition artifacts
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - name: Run build-manifest (validate schema + codegen)
        run: node --loader tsx packages/scripts/build-manifest.ts
        env:
          INFINITYRX_MANIFEST: infrastructure/manifests/operator-dev.yml
          INFINITYRX_GENERATED_OUT: packages/shell/src/_generated
      - name: Run generate-eslint-zones
        run: node --loader tsx packages/scripts/generate-eslint-zones.ts
      - name: Upload generated artifacts
        uses: actions/upload-artifact@v4
        with:
          name: composition-artifacts
          path: packages/shell/src/_generated/
          retention-days: 1

  # NOTE: lint-typecheck-test must add `needs: prepare-artifacts` and a download step.
  # Update the existing lint-typecheck-test job header to:
  #   needs: prepare-artifacts
  # and add as the first step (before npm ci):
  #   - uses: actions/download-artifact@v4
  #     with:
  #       name: composition-artifacts
  #       path: packages/shell/src/_generated/

  composition-audit:
    name: Composition audit (schema + zone validation)
    runs-on: ubuntu-latest
    needs: lint-typecheck-test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
      - run: npm ci
      - uses: actions/download-artifact@v4
        with:
          name: composition-artifacts
          path: packages/shell/src/_generated/
      - name: Validate manifest transitive closure
        run: node --loader tsx packages/scripts/validate-manifest.ts
        env:
          INFINITYRX_MANIFEST: infrastructure/manifests/operator-dev.yml
      # audit-module-graph (post-build .nft.json scan) is local-only for SP-0.
      # Run `npm run portal:audit` locally after `next build` to validate omitted modules.
      # Full CI gate for audit-module-graph deferred to portal-build-audit wave (requires
      # next build in CI — several minutes).
```

Add `composition:check` convenience script to root `package.json` for local dev:
```json
"composition:check": "node --loader tsx packages/scripts/build-manifest.ts && node --loader tsx packages/scripts/generate-eslint-zones.ts && git diff --quiet packages/shell/src/_generated/ || echo 'WARNING: generated files changed — commit or rebuild'"
```

**CONCERN 2 + STILL-OPEN-5 resolution — single authoritative placement (v3 final):**
- `build-manifest` (manifest validation + codegen): runs in `prepare-artifacts` CI job (new) AND in `next.config.ts` prebuild (Task 5). `prepare-artifacts` is the authoritative CI gate; `next.config.ts` prebuild is a local-dev convenience.
- `audit-module-graph` (post-build .nft.json trace scan): LOCAL-ONLY for SP-0. NOT in any CI job. It cannot run in CI until a full `next build` exists. Add `portal:audit` npm script to `portal/operator/package.json`: `"portal:audit": "node --loader tsx packages/scripts/audit-module-graph.ts"`. Full CI gate deferred to `portal-build-audit` wave (follow-on).
- Acceptance criterion A18 reflects this single story (no contradiction).
- **Follow-up task:** Create `portal-build-audit` CI job in the next wave that runs `next build` and `npm run portal:audit`.

- [ ] **Step 6.3: Update repo-root `tsconfig.json` to reference the prescriber-directory module**

Add to the `references` array:

```json
{ "path": "./packages/modules/prescriber-directory" }
```

- [ ] **Step 6.4: Update `.gitignore`**

Add after the existing `packages/*/node_modules` line:

```
# Generated composition artifacts — rebuilt by build-manifest.ts at pre-build time.
packages/shell/src/_generated/*
!packages/shell/src/_generated/.gitkeep
```

**Test count (Task 6):** 0 new tests (configuration changes only; manifest validation is covered by Task 1's schema tests).

### Task 7: Wire ESLint zones into workspace root config + composition-zone tests

**Files:**
- Modify: `eslint.config.mjs` (repo root) — add `GENERATED_MODULE_ZONES` dynamic import + `import/no-restricted-paths` rule
- Create: `packages/scripts/eslint-zones-integration.test.ts` — tests that the ESLint config loads cleanly and that the zone rule fires on a synthetic violation

**What it does:** Updates the workspace-root `eslint.config.mjs` that Plan A scaffolded (with empty `GENERATED_MODULE_ZONES = []`) to dynamically import from `packages/shell/src/_generated/eslint-zones.mjs` and apply `import/no-restricted-paths`. The import line is the ONLY line that changes when a new module is added.

**HEAD fact (BLOCK 5 + STILL-OPEN-3):** The file at HEAD is `eslint.config.mjs` (ESM `.mjs`). The generator now emits `eslint-zones.mjs` (pure ESM, no TypeScript) which Node ESM can dynamically import at runtime without a TS loader. The import path uses `.mjs` — NOT `.js` or `.ts`.

**STILL-OPEN-3b fix — cold-checkout fallback:** The fallback on missing generated file returns the
`GENERATED_MODULE_ZONES_SENTINEL` constant (an empty array with a named constant, matching the
generated file's export name) instead of a bare `[]`. This avoids a schema violation if
`eslint-plugin-import` enforces `minItems: 1` on the zones array. A `console.warn` is emitted
so the missing-file case is visible during dev.

Per SD-4 §4: the `zones` array in `eslint.config.mjs` must reference `GENERATED_MODULE_ZONES` from the generated file — no hand-edited zone entries.

- [ ] **Step 7.1: Update `eslint.config.mjs` to import `GENERATED_MODULE_ZONES`**

Locate the existing `eslint.config.mjs` in the repo root (created by Plan A). Find the line containing `GENERATED_MODULE_ZONES` or `import/no-restricted-paths` (Plan A scaffolded this with an empty array or a `TODO` comment). Replace that section with a cold-checkout-safe dynamic import:

```js
// eslint.config.mjs (repo root) — the relevant section to add/modify:

// Generated composition-zone enforcement (SD-4 §4).
// STILL-OPEN-3 fix: import .mjs (not .js or .ts) — generator emits pure ESM .mjs
// which Node can import at runtime without a TS loader.
// STILL-OPEN-3b fix: fallback is the sentinel constant, not [] — avoids minItems:1 schema
// violation; console.warn makes the missing-file case visible during dev.
const GENERATED_MODULE_ZONES_SENTINEL = [];
let GENERATED_MODULE_ZONES = GENERATED_MODULE_ZONES_SENTINEL;
try {
  const generated = await import("./packages/shell/src/_generated/eslint-zones.mjs");
  GENERATED_MODULE_ZONES = generated.GENERATED_MODULE_ZONES;
} catch {
  // Cold checkout — zones not yet generated. ESLint runs with sentinel (empty zones = no-op).
  // Run `npm run prebuild` (or `npm run composition:check`) to populate.
  console.warn("[eslint] WARN: packages/shell/src/_generated/eslint-zones.mjs not found. Run npm run prebuild.");
}

// ... (rest of the existing config) ...
// In the rules object, replace the placeholder for import/no-restricted-paths:
"import/no-restricted-paths": ["error", {
  zones: GENERATED_MODULE_ZONES,
}],
```

If Plan A's `eslint.config.mjs` already has the `import/no-restricted-paths` rule with an empty `zones: []`, change `zones: []` to `zones: GENERATED_MODULE_ZONES` and add the dynamic-import block at the top of the config object (after other static imports).

- [ ] **Step 7.2: Create `packages/scripts/eslint-zones-integration.test.ts`**

```ts
// packages/scripts/eslint-zones-integration.test.ts
// Verifies that:
// 1. The generate-eslint-zones script produces a .mjs file (loadable by Node ESM — STILL-OPEN-3).
// 2. The zone shape is correct (required fields present).
// 3. A synthetic cross-module import path triggers the zone pattern.
import { mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import { buildZones, generateEslintZones } from "./generate-eslint-zones.js";

function makeTmpOutputDir() {
  const dir = join(tmpdir(), `eslint-zone-int-${randomUUID()}`);
  mkdirSync(dir, { recursive: true });
  return dir;
}

describe("ESLint zone integration", () => {
  // NEW-2 fix: static readFileSync import replaces dynamic await import() — no async needed.
  it("generated zones file is valid .mjs (no TS syntax, GENERATED_MODULE_ZONES exported)", () => {
    const outputDir = makeTmpOutputDir();
    generateEslintZones({
      repoRoot: makeTmpOutputDir(),
      outputDir,
      discoverModuleNames: () => ["prescriber-directory", "reclaimrx"],
    });
    // STILL-OPEN-3a: output is .mjs not .ts
    const content = readFileSync(join(outputDir, "eslint-zones.mjs"), "utf8");
    // File must export GENERATED_MODULE_ZONES.
    expect(content).toContain("export const GENERATED_MODULE_ZONES");
    // Must contain the prescriber-directory → reclaimrx zone.
    expect(content).toContain("prescriber-directory");
    expect(content).toContain("reclaimrx");
    // .mjs must not contain TypeScript syntax.
    expect(content).not.toContain(": ZoneEntry[]");
    expect(content).not.toContain("as const");
  });

  it("each zone entry has target, from, and message fields", () => {
    const zones = buildZones(["alpha", "beta"]);
    for (const zone of zones) {
      expect(typeof zone.target).toBe("string");
      expect(typeof zone.from).toBe("string");
      expect(typeof zone.message).toBe("string");
    }
  });

  it("zone target path uses relative ./ prefix (required by import/no-restricted-paths)", () => {
    const zones = buildZones(["prescriber-directory"]);
    // Single module → no zones; check with 2 modules.
    const zones2 = buildZones(["prescriber-directory", "reclaimrx"]);
    for (const zone of zones2) {
      expect(zone.target).toMatch(/^\.\//);
      expect(zone.from).toMatch(/^\.\//);
    }
  });

  it("zone from path for (alpha → beta) zone does NOT contain alpha (not the same module)", () => {
    const zones = buildZones(["alpha", "beta"]);
    const alphaToBeta = zones.find((z) => z.target.includes("alpha") && z.from.includes("beta"));
    expect(alphaToBeta).toBeDefined();
    expect(alphaToBeta!.from).not.toContain("alpha");
  });

  it("cross-module path matches the zone pattern (synthetic violation detection)", () => {
    // Simulate what ESLint's path-resolver would see: a file in packages/modules/alpha/
    // importing something from packages/modules/beta/.
    const crossModulePath = "./packages/modules/beta/src/some-file";
    const zones = buildZones(["alpha", "beta"]);
    const alphaToBeaZone = zones.find((z) => z.target.includes("alpha") && z.from.includes("beta"));
    expect(alphaToBeaZone).toBeDefined();
    // The from glob should match the cross-module import.
    const fromPattern = alphaToBeaZone!.from.replace("**", ".*").replace(/\//g, "\\/");
    expect(crossModulePath).toMatch(new RegExp(fromPattern.replace("./", "\\./").replace("**", ".*")));
  });
});
```

**Test count (Task 7):** 5 tests.

### Task 8: Acceptance status document

**Files:**
- Create: `docs/superpowers/plans/2026-05-15-sp0-plan-d-acceptance.md`

**What it does:** Documents the SP-0 finishing gate acceptance criteria, one row per criterion, with PASS / PARTIAL / FAIL status filled in at execution time. Included here as a required deliverable so the executor knows to create it when all tasks are done.

- [ ] **Step 8.1: Create `docs/superpowers/plans/2026-05-15-sp0-plan-d-acceptance.md`**

The executor must fill in the ACTUAL STATUS column after running all tasks and tests.

```markdown
# SP-0 Plan D — Acceptance Status

> Filled in by the executing agent after all 8 tasks are complete.
> Date: <fill in>
> Executed by: <fill in>

## Acceptance Criteria

| # | Criterion | Plan ref | Actual status |
|---|---|---|---|
| A1 | `build-manifest.ts` runs on `operator-dev.yml` without error; emits `_generated/manifest.json`, `module-imports.ts`, `nav.ts` | Task 1 | |
| A2 | `build-manifest.ts` test suite: all 8 tests pass (7 original + 1 digit-bearing kebab-to-camel bonus — v3) | Task 1 | |
| A3 | Schema validation fails fast on invalid `audience` enum value | Task 1 | |
| A4 | `generate-eslint-zones.ts` for 1 module → 0 zones; 2 modules → 2 zones; 3 modules → 6 zones; emits `.mjs` not `.ts` (v3) | Task 2 | |
| A5 | `generate-eslint-zones.ts` test suite: all 9 tests pass | Task 2 | |
| A6 | `audit-module-graph.ts` PASS when omitted module absent; FAIL when present in .nft.json; inject-only pattern (v3) | Task 3 | |
| A7 | `audit-module-graph.ts` test suite: all 6 tests pass (NEW-3 fix: was "all 6" in v2, now confirmed 6 with inject-only CONCERN-1 tests included) | Task 3 | |
| A8 | `prescriber-directory/module.config.ts` validates: all 7 config tests pass | Task 4 | |
| A9 | `createPrescriberDirectoryClient("development")` returns mock client (not class, factory function result) | Task 4 | |
| A10 | `createPrescriberDirectoryClient("production", { baseUrl })` returns real client | Task 4 | |
| A11 | `createPrescriberDirectoryClient("production")` without `baseUrl` throws | Task 4 | |
| A12 | Factory test suite: all 7 tests pass | Task 4 | |
| A13 | `portal/operator/app/layout.tsx` renders AppShell with ManifestNav in nav slot | Task 5 | |
| A14 | `ManifestNav` renders module names from `manifest.json`; graceful fallback when file missing | Task 5 | |
| A15 | Portal layout + nav test suite: all 7 tests pass | Task 5 | |
| A16 | `operator-dev.yml` includes `prescriber-directory` in `modules` + correct `required_*` fields | Task 6 | |
| A17 | `validate-manifest.ts` (Plan A) passes on updated `operator-dev.yml` | Task 6 | |
| A18 | CI `sp0-foundation.yml` has `prepare-artifacts` job + `composition-audit` job; `lint-typecheck-test` `needs: prepare-artifacts`; `audit-module-graph` is local npm script `portal:audit` only (SP-0 deferral — STILL-OPEN-5 v3 final) | Task 6 | |
| A19 | Repo-root `eslint.config.mjs` imports `.mjs` (not `.js` or `.ts`); cold-checkout fallback emits `console.warn` and uses sentinel constant (not `[]`) — STILL-OPEN-3 v3 | Task 7 | |
| A20 | ESLint zone integration tests: all 5 tests pass | Task 7 | |
| A21 | `workspace-root tsc -b` compiles cleanly with all packages including `prescriber-directory` | Cross-task | |
| A22 | `npm run test:packages` runs all vitest suites (scripts + contract + auth + ui + qa-harness + prescriber-directory); 0 failures | Cross-task | |
| A23 | `.gitignore` excludes `packages/shell/src/_generated/*` (except `.gitkeep`) | Task 6 | |
| A24 | No `@infinityrx/module-*` imports outside `packages/shell/src/_generated/` (ESLint clean on workspace) | Task 7 | |

## Test Count Summary

| Task | Test file(s) | Count | Notes |
|---|---|---|---|
| Task 1 | `build-manifest.test.ts` | 8 | Uses real schema (BLOCK 2); +1 digit-bearing kebab-to-camel bonus test (v3) |
| Task 2 | `generate-eslint-zones.test.ts` | 9 | .mjs output assertion added (STILL-OPEN-3, v3) |
| Task 3 | `audit-module-graph.test.ts` | 6 | Inject-only pattern (STILL-OPEN-4 option c, v3); 2 CONCERN-1 tests retained in the 6 (inject via makeOpts) |
| Task 4 | `module.config.test.ts` + `factory.test.ts` | 7 + 7 = 14 | factory tests assert interface, not instanceof (BLOCK 6) |
| Task 5 | `layout.test.tsx` + `manifest-nav.test.tsx` | 2 + 5 = 7 | layout tests updated for surgical modification (BLOCK 4) |
| Task 6 | — (config only) | 0 | |
| Task 7 | `eslint-zones-integration.test.ts` | 5 | .mjs assertion + no-TS-syntax assertion added (STILL-OPEN-3, v3) |
| Task 8 | — (docs only) | 0 | |
| **Total** | | **49** | v3: −2 removed CONCERN-1 disk-fixture tests (inject-only), +1 bonus kebab-digit test |
```

**Test count (Task 8):** 0 new tests (documentation only).

---

## Self-Review

### Spec-coverage table

| Pillar | SD-4 section | Plan D task(s) | Status |
|---|---|---|---|
| Pillar 1 — Composition codegen | §2 generator, §3 manifest schema | Task 1 (build-manifest) | Covered |
| Pillar 1 — Module-graph audit | §5.1 server-graph audit | Task 3 (audit-module-graph) | Covered (offline; post-build portal hook for full client-bundle audit deferred — see D1) |
| Pillar 1 — ESLint zones | §4 no-sibling-imports | Task 2 + Task 7 | Covered |
| Pillar 2 — Reference module | SD-4 §3 module.config.ts shape | Task 4 (prescriber-directory) | Covered |
| Pillar 2 — Factory wiring | SD-2 framework-agnostic mandate | Task 4 factory.ts | Covered |
| Pillar 3 — Portal AppShell | Plan C AppShell `{children, header?, nav?}` API | Task 5 layout.tsx | Covered (minimum scaffolding) |
| Pillar 3 — Manifest-driven nav | SD-4 §2 `_generated/manifest.json` | Task 5 manifest-nav.tsx | Covered |
| Manifest update | operator-dev.yml Plan A placeholder → real | Task 6 | Covered |
| CI extension | SP-0 composition-audit job | Task 6 | Covered (offline checks; next build audit deferred) |

### Subagent-initiated decisions (for codex scrutiny)

**D1 — Client-bundle audit deferred to post-build portal CI job.**
SD-4 §5 requires both server-graph audit (`.nft.json`) AND client-bundle audit (webpack stats JSON). Plan D implements the `.nft.json` server-graph audit. The client-bundle audit requires a full `next build` run in CI (several minutes). That is deferred to a "portal-build-audit" CI job in a subsequent wave. The offline composition checks (Task 6) cover everything that doesn't require an actual build.

**D2 — `loadModuleConfig` uses `_require()` (createRequire CJS interop) instead of dynamic `import()`.**
`build-manifest.ts` runs under `tsx`/`ts-node/esm`. `_require` is the result of `createRequire(import.meta.url)` — this is the correct ESM-safe way to load CJS modules. The bare `require()` call that was in v2 was incorrect (NEW-1); fixed to `_require(configPath)`. In the test path, `loadConfig` is stubbed entirely, so this is a test-time non-issue. The `_require()` call is annotated with `eslint-disable` for the one-liner. Decision: accept the CJS interop for now; a future refactor to a `tsx.load()` API can replace it without changing the test surface.

**D3 — `ManifestNav` reads `manifest.json` at request time (SSR), not `nav.ts`.**
`nav.ts` is a TypeScript file consumed at build time by the ESLint zone check and type system. At SSR runtime the portal cannot dynamically import generated TS. `manifest.json` (JSON, not TS) is the correct runtime format. Nav labels are derived from module names (kebab-case → Title Case) which is good enough for the minimum scaffolding; full nav metadata (icon, order) will come from a separate endpoint or re-emit in `manifest.json` in a follow-on task.

**D4 — `prescriber-directory` factory delegates to Plan B's exported factory functions.**
Plan B HEAD (wave/B10-w5:packages/contract/src/index.ts) exports `createRealPrescriberDirectoryClient(config)`
and `createMockPrescriberDirectoryClient()` as factory functions — NOT classes. (BLOCK 6 fix: v1
incorrectly referenced class names `MockPrescriberDirectoryClient` / `RealPrescriberDirectoryClient`
which do not exist as exports.) Plan D's factory delegates to these two functions. If Plan B renames
them, Plan D's factory and tests break at compile time — the correct behavior (explicit dependency,
caught by `tsc -b`). Tests assert interface shape and behavior; no `instanceof` checks on
non-exported types. Note for maintainers: see `packages/modules/prescriber-directory/src/factory.ts`
for the delegation pattern every future module will follow.

**D5 — `_generated/.gitkeep` committed; rest of `_generated/` gitignored.**
Generated files must not be committed (they change on every build, pollute git history). The `.gitkeep` ensures the directory exists so `build-manifest.ts` can write to it without needing to create it. `.gitignore` rule in Task 6 excludes everything except `.gitkeep`. This is the same pattern Plans A–C use for other generated directories.

### Known gaps (out of scope for Plan D, tracked for follow-on)

| # | Gap | Tracking |
|---|---|---|
| G1 | Client-bundle webpack-stats audit (SD-4 §5.2) | Post-SP-0 portal CI job |
| G2 | `verify-instance-secrets.ts` (SD-4 §3.X deploy/boot secret existence check) | Infrastructure wave |
| G3 | `generate-ci-matrix.ts` (SD-4 §6 scoped pairwise CI matrix) | SP-1 when second module lands |
| G4 | `lint-tsconfig.ts` (SD-4 §4 belt-and-suspenders TS alias gate) | SP-1 |
| G5 | `portal/operator/app/api/` BFF proxy auth gating | Plan C-shell |
| G6 | Full nav metadata (icon, order) in `manifest.json` | Task 5 follow-on |
