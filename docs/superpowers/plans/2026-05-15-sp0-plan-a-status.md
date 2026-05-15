# SP-0 Plan A — Foundation Scaffolding — Acceptance Status

**Status:** Complete. `2026-05-15`

**Final commit:** `<see latest commit on this file>`

**Task SHAs (for traceability):**

| Task | Description | Final SHA |
|---|---|---|
| 1 | Repo-root workspace + packages/scripts scaffold (+ placeholder eslint.config.mjs + broadened .gitignore globs) | `a5b8a63` |
| 2 | Manifest JSON Schema (Draft 2020-12, SD-4 §3) | `46e50b0` |
| 3 | Example manifests + secret catalog + integrations allow-list | `b6ea334` |
| 4 | Manifest validator + 10 vitest tests (TDD) | `2d69d81` |
| 5 | Workspace-root ESLint with full SD-4 §4 import-boundary rules (+ .npmrc legacy-peer-deps + ajv overrides + validator ESM import fixes) | `4720be0` |
| 6 | GitHub Actions sp0-foundation workflow (continue-on-error on portal lint) | `59a8296` |
| 7 | Acceptance status doc (this file) | `<see latest commit on this file>` |

**What ships:**

- Repo-root `package.json` with `packages/*` + `portal/*` workspaces.
- `tsconfig.base.json` + workspace-root `tsconfig.json` with `verbatimModuleSyntax`, `strict`, `composite`.
- `.npmrc` with `engine-strict`, `save-exact`, `fund=false`, `legacy-peer-deps`.
- Workspace-root `eslint.config.mjs` with SD-4 §4 import-boundary rules — 17 no-restricted-syntax selectors covering 3 specifier shapes (package, relative-traversal, TS path-alias) across 5–6 forms each, plus the framework-import ban scoped to `packages/**`, plus the sentinel `import/no-restricted-paths` zone (Plan D populates).
- `schemas/instance-manifest.schema.json` — Draft 2020-12, Ajv strict mode, all 17 keys covered, `additionalProperties: false` at every level.
- `infrastructure/manifests/operator-dev.yml` (dev/full composition — empty modules in Plan A).
- `infrastructure/manifests/example-reclaimrx-standalone.yml` (reference shape for single-module customer).
- `infrastructure/secret-catalog.yml` (scope catalog: jwt, nextauth, db).
- `infrastructure/integrations.yml` (egress allow-list, empty).
- `packages/scripts/validate-manifest.ts` + 10 vitest tests covering JSON Schema gate, secret-catalog ownership, integrations allow-list, malformed catalog, malformed allow-list, audience enum, missing required keys, additionalProperties:false rejection, malformed secret URIs, unknown scopes.
- Root `package.json` `overrides` block pinning `ajv-formats.ajv` to 8.17.1 (deduplicates the ajv tree so `tsc -b` passes; leaves eslint's ajv@6 untouched).
- `.github/workflows/sp0-foundation.yml` — single Foundation job running lint:root + lint:portal-operator (non-blocking) + typecheck + manifest:validate + manifest:validate:standalone + scripts test.

**What is NOT in Plan A** (deferred to Plan B/C/D):

- Any `packages/contract`, `packages/auth`, `packages/ui`, `packages/qa-harness`, `packages/shell` implementation — Plan B starts with contract + auth.
- The `packages/modules/reclaimrx` reference module — Plan D.
- The composition codegen scripts (`generate-composition.ts`, `audit-composition.ts`, `generate-ci-matrix.ts`, `generate-eslint-zones.ts`) — Plan D.
- `portal/operator` modifications (mounting the shell + reference module) — Plan D.
- Composition CI matrix workflow — Plan D.
- The `import/no-restricted-paths` zones array population (currently sentinel-only) — Plan D's `scripts/generate-eslint-zones.ts`.

**Verification (executed at Task 7 acceptance time):**

| Command | Expected | Result |
|---|---|---|
| `npm ci` | clean install, no peer-dep errors | PASS |
| `npm run lint:root` | exit 0 (root ESLint over packages/scripts) | 0 |
| `npm run typecheck` | exit 0 (project references compile) | 0 |
| `npm run manifest:validate` | `✓ infrastructure/manifests/operator-dev.yml validates clean` | 0 |
| `npm run manifest:validate:standalone` | `✓ infrastructure/manifests/example-reclaimrx-standalone.yml validates clean` | 0 |
| `npm --workspace=@infinityrx/scripts test` | 10/10 vitest tests pass | 10/10 |

**Known pre-existing issues** (NOT introduced by Plan A; out-of-scope for foundation milestone):

- `npm run lint:portal-operator` exits non-zero on pre-existing portal/operator violations:
  ```
  portal/operator/app/analytics/claims/page.tsx
    168:43  warning  Unexpected console statement. Only these console methods are allowed: warn, error, log  no-console

  portal/operator/tests/e2e/b11-dogfood.spec.ts
    13:16  error  'expect' is defined but never used. Allowed unused vars must match /^_/u  @typescript-eslint/no-unused-vars

  portal/operator/tests/e2e/b11-w0_1-auth-write-isolation.spec.ts
    334:94  warning  Unexpected any. Specify a different type  @typescript-eslint/no-explicit-any

  ✖ 3 problems (1 error, 2 warnings)
  ```
- These are flagged in CI but the workflow uses `continue-on-error: true` on that step so the foundation job stays green. Fix should be tracked as a separate follow-up effort and the `continue-on-error` line removed once resolved.

**Plan A decision:** ready for Plan B (packages/contract + packages/auth) to be written and executed.

**References:**

- Main SP-0 spec: `docs/superpowers/specs/2026-05-14-sp0-integration-foundation-design.md` (`a50130f`)
- Plan A spec: `docs/superpowers/plans/2026-05-15-sp0-plan-a-foundation-scaffolding.md` (`424bd14`)
- Sub-decision 1 (auth): `2026-05-15-sp0-decision-spike-auth-interface.md` (`b876c3b`)
- Sub-decision 2 (framework): `2026-05-15-sp0-decision-spike-framework.md` (`14d847a`)
- Sub-decision 3 (gateway): `2026-05-15-sp0-decision-spike-gateway.md` (`daffdb0`)
- Sub-decision 4 (composition): `2026-05-15-sp0-decision-spike-composition.md` (`0b3c9d7`)
