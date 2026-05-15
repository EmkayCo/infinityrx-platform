# SP-0 Plan A — Foundation Scaffolding Implementation Plan

> **Status:** v2, 2026-05-15. v1 (`4b41f4e`) failed codex review with 4 BLOCKs + 3 CONCERNs + 2 NITs. v2 closes them:
> - Validator Ajv imports fixed to ESM-correct shape (`new Ajv2020(...)`, `addFormats(ajv)` — no `.default`).
> - Validator CLI entrypoint check switched to `pathToFileURL(process.argv[1]).href === import.meta.url` so Windows paths with spaces match.
> - Root `npm run lint` now COMPOSES `lint:root` + `lint:portal-operator` — root ESLint does NOT silently subsume the existing operator config.
> - Root `no-restricted-imports` framework-ban scoped to `packages/**`, `portal/shared/**`, `packages/scripts/**` only (not `portal/operator/**` where `next/*` is allowed).
> - TS tooling moved from top-level `scripts/` (which is already the Python-loaders directory) to `packages/scripts/` — no more mixed-language workspace directory.
> - Validator gains 2 new tests for malformed `secret-catalog.yml` / `integrations.yml` shapes; validator code adds `Array.isArray` guards.
> - ESLint-config load-verification step added (proves `import/no-restricted-paths` with empty zones is a no-op, not a config error).
> - Self-review D11 reworded to PARTIAL (config guardrails only).
> - Lockfile-authority model documented in Task 1.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the SP-0 monorepo structure (`packages/*` workspaces), strict-mode YAML deployment-manifest schema, manifest-validator script, baseline workspace-root TypeScript + ESLint config, and CI shell — all green and committed, with no implementation code yet. Subsequent plans (B/C/D) layer the actual packages on top.

**Architecture:** Adds `packages/` as a new npm-workspaces root alongside existing `portal/operator` + `portal/shared`. New top-level dirs: `packages/` (workspace, including the new `packages/scripts/` for TS tooling — leaves the existing Python `scripts/` directory untouched), `schemas/` (JSON Schemas), `infrastructure/manifests/` (per-instance YAML), `infrastructure/secret-catalog.yml`, `infrastructure/integrations.yml`. Existing `portal/shared` stays untouched for now — it gets migrated into `packages/contract`/`packages/auth`/etc in Plans B/C. Workspace-root `tsconfig.base.json` + `eslint.config.js` are added at the **repo root** (not inside `portal/`) so they cover both `portal/*` and `packages/*` workspaces. Root `npm run lint` explicitly composes `lint:root` (root ESLint over `packages/**` + `portal/shared/**` + `packages/scripts/**`) + `lint:portal-operator` (the operator portal's existing local ESLint config). Root `package-lock.json` is the authoritative install for CI; `portal/package-lock.json` remains for portal-only local workflows but is not used by CI.

**Tech Stack:** Node 22 LTS, npm workspaces (existing convention — not pnpm), TypeScript 5.6, ESLint 9 (flat config), Ajv 8 (JSON Schema validation), YAML via `yaml` package, Vitest 2 for the validator tests, GitHub Actions for CI.

**Spec references:**
- Main spec `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` (commit `a50130f`)
- SD-4 composition spike `docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md` (commit `0b3c9d7`) §3 (manifest schema), §3.X (env-bound secrets), §7 (pinned tasks)
- SD-2 framework spike `docs/superpowers/specs/2026-05-15-sp0-decision-spike-framework.md` (commit `14d847a`)

**Out of scope for Plan A** (deferred to B/C/D):
- Any TypeScript implementation code inside `packages/contract`/`auth`/`ui`/`qa-harness`/`shell` — Plan A creates the package skeletons only.
- The full ESLint workspace-root `import/no-restricted-paths` zone array — Plan A scaffolds the rule with an empty zones list because no modules exist yet; Plan D's `scripts/generate-eslint-zones.ts` will populate it.
- The composition codegen scripts (`generate-composition.ts`, `audit-composition.ts`, `generate-ci-matrix.ts`, `generate-eslint-zones.ts`) — Plan D.
- Auth machinery (`packages/auth`) — Plan B.
- Backend `/health` endpoint changes — Plan B/C cross-cutting.

---

## File Structure (Plan A creates / modifies)

### Creates

```
schemas/
  instance-manifest.schema.json          # strict-mode JSON Schema for the YAML manifest

infrastructure/
  manifests/
    operator-dev.yml                     # the dev/reference full composition (placeholder modules list)
    example-reclaimrx-standalone.yml     # documents the [reclaimrx] standalone shape
  secret-catalog.yml                     # secret://<scope> ownership list (empty in Plan A)
  integrations.yml                       # external-endpoint allow-list (empty in Plan A)

packages/
  .gitkeep                               # makes the empty workspace root committable
  README.md                              # explains what goes here in plans B/C/D
  scripts/
    validate-manifest.ts                 # Ajv-based validator per SD-4 §3 (offline checks only)
    validate-manifest.test.ts            # vitest unit tests
    package.json                         # @infinityrx/scripts workspace
    tsconfig.json
    vitest.config.ts

# Repo-root config (NEW — currently no config at this level)
tsconfig.base.json                       # shared TS config (verbatimModuleSyntax true)
tsconfig.json                            # workspace-root tsconfig (references all workspaces)
eslint.config.js                         # workspace-root ESLint flat config
.npmrc                                   # workspaces config + Node engine pin
.github/
  workflows/
    sp0-foundation.yml                   # lint + typecheck + manifest-validate
```

### Modifies

```
package.json                             # add scripts/ + packages/* to workspaces; add devDependencies
.gitignore                               # add packages/*/node_modules, packages/*/dist
```

### Leaves alone

```
portal/                                  # entire portal/ tree untouched in Plan A
                                         #   - portal/package.json + portal/package-lock.json remain
                                         #     for portal-only local workflows; CI uses repo-root lockfile
modules/                                 # Python backend modules untouched
shared/                                  # Python shared code untouched
scripts/                                 # existing top-level Python loaders (apply_rls.py,
                                         #   load_fdb.py, etc.) — DELIBERATELY untouched
                                         #   TS tooling lives in packages/scripts/
infrastructure/docker/, infrastructure/scripts/   # existing infra untouched
.claude/, docs/                          # untouched
```

---

## Plan A — Tasks

### Task 1: Repo-root workspace + scripts/ package scaffold

**Files:**
- Create: `package.json` (repo root — currently doesn't exist; `portal/package.json` covers portal workspaces only and remains in place)
- Create: `tsconfig.base.json`
- Create: `tsconfig.json`
- Create: `.npmrc`
- Create: `packages/.gitkeep`
- Create: `packages/README.md`
- Create: `packages/scripts/package.json`
- Create: `packages/scripts/tsconfig.json`

- [ ] **Step 1.1: Verify there is no repo-root `package.json`**

Run: `ls package.json 2>&1`
Expected: `ls: cannot access 'package.json': No such file or directory`

If a root `package.json` already exists, STOP and surface it — Plan A assumes the portal/ workspace root is the only one; a new root must not conflict.

- [ ] **Step 1.2: Write repo-root `package.json`**

```json
{
  "name": "infinityrx-platform",
  "private": true,
  "version": "0.0.0",
  "description": "InfinityRx platform monorepo. SP-0 establishes packages/* workspaces alongside the existing portal/ workspaces.",
  "engines": {
    "node": ">=22.0.0 <23"
  },
  "workspaces": [
    "portal/operator",
    "portal/shared",
    "packages/*"
  ],
  "scripts": {
    "lint": "npm run lint:root && npm run lint:portal-operator",
    "lint:root": "eslint . --ignore-pattern \"portal/operator/**\" --ignore-pattern \"node_modules/**\" --ignore-pattern \"**/dist/**\" --ignore-pattern \"**/.next/**\"",
    "lint:portal-operator": "npm --workspace=ifx-operator-portal run lint",
    "typecheck": "tsc -b",
    "manifest:validate": "npm --workspace=@infinityrx/scripts run validate-manifest -- infrastructure/manifests/operator-dev.yml",
    "manifest:validate:standalone": "npm --workspace=@infinityrx/scripts run validate-manifest -- infrastructure/manifests/example-reclaimrx-standalone.yml",
    "test": "npm --workspace=@infinityrx/scripts test"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "22.7.5",
    "eslint": "9.13.0",
    "@eslint/js": "9.13.0",
    "typescript-eslint": "8.10.0",
    "vitest": "2.1.3"
  }
}
```

**Lockfile authority:** root `package.json` + root `package-lock.json` is the source of truth for CI and SP-0 plan execution. `portal/package.json` + `portal/package-lock.json` remain in place for portal-only local workflows (anyone running `cd portal && npm install` directly). CI runs `npm ci` from the repo root only. If a dependency version diverges between the two lockfiles, the root lockfile wins; the discrepancy is resolved by Plan C when `portal/shared` migrates into `packages/*` and `portal/package.json` is reduced or removed.

- [ ] **Step 1.3: Write `tsconfig.base.json`**

```json
{
  "compilerOptions": {
    "target": "ES2023",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2023"],
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "exactOptionalPropertyTypes": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "declaration": true,
    "declarationMap": true,
    "sourceMap": true,
    "composite": true,
    "incremental": true
  }
}
```

- [ ] **Step 1.4: Write workspace-root `tsconfig.json`**

```json
{
  "files": [],
  "references": [
    { "path": "./packages/scripts" }
  ]
}
```

(`portal/*` and other `packages/*` references get added as those workspaces gain TypeScript code in Plans B/C/D. `packages/scripts/` is the only workspace with TS code in Plan A.)

- [ ] **Step 1.5: Write `.npmrc`**

```
engine-strict=true
save-exact=true
fund=false
```

- [ ] **Step 1.6: Write `packages/.gitkeep` and `packages/README.md`**

`packages/.gitkeep`: empty file.

`packages/README.md`:

```markdown
# packages/

SP-0 workspace root for shared TypeScript packages.

| Package | Plan that adds it | Purpose |
|---|---|---|
| `packages/contract` | Plan B | Typed backend clients, error envelope, cache policy types |
| `packages/auth` | Plan B | Canonical auth/JWT contract per SD-1 (`b876c3b`) |
| `packages/ui` | Plan C | Shared design system (Radix/shadcn primitives) |
| `packages/qa-harness` | Plan C | Dev-mode harness (services-health, mock toggle, factories) |
| `packages/shell` | Plan C | Thin Next.js host; module registration + mounting + generated composition artifacts |
| `packages/modules/<name>` | Plan D + SP-1+ | One package per product module; SP-0 ships ReclaimRx as the reference |

All packages here are framework-agnostic per SD-2 (`14d847a`) — zero `next/*` imports. Next.js usage lives ONLY in `portal/operator/app/`.
```

- [ ] **Step 1.7: Write `packages/scripts/package.json`**

```json
{
  "name": "@infinityrx/scripts",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "build": "tsc -b",
    "validate-manifest": "tsx validate-manifest.ts",
    "test": "vitest run"
  },
  "dependencies": {
    "ajv": "8.17.1",
    "ajv-formats": "3.0.1",
    "yaml": "2.6.0"
  },
  "devDependencies": {
    "tsx": "4.19.1",
    "vitest": "2.1.3",
    "typescript": "5.6.3",
    "@types/node": "22.7.5"
  }
}
```

- [ ] **Step 1.8: Write `packages/scripts/tsconfig.json`**

```json
{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "./dist",
    "rootDir": "."
  },
  "include": ["*.ts"],
  "exclude": ["**/*.test.ts", "dist", "node_modules"]
}
```

- [ ] **Step 1.9: Update `.gitignore`**

Append:

```
# SP-0 additions
packages/*/node_modules
packages/*/dist
packages/*/*.tsbuildinfo
```

- [ ] **Step 1.10: Install dependencies**

Run: `npm install`

Expected: clean install, no peer-dep warnings, `package-lock.json` updated. If `@infinityrx/scripts` doesn't show up in `npm ls --workspaces --depth=0`, the workspaces array is misconfigured — debug before continuing.

- [ ] **Step 1.11: Commit**

```bash
git add package.json package-lock.json tsconfig.base.json tsconfig.json .npmrc .gitignore packages/.gitkeep packages/README.md packages/scripts/package.json packages/scripts/tsconfig.json
git commit -m "feat(sp-0): scaffold packages/ workspace and root TS config

Adds repo-root npm-workspaces config alongside the existing
portal/ workspace root. Introduces packages/ (containing
packages/scripts/ for TS tooling in Plan A; packages/contract,
auth, ui, qa-harness, shell, modules/* arrive in Plans B/C/D).
Adds workspace-root tsconfig.base.json with verbatimModuleSyntax
true per SD-4 §4 closing pass-1 type-only import bypass.

Top-level scripts/ (existing Python loaders) is untouched —
TS tooling lives in packages/scripts/ to keep workspace
boundaries clean.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Manifest JSON Schema (`schemas/instance-manifest.schema.json`)

**Files:**
- Create: `schemas/instance-manifest.schema.json`
- Create: `schemas/README.md`

Schema per SD-4 §3: strict mode (`additionalProperties: false`), every `required_*` array `uniqueItems: true`, `audience` enum, `migration_policy.ordering` enum.

- [ ] **Step 2.1: Write `schemas/instance-manifest.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://infinityrx.dev/schemas/instance-manifest.schema.json",
  "title": "InfinityRx Instance Deployment Manifest",
  "description": "Per-customer instance manifest. Source of truth for build + deploy. See SD-4 (composition spike) §3 for the authoritative definition.",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "instance_name",
    "audience",
    "auth_profile",
    "modules",
    "required_backends",
    "required_shared_services",
    "required_schemas",
    "required_migrations",
    "required_env",
    "required_health",
    "required_seed_data",
    "required_queues",
    "required_jobs",
    "required_buckets",
    "required_integrations",
    "required_secrets",
    "migration_policy"
  ],
  "properties": {
    "instance_name": {
      "type": "string",
      "pattern": "^[a-z0-9][a-z0-9-]*[a-z0-9]$",
      "minLength": 3,
      "maxLength": 64,
      "description": "Lowercase kebab-case. Used in container labels and logs."
    },
    "audience": {
      "type": "string",
      "enum": ["operator", "client", "provider"],
      "description": "Determines which portal app builds against this manifest."
    },
    "auth_profile": {
      "type": "string",
      "enum": ["development", "mock", "production"],
      "description": "References infrastructure/auth-profiles/<name>.yml (added in Plan B alongside packages/auth)."
    },
    "branding": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "primary_color": { "type": "string", "pattern": "^#[0-9a-fA-F]{6}$" },
        "logo_url": { "type": "string", "format": "uri" }
      }
    },
    "modules": {
      "type": "array",
      "items": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
      "uniqueItems": true,
      "minItems": 0
    },
    "required_backends":         { "$ref": "#/$defs/string_array" },
    "required_shared_services":  { "$ref": "#/$defs/string_array" },
    "required_schemas":          { "$ref": "#/$defs/string_array" },
    "required_migrations":       { "$ref": "#/$defs/string_array" },
    "required_env":              { "$ref": "#/$defs/string_array" },
    "required_health":           {
      "type": "array",
      "items": { "type": "string", "format": "uri" },
      "uniqueItems": true,
      "minItems": 0
    },
    "required_seed_data":        { "$ref": "#/$defs/string_array" },
    "required_queues":           { "$ref": "#/$defs/string_array" },
    "required_jobs":             { "$ref": "#/$defs/string_array" },
    "required_buckets":          { "$ref": "#/$defs/string_array" },
    "required_integrations":     { "$ref": "#/$defs/string_array" },
    "required_secrets": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^secret://[a-z][a-z0-9-]*/[a-z0-9][a-z0-9-]*$"
      },
      "uniqueItems": true,
      "minItems": 0
    },
    "migration_policy": {
      "type": "object",
      "additionalProperties": false,
      "required": ["ordering", "rollback", "pre_check"],
      "properties": {
        "ordering": { "type": "string", "enum": ["explicit"] },
        "rollback": { "type": "string", "enum": ["none"] },
        "pre_check": { "type": "string", "enum": ["dry_run_required"] }
      }
    }
  },
  "$defs": {
    "string_array": {
      "type": "array",
      "items": { "type": "string", "minLength": 1 },
      "uniqueItems": true,
      "minItems": 0
    }
  }
}
```

- [ ] **Step 2.2: Write `schemas/README.md`**

```markdown
# schemas/

JSON Schemas used to validate configuration files outside the TypeScript type system.

| Schema | Validates | Authority |
|---|---|---|
| `instance-manifest.schema.json` | `infrastructure/manifests/<instance>.yml` | SD-4 §3 |

All schemas are Draft 2020-12 + Ajv strict mode (`additionalProperties: false` enforced). The validator (`scripts/validate-manifest.ts`) refuses any file that fails the schema before computing transitive-closure checks.
```

- [ ] **Step 2.3: Commit**

```bash
git add schemas/
git commit -m "feat(sp-0): instance-manifest JSON Schema per SD-4 §3

Strict-mode Draft 2020-12 schema with additionalProperties:false
at every level. Required keys cover the 12 required_* axes plus
migration_policy. instance_name is kebab-case; required_secrets
match secret://<scope>/<name> grammar; required_health entries
are URIs. Validator is added in Task 4.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Example manifests + secret catalog + integrations allow-list

**Files:**
- Create: `infrastructure/manifests/operator-dev.yml`
- Create: `infrastructure/manifests/example-reclaimrx-standalone.yml`
- Create: `infrastructure/manifests/README.md`
- Create: `infrastructure/secret-catalog.yml`
- Create: `infrastructure/integrations.yml`

- [ ] **Step 3.1: Write `infrastructure/manifests/operator-dev.yml`**

```yaml
# Dev / reference full-composition manifest.
# Used by `npm run operator:dev` and by Plan A's manifest-validator test.
# Modules list is EMPTY in Plan A — Plan D's reclaimrx scaffolding adds it.
instance_name: operator-dev
audience: operator
auth_profile: development
branding:
  primary_color: "#1f2937"
modules: []
required_backends: []
required_shared_services:
  - postgres
  - redis
required_schemas: []
required_migrations: []
required_env:
  - JWT_SECRET
  - NEXTAUTH_SECRET
  - INFINITYRX_ENV
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets:
  - secret://jwt/signing-key
  - secret://nextauth/secret
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
```

- [ ] **Step 3.2: Write `infrastructure/manifests/example-reclaimrx-standalone.yml`**

```yaml
# Reference manifest documenting the shape of a "customer buys just ReclaimRx" composition.
# NOT auto-deployed. Plan D wires up the actual reclaimrx module package + its requires.* fields.
instance_name: example-reclaimrx-standalone
audience: operator
auth_profile: production
modules:
  - reclaimrx
required_backends:
  - reclaimrx
  - core-platform
required_shared_services:
  - postgres
  - redis
required_schemas:
  - reclaimrx_v1
  - core_v1
required_migrations:
  - core
  - reclaimrx
required_env:
  - JWT_SECRET
  - NEXTAUTH_SECRET
  - INFINITYRX_ENV
  - DATABASE_URL_CORE
  - DATABASE_URL_RECLAIMRX
  - REDIS_URL
required_health:
  - http://core-platform:8000/health
  - http://reclaimrx:8020/health
required_seed_data:
  - reclaimrx/fwa-rules
required_queues:
  - reclaimrx.investigation.opened
required_jobs:
  - core.audit_chain_verify
  - core.session_reaper
  - reclaimrx.graph_anomaly_scan
required_buckets:
  - reclaimrx-investigation-evidence
  - core-export-staging
required_integrations: []
required_secrets:
  - secret://jwt/signing-key
  - secret://nextauth/secret
  - secret://db/core
  - secret://db/reclaimrx
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
```

- [ ] **Step 3.3: Write `infrastructure/manifests/README.md`**

```markdown
# infrastructure/manifests/

Per-customer instance manifests. One YAML file per customer-instance, validated against `schemas/instance-manifest.schema.json` by `scripts/validate-manifest.ts`.

| File | Purpose |
|---|---|
| `operator-dev.yml` | Dev / reference full composition. Modules list grows in Plan D as packages/modules/* are added. |
| `example-reclaimrx-standalone.yml` | Reference shape for a single-module customer. Not auto-deployed. |

Plan A validates that both files pass the schema. Plans B/C/D extend `operator-dev.yml` as new modules ship.

Manifest authority is SD-4 §3 (`docs/superpowers/specs/2026-05-15-sp0-decision-spike-composition.md`).
```

- [ ] **Step 3.4: Write `infrastructure/secret-catalog.yml`**

```yaml
# Catalog of secret scopes the InfinityRx platform owns.
# scripts/validate-manifest.ts confirms every manifest secret reference's scope
# is declared here (per SD-4 §3 PR-CI offline checks).
# Plan A seeds the bare minimum; Plans B/C/D extend as scopes are needed.
scopes:
  - name: jwt
    description: JWT signing/verification keys per environment
    owner: packages/auth (added in Plan B)
  - name: nextauth
    description: NextAuth.js session encryption secret
    owner: portal/operator
  - name: db
    description: Database connection URLs per backend module
    owner: each backend module's module.config.ts (Plan D+)
```

- [ ] **Step 3.5: Write `infrastructure/integrations.yml`**

```yaml
# Allow-list of external network endpoints the platform may call out to.
# Empty in Plan A; populated as modules declare requires.integrations.
allowed_integrations: []
```

- [ ] **Step 3.6: Commit**

```bash
git add infrastructure/manifests/ infrastructure/secret-catalog.yml infrastructure/integrations.yml
git commit -m "feat(sp-0): seed instance manifests + secret catalog + integrations allow-list

operator-dev.yml is the dev/full composition (empty modules in
Plan A; grows in Plan D). example-reclaimrx-standalone.yml
documents the single-module shape. secret-catalog.yml + integrations.yml
are the offline-validation references for the manifest validator
per SD-4 §3 PR-CI offline checks.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Manifest validator script + tests (TDD)

**Files:**
- Create: `packages/scripts/validate-manifest.ts`
- Create: `packages/scripts/validate-manifest.test.ts`
- Create: `packages/scripts/vitest.config.ts`

This is TDD: write the failing tests first, then implement.

- [ ] **Step 4.1: Write `packages/scripts/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["*.test.ts"],
    environment: "node",
  },
});
```

- [ ] **Step 4.2: Write `packages/scripts/validate-manifest.test.ts` (failing tests)**

```ts
import { describe, it, expect } from "vitest";
import { validateManifest } from "./validate-manifest.js";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");

function loadFixture(rel: string): string {
  return readFileSync(join(repoRoot, rel), "utf8");
}

describe("validateManifest", () => {
  it("accepts the operator-dev.yml fixture", () => {
    const yaml = loadFixture("infrastructure/manifests/operator-dev.yml");
    const result = validateManifest(yaml, {
      secretCatalogYaml: loadFixture("infrastructure/secret-catalog.yml"),
      integrationsAllowlistYaml: loadFixture("infrastructure/integrations.yml"),
    });
    expect(result.ok).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("accepts the example-reclaimrx-standalone.yml fixture", () => {
    const yaml = loadFixture("infrastructure/manifests/example-reclaimrx-standalone.yml");
    const result = validateManifest(yaml, {
      secretCatalogYaml: loadFixture("infrastructure/secret-catalog.yml"),
      integrationsAllowlistYaml: loadFixture("infrastructure/integrations.yml"),
    });
    expect(result.ok).toBe(true);
    expect(result.errors).toEqual([]);
  });

  it("rejects manifests missing required keys", () => {
    const result = validateManifest("instance_name: foo\naudience: operator\n", {
      secretCatalogYaml: "scopes: []\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
    expect(result.errors.some((e) => e.includes("must have required property"))).toBe(true);
  });

  it("rejects unknown top-level keys (additionalProperties:false)", () => {
    const yaml = `
instance_name: rogue-instance
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets: []
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
rogue_key: should-fail
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes: []\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.includes("rogue_key") || e.includes("additional"))).toBe(true);
  });

  it("rejects audience values outside the enum", () => {
    const yaml = `
instance_name: bad-audience
audience: admin
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets: []
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes: []\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.includes("audience"))).toBe(true);
  });

  it("rejects malformed secret references", () => {
    const yaml = `
instance_name: bad-secret
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets:
  - not-a-secret-uri
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes:\n  - name: jwt\n    description: x\n    owner: x\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.toLowerCase().includes("pattern") || e.includes("secret"))).toBe(true);
  });

  it("rejects secret references whose scope is not in the catalog", () => {
    const yaml = `
instance_name: unknown-scope
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets:
  - secret://unknown-scope/foo
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes:\n  - name: jwt\n    description: x\n    owner: x\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.includes("unknown-scope"))).toBe(true);
  });

  it("returns a graceful error for a malformed secret-catalog.yml (non-array scopes)", () => {
    const yaml = `
instance_name: malformed-catalog-test
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets: []
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes: not-an-array\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.toLowerCase().includes("catalog"))).toBe(true);
  });

  it("returns a graceful error for a malformed integrations.yml (non-array allowed_integrations)", () => {
    const yaml = `
instance_name: malformed-allowlist-test
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations: []
required_secrets: []
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes: []\n",
      integrationsAllowlistYaml: "allowed_integrations: not-an-array\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.toLowerCase().includes("integration"))).toBe(true);
  });

  it("rejects required_integrations entries not in the allow-list", () => {
    const yaml = `
instance_name: bad-integration
audience: operator
auth_profile: development
modules: []
required_backends: []
required_shared_services: []
required_schemas: []
required_migrations: []
required_env: []
required_health: []
required_seed_data: []
required_queues: []
required_jobs: []
required_buckets: []
required_integrations:
  - some.external.api
required_secrets: []
migration_policy:
  ordering: explicit
  rollback: none
  pre_check: dry_run_required
`;
    const result = validateManifest(yaml, {
      secretCatalogYaml: "scopes: []\n",
      integrationsAllowlistYaml: "allowed_integrations: []\n",
    });
    expect(result.ok).toBe(false);
    expect(result.errors.some((e) => e.includes("some.external.api"))).toBe(true);
  });
});
```

- [ ] **Step 4.3: Run tests to verify they fail**

Run: `npm --workspace=@infinityrx/scripts test`
Expected: ALL 10 tests FAIL with "validateManifest is not defined" or import error. This confirms the test file imports the function that does not exist yet.

- [ ] **Step 4.4: Write `packages/scripts/validate-manifest.ts`**

```ts
#!/usr/bin/env node
/**
 * Manifest validator per SD-4 §3 (PR-CI offline checks only).
 *
 * Performs:
 *   1. JSON Schema gate (Ajv 2020 strict mode, additionalProperties:false)
 *   2. Secret-reference scope catalog ownership check
 *   3. Required-integrations allow-list check
 *
 * Does NOT perform:
 *   - Transitive-closure validation against module.config.ts files (Plan D adds it
 *     once packages/modules/* exist).
 *   - Live secret-manager existence (deploy/boot only — scripts/verify-instance-secrets.ts
 *     in Plan D).
 *
 * Authority: SD-4 (`0b3c9d7`) §3.
 */
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { parse as parseYaml } from "yaml";
import { readFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, resolve } from "node:path";
import process from "node:process";
import type { ValidateFunction } from "ajv";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..");

export interface ValidatorInputs {
  /** Raw YAML of infrastructure/secret-catalog.yml */
  secretCatalogYaml: string;
  /** Raw YAML of infrastructure/integrations.yml */
  integrationsAllowlistYaml: string;
}

export interface ValidationResult {
  ok: boolean;
  errors: string[];
}

const SECRET_URI_RE = /^secret:\/\/([a-z][a-z0-9-]*)\/([a-z0-9][a-z0-9-]*)$/;

let cachedValidator: ValidateFunction | null = null;

function buildSchemaValidator(): ValidateFunction {
  const ajv = new Ajv2020({ strict: true, allErrors: true });
  addFormats(ajv);
  const schemaJson = readFileSync(
    join(repoRoot, "schemas/instance-manifest.schema.json"),
    "utf8",
  );
  return ajv.compile(JSON.parse(schemaJson));
}

export function validateManifest(
  manifestYaml: string,
  inputs: ValidatorInputs,
): ValidationResult {
  const errors: string[] = [];

  let manifest: unknown;
  try {
    manifest = parseYaml(manifestYaml);
  } catch (e) {
    return { ok: false, errors: [`YAML parse error: ${(e as Error).message}`] };
  }

  // 1. JSON Schema gate
  if (!cachedValidator) cachedValidator = buildSchemaValidator();
  const schemaOk = cachedValidator(manifest);
  if (!schemaOk) {
    for (const err of cachedValidator.errors ?? []) {
      errors.push(`schema: ${err.instancePath || "/"} ${err.message ?? "(no message)"}`);
    }
    // Schema failure means downstream checks can't trust the shape; bail.
    return { ok: false, errors };
  }

  const m = manifest as {
    required_secrets: string[];
    required_integrations: string[];
  };

  // 2. Secret-reference catalog ownership
  let catalogRaw: unknown;
  try {
    catalogRaw = parseYaml(inputs.secretCatalogYaml);
  } catch (e) {
    return { ok: false, errors: [`secret-catalog YAML parse error: ${(e as Error).message}`] };
  }
  if (
    catalogRaw === null ||
    typeof catalogRaw !== "object" ||
    !Array.isArray((catalogRaw as { scopes?: unknown }).scopes)
  ) {
    errors.push(
      "secret-catalog: expected an object with a `scopes:` array. " +
      "Check infrastructure/secret-catalog.yml shape.",
    );
    return { ok: false, errors };
  }
  const knownScopes = new Set<string>(
    ((catalogRaw as { scopes: Array<{ name?: unknown }> }).scopes)
      .filter((s) => s && typeof s.name === "string")
      .map((s) => s.name as string),
  );

  for (const ref of m.required_secrets) {
    const match = SECRET_URI_RE.exec(ref);
    if (!match) {
      errors.push(`required_secrets: "${ref}" does not match secret://<scope>/<name> grammar`);
      continue;
    }
    const [, scope] = match;
    if (!knownScopes.has(scope)) {
      errors.push(`required_secrets: scope "${scope}" (in "${ref}") not declared in infrastructure/secret-catalog.yml`);
    }
  }

  // 3. Integrations allow-list
  let allowlistRaw: unknown;
  try {
    allowlistRaw = parseYaml(inputs.integrationsAllowlistYaml);
  } catch (e) {
    return { ok: false, errors: [`integrations YAML parse error: ${(e as Error).message}`] };
  }
  if (
    allowlistRaw === null ||
    typeof allowlistRaw !== "object" ||
    !Array.isArray((allowlistRaw as { allowed_integrations?: unknown }).allowed_integrations)
  ) {
    errors.push(
      "integrations: expected an object with an `allowed_integrations:` array. " +
      "Check infrastructure/integrations.yml shape.",
    );
    return { ok: false, errors };
  }
  const allowed = new Set<string>(
    (allowlistRaw as { allowed_integrations: unknown[] })
      .allowed_integrations.filter((v): v is string => typeof v === "string"),
  );
  for (const integration of m.required_integrations) {
    if (!allowed.has(integration)) {
      errors.push(`required_integrations: "${integration}" not in infrastructure/integrations.yml allow-list`);
    }
  }

  return { ok: errors.length === 0, errors };
}

// CLI entrypoint: `tsx validate-manifest.ts <path-to-manifest.yml>`.
// Portable invocation check (handles Windows paths with spaces correctly).
const invokedDirectly =
  typeof process.argv[1] === "string" &&
  pathToFileURL(resolve(process.argv[1])).href === import.meta.url;

if (invokedDirectly) {
  const manifestPath = process.argv[2];
  if (!manifestPath) {
    console.error("usage: validate-manifest <path-to-manifest.yml>");
    process.exit(2);
  }
  const manifest = readFileSync(join(repoRoot, manifestPath), "utf8");
  const secretCatalog = readFileSync(join(repoRoot, "infrastructure/secret-catalog.yml"), "utf8");
  const integrations = readFileSync(join(repoRoot, "infrastructure/integrations.yml"), "utf8");
  const result = validateManifest(manifest, {
    secretCatalogYaml: secretCatalog,
    integrationsAllowlistYaml: integrations,
  });
  if (result.ok) {
    console.log(`✓ ${manifestPath} validates clean`);
    process.exit(0);
  } else {
    console.error(`✗ ${manifestPath} has ${result.errors.length} error(s):`);
    for (const e of result.errors) console.error(`  - ${e}`);
    process.exit(1);
  }
}
```

- [ ] **Step 4.5: Run tests to verify they pass**

Run: `npm --workspace=@infinityrx/scripts test`
Expected: all 10 tests PASS.

- [ ] **Step 4.6: Run the CLI against the dev manifest end-to-end**

Run (from repo root): `npm run manifest:validate`
Expected: `✓ infrastructure/manifests/operator-dev.yml validates clean` and exit 0.

- [ ] **Step 4.7: Run the CLI against the reclaimrx-standalone example**

Run (from repo root): `npm run manifest:validate:standalone`
Expected: `✓ infrastructure/manifests/example-reclaimrx-standalone.yml validates clean` and exit 0.

- [ ] **Step 4.8: Commit**

```bash
git add packages/scripts/validate-manifest.ts packages/scripts/validate-manifest.test.ts packages/scripts/vitest.config.ts
git commit -m "feat(sp-0): manifest validator with 10 vitest tests (TDD)

packages/scripts/validate-manifest.ts performs the SD-4 §3
PR-CI offline checks: JSON Schema gate (Ajv 2020 strict mode),
secret-reference scope catalog ownership, required_integrations
allow-list. Does NOT perform transitive-closure (Plan D) or
live secret-manager calls (deploy/boot only).

10 vitest tests cover happy path (2 manifests), missing
required keys, additionalProperties:false, audience enum,
malformed secret URIs, unknown scopes, unknown integrations,
malformed secret-catalog.yml (non-array scopes), malformed
integrations.yml (non-array allowed_integrations).

Implementation uses Ajv2020 ESM default import (no .default
dereference), pathToFileURL for portable CLI entrypoint
detection across Windows/Unix paths with spaces, and
Array.isArray guards on every YAML-loaded input.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Workspace-root ESLint flat config (stub)

**Files:**
- Create: `eslint.config.js` (repo root)

Plan A scaffolds the workspace-root ESLint with the `no-restricted-imports` package-name rule active and the `import/no-restricted-paths` zone array empty (no modules exist yet). Plan D's `scripts/generate-eslint-zones.ts` populates the zones array.

- [ ] **Step 5.1: Add `eslint-plugin-import` to root devDependencies**

Modify `package.json` devDependencies:

```json
"devDependencies": {
  "typescript": "5.6.3",
  "@types/node": "22.7.5",
  "eslint": "9.13.0",
  "@eslint/js": "9.13.0",
  "typescript-eslint": "8.10.0",
  "vitest": "2.1.3",
  "eslint-plugin-import": "2.31.0",
  "eslint-import-resolver-typescript": "3.6.3"
}
```

Run: `npm install`
Expected: clean install.

- [ ] **Step 5.2: Write `eslint.config.js`**

```js
// Workspace-root ESLint flat config.
// Authority: SD-4 §4 (composition spike) for import-boundary enforcement.
// Plan A scaffolds the rule shape with empty zones; Plan D's
// scripts/generate-eslint-zones.ts populates `GENERATED_MODULE_ZONES`
// from packages/modules/* as those modules are added.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import importPlugin from "eslint-plugin-import";

// Plan D will replace this empty array with the generated zones import:
//   import { GENERATED_MODULE_ZONES } from "./packages/shell/src/_generated/eslint-zones.js";
const GENERATED_MODULE_ZONES = [];

export default tseslint.config(
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.next/**",
      "**/playwright-report/**",
      "**/test-results/**",
      // SP-0 Plan D will add: "packages/shell/src/_generated/**" as an allow-only
      // path for @infinityrx/module-* references.
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,

  // ── Block A: @infinityrx/module-* boundary applies EVERYWHERE in the workspace.
  // (The `import/no-restricted-paths` zones at the bottom complement this for
  //  relative/alias bypass paths once Plan D populates them.)
  {
    files: ["**/*.{ts,tsx,js,jsx,mjs,cjs}"],
    plugins: { import: importPlugin },
    settings: {
      "import/resolver": {
        typescript: { project: ["./tsconfig.json", "./packages/scripts/tsconfig.json"] },
      },
    },
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [
          { group: ["@infinityrx/module-*"],
            message: "Modules are referenced ONLY from packages/shell/src/_generated/. Direct imports break composition isolation (SD-4 §2)." },
        ],
      }],

      // SD-4 §4 bypass-path coverage. Plan A scaffolds the rule; Plan D
      // verifies it catches each bypass form with integration tests.
      "no-restricted-syntax": ["error",
        // Shape 1 — @infinityrx/module-* dynamic forms
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
        // Shape 2 — relative traversal
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
        // Shape 3 — TS path-alias forms
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
      ],

      "@typescript-eslint/consistent-type-imports": ["error",
        { prefer: "type-imports", fixStyle: "separate-type-imports" }],

      // Empty in Plan A — Plan D's scripts/generate-eslint-zones.ts
      // emits a concrete N*(N-1) zone array into _generated/eslint-zones.ts
      // and this rule's `zones` becomes that import.
      "import/no-restricted-paths": ["error", { zones: GENERATED_MODULE_ZONES }],
    },
  },

  // ── Block B: framework-agnostic import ban scoped to dirs that MUST stay
  // framework-agnostic per SD-2 (`14d847a`). portal/operator/** is excluded
  // because that is the ONE place where Next.js is allowed.
  {
    files: [
      "packages/**/*.{ts,tsx,js,jsx,mjs,cjs}",
      "portal/shared/**/*.{ts,tsx,js,jsx,mjs,cjs}",
    ],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [
          { group: ["@infinityrx/module-*"],
            message: "Modules are referenced ONLY from packages/shell/src/_generated/. Direct imports break composition isolation (SD-4 §2)." },
          { group: ["next/*", "next-auth/*", "@auth/*"],
            message: "Framework-specific imports are forbidden outside portal/operator/app/. Move usage into a thin adapter (SD-2)." },
        ],
      }],
    },
  },

  // ── Block C: the operator portal's local ESLint config (portal/operator/eslint.config.js)
  // owns ALL portal/operator/** rules. Root ESLint applies only the @infinityrx/module-*
  // ban and the no-restricted-syntax bypass-path rules in this scope.
  // The root `npm run lint` script runs root lint with --ignore-pattern "portal/operator/**"
  // and then runs `npm --workspace=ifx-operator-portal run lint` separately so the operator's
  // own config executes on its own files. Both lints must pass for the workspace to be green.
);
```

- [ ] **Step 5.3: Verify the root ESLint config loads cleanly with empty zones**

Critical: `import/no-restricted-paths` with `zones: []` must be a no-op, not a config error. Prove it before running full lint:

Run: `npx eslint --print-config packages/scripts/validate-manifest.ts > /tmp/eslint-resolved.json 2>&1`

Expected: exit 0, `/tmp/eslint-resolved.json` is valid JSON containing the resolved rule set (including `"import/no-restricted-paths": [...]`). If exit ≠ 0 or output is an error message, the config has a structural problem (most likely `import/no-restricted-paths` rejecting the empty zones array). In that case, change the empty default to `[{ target: "./packages/.gitkeep", from: "./packages/.gitkeep" }]` (a self-referencing no-op zone) and document the workaround in a code comment.

- [ ] **Step 5.4: Run the composed lint locally**

Run: `npm run lint`

Expected: both `lint:root` and `lint:portal-operator` exit 0. Specifically:
1. `lint:root` runs ESLint over packages/scripts/* and any other non-portal-operator workspace files. Currently the only TS file is the validator; clean run expected.
2. `lint:portal-operator` invokes `npm --workspace=ifx-operator-portal run lint`, which uses the operator's existing `portal/operator/eslint.config.js`. That config is unchanged in Plan A — its run today is the baseline.

If the operator's lint script doesn't exist yet (check `portal/operator/package.json`'s scripts), the composed `lint:portal-operator` will fail with "Missing script". Fix: either add a no-op `"lint": "echo 'operator lint TBD in Plan C'"` step to the operator's package.json (NOT recommended — Plan A wants the existing lint to actually run), OR — confirmed by `cat portal/operator/package.json | jq '.scripts.lint'` — the operator already has a lint script and the composition works.

- [ ] **Step 5.5: Commit**

```bash
git add eslint.config.js package.json package-lock.json
git commit -m "feat(sp-0): workspace-root ESLint flat config with SD-4 §4 import-boundary rules

Scaffolds the no-restricted-imports + no-restricted-syntax
bypass-path rules from SD-4 §4 covering the three specifier
shapes (package, relative traversal, TS path-alias) across
five forms (Import, ExportAll, ExportNamed, ImportExpression,
require call). Adds consistent-type-imports and
verbatimModuleSyntax (via tsconfig.base.json) so type-only
imports are stripped from emit.

import/no-restricted-paths zones array is empty in Plan A
(no modules exist yet); Plan D's scripts/generate-eslint-zones.ts
populates it.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: GitHub Actions CI workflow for SP-0 foundation

**Files:**
- Create: `.github/workflows/sp0-foundation.yml`

CI runs on every push and PR. Lane: lint + typecheck + manifest-validate + scripts tests. Composition matrix lane is empty in Plan A; Plan D fills it.

- [ ] **Step 6.1: Write `.github/workflows/sp0-foundation.yml`**

```yaml
name: sp0-foundation

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  foundation:
    name: Foundation (lint, typecheck, manifest-validate, scripts tests)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node 22
        uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: "npm"

      - name: Install dependencies
        run: npm ci

      - name: Lint — root config (packages/* + portal/shared)
        run: npm run lint:root

      - name: Lint — operator portal (existing local config)
        run: npm run lint:portal-operator

      - name: Typecheck (project references)
        run: npm run typecheck

      - name: Manifest validate (operator-dev.yml)
        run: npm run manifest:validate

      - name: Manifest validate (example-reclaimrx-standalone.yml)
        run: npm run manifest:validate:standalone

      - name: Scripts tests (vitest)
        run: npm --workspace=@infinityrx/scripts test
```

- [ ] **Step 6.2: Run the CI sequence locally to prove green**

Run in sequence (any failure means CI would fail too):

```bash
npm ci
npm run lint:root
npm run lint:portal-operator
npm run typecheck
npm run manifest:validate
npm run manifest:validate:standalone
npm --workspace=@infinityrx/scripts test
```

Expected: all 7 commands exit 0.

- [ ] **Step 6.3: Commit**

```bash
git add .github/workflows/sp0-foundation.yml
git commit -m "ci(sp-0): foundation workflow — lint, typecheck, manifest-validate, scripts tests

Single job runs the four checks Plan A enables. Composition-matrix
workflow is added in Plan D once the codegen scripts + reference
module exist.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Plan A acceptance — verify the foundation is sound

**Files:**
- Create: `docs/superpowers/plans/2026-05-15-sp0-plan-a-status.md`

This is the explicit acceptance gate before Plan B starts.

- [ ] **Step 7.1: Run the full local CI sequence one more time, clean**

```bash
rm -rf node_modules packages/scripts/node_modules portal/operator/node_modules portal/shared/node_modules
npm ci
npm run lint:root
npm run lint:portal-operator
npm run typecheck
npm run manifest:validate
npm run manifest:validate:standalone
npm --workspace=@infinityrx/scripts test
```

Expected: all 7 commands exit 0. If anything fails, fix before Step 7.2.

- [ ] **Step 7.2: Write the Plan A status document**

```markdown
# SP-0 Plan A — Foundation Scaffolding — Acceptance Status

**Status:** Complete. <DATE_FROM_GIT_LOG>

**Final commit:** <FINAL_SHA_FROM_GIT_LOG>

**What ships:**
- Repo-root `package.json` with `packages/*` + `scripts` workspaces alongside existing `portal/*`.
- `tsconfig.base.json` + workspace-root `tsconfig.json` with `verbatimModuleSyntax`, `strict`, `composite`.
- Workspace-root `eslint.config.js` with SD-4 §4 import-boundary rules scaffolded (zones array empty until Plan D).
- `schemas/instance-manifest.schema.json` — Draft 2020-12, Ajv strict mode, all 17 keys covered.
- `infrastructure/manifests/operator-dev.yml` (dev/full composition — empty modules in Plan A).
- `infrastructure/manifests/example-reclaimrx-standalone.yml` (reference shape for single-module customer).
- `infrastructure/secret-catalog.yml` (scope catalog).
- `infrastructure/integrations.yml` (egress allow-list, empty).
- `scripts/validate-manifest.ts` + 8 vitest tests covering schema gate, scope catalog, integrations allow-list.
- `.github/workflows/sp0-foundation.yml` CI workflow (lint + typecheck + manifest-validate + scripts test).

**What is NOT in Plan A** (Plan B and after):
- Any package implementation code (`packages/contract`, `packages/auth`, etc. are not even scaffolded yet — Plan B starts with `packages/contract` + `packages/auth`).
- Composition codegen scripts (`generate-composition.ts`, `audit-composition.ts`, `generate-ci-matrix.ts`, `generate-eslint-zones.ts`) — Plan D.
- The reference `packages/modules/reclaimrx` module — Plan D.
- `portal/operator` modifications — Plan D (mounts the shell + reference module).

**Verification:**
- `npm run lint:root` exits 0 (root ESLint over packages/scripts + ignored portal/operator).
- `npm run lint:portal-operator` exits 0 (operator's own ESLint config runs unchanged).
- `npm run typecheck` exits 0 against the workspace-root tsconfig project references.
- `npm run manifest:validate` returns "✓ infrastructure/manifests/operator-dev.yml validates clean".
- `npm run manifest:validate:standalone` returns "✓ infrastructure/manifests/example-reclaimrx-standalone.yml validates clean".
- `npm --workspace=@infinityrx/scripts test` — 10/10 vitest tests pass.
- `.github/workflows/sp0-foundation.yml` runs green on first PR after Plan A commits.

**Decision: ready for Plan B (packages/contract + packages/auth) to be written and executed.**
```

Fill in `<DATE_FROM_GIT_LOG>` and `<FINAL_SHA_FROM_GIT_LOG>` from `git log -1 --format="%cs %H"` output.

- [ ] **Step 7.3: Commit Plan A acceptance doc**

```bash
git add docs/superpowers/plans/2026-05-15-sp0-plan-a-status.md
git commit -m "docs(sp-0): Plan A foundation scaffolding acceptance status

Records what Plan A delivered, what's explicitly NOT in scope,
and the 8 verification commands that prove the foundation is
green end-to-end. Gate condition for Plan B to start.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Plan A — Done

After Task 7's final commit, Plan A is complete. Verification: `git log --oneline | head -10` should show 7 SP-0 Plan A commits (workspace scaffold, schema, manifests/catalogs, validator+tests, ESLint config, CI workflow, status doc).

Plan B (packages/contract + packages/auth) gets written next using the established patterns: workspace-root config, validation gate, TDD discipline, CI workflow extension.

---

## Self-Review Checklist (applied 2026-05-15)

**1. Spec coverage:**

| Spec section | Plan A covers? | Notes |
|---|---|---|
| §4.1 D10 auth contract | NO — Plan B | Per Plan A's scope boundary |
| §4.1 D11 framework | PARTIAL — config guardrails only | tsconfig.base.json + workspace-root ESLint scoping framework-imports to packages/** + portal/shared/**. Actual framework/shell enforcement lands in Plan C/D when the shell mounts and the operator portal consumes it |
| §4.1 D12 gateway | YES (by omission) | No gateway service created — SD-3 defer is honored |
| §4.1 D13 composition mechanism | PARTIAL | Schema + validator (Task 2, 4), ESLint scaffold (Task 5); codegen scripts deferred to Plan D |
| §5.2 repo structure | YES | packages/, schemas/, infrastructure/manifests/ created |
| §6.10 deployment manifest | YES | Full SD-4 §3 schema implemented |
| §9.5 CI | PARTIAL | Foundation lane only; composition matrix lane in Plan D |

Gaps are intentional and documented in Task 7's status doc.

**2. Placeholder scan:** Searched for "TBD", "TODO", "implement later", "fill in", "Add appropriate", "similar to" — none found in the plan tasks. The validator code is complete; the ESLint config has empty arrays in named locations (`GENERATED_MODULE_ZONES = []`) with explicit comments tying them to Plan D's codegen.

**3. Type consistency:** `validateManifest` signature is `(manifestYaml: string, inputs: ValidatorInputs) => ValidationResult` in both the test file and the implementation. `ValidatorInputs` shape (`{ secretCatalogYaml, integrationsAllowlistYaml }`) is consistent across all 8 tests.

No issues found.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-15-sp0-plan-a-foundation-scaffolding.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Each of the 7 tasks gets its own context, so a single task's debugging doesn't blow up the main session.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Faster end-to-end but burns more context.

Which approach?
