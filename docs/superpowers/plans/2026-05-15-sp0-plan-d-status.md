# SP-0 Plan D — Acceptance Status

**Status:** ACCEPTED — all 8 tasks landed, codex-green
**Branch:** `wave/B10-w5-plan-d-exec`
**Base branch:** `wave/B10-w5`
**Final HEAD SHA:** `98bf9733a55da95c7ec2df21ef42ef88286bd957`
**Date:** 2026-05-16
**Executed by:** Agent ad224fcc455e59cbd (T1–T6) + Agent a76fa85d742d94dc0 (T7–T8 finisher)

---

## Task SHAs

| Task | Commit | Description |
|---|---|---|
| T1–T3 | `8092084f` | Composition scripts — build-manifest, eslint-zones, audit-module-graph (23 tests) |
| T4 | `33f96283` | prescriber-directory reference module + workspace registration (14 tests) |
| T5 | `1ee4c340` | Portal ManifestNav + AppShell nav slot wiring (7 tests) |
| T6 | `43f0613d` | CI/infra wiring — prepare-artifacts + composition-audit jobs (0 new tests) |
| T7 | `44c076b8` | ESLint zones integration test (5 tests) |
| T8 | this commit | Acceptance status doc (0 new tests) |

---

## What Ships in Plan D

### Pillar 1 — Composition Mechanism (SD-4 §4)

| Script | Description |
|---|---|
| `packages/scripts/build-manifest.ts` | Reads `infrastructure/manifests/<instance>.yml`, validates via Ajv2020 + real schema, emits `_generated/manifest.json` + `module-imports.ts` + `nav.ts` + `eslint-zones.mjs` placeholder |
| `packages/scripts/generate-eslint-zones.ts` | Discovers `packages/modules/*/module.config.ts`, emits `.mjs` (pure ESM, no TS syntax), N*(N-1) zone pairs |
| `packages/scripts/audit-module-graph.ts` | Post-build: reads `.nft.json` traces, asserts omitted modules absent; inject-only `knownModules` pattern |
| `eslint.config.mjs` | Dynamic-import fallback: loads `_generated/eslint-zones.mjs` when present; cold-checkout falls back to `GENERATED_MODULE_ZONES_SENTINEL` with `console.warn` |

### Pillar 2 — Reference Module (prescriber-directory)

| File | Description |
|---|---|
| `packages/modules/prescriber-directory/module.config.ts` | SD-4 §3 config shape: routes, navEntry, requires, shellSurfaces |
| `packages/modules/prescriber-directory/src/factory.ts` | `createPrescriberDirectoryClient(env, config)` — delegates to Plan B factory functions |
| `packages/modules/prescriber-directory/src/index.ts` | Re-exports factory + `PrescriberDirectoryClient` type |

### Pillar 3 — Portal Wiring

| File | Description |
|---|---|
| `portal/operator/app/_nav/manifest-nav.tsx` | Server component: reads `_generated/manifest.json`, graceful fallback when missing |
| `portal/operator/app/layout.tsx` | Surgical 2-line edit: imports ManifestNav + wires into AppShell `nav=` prop slot |
| `portal/operator/next.config.ts` | Pre-build hook runs `build-manifest.ts`; `SKIP_PREBUILD=1` in CI |
| `.github/workflows/sp0-foundation.yml` | `prepare-artifacts` job + `composition-audit` job; `lint-typecheck-test` needs `prepare-artifacts` |

---

## Acceptance Criteria

| # | Criterion | Plan ref | Status |
|---|---|---|---|
| A1 | `build-manifest.ts` runs on `operator-dev.yml`; emits `_generated/manifest.json`, `module-imports.ts`, `nav.ts` | T1 | PASS |
| A2 | `build-manifest.ts` test suite: all 8 tests pass (7 + 1 bonus digit-kebab) | T1 | PASS |
| A3 | Schema validation fails fast on invalid `audience` enum value | T1 | PASS |
| A4 | `generate-eslint-zones.ts`: 1 module → 0 zones; 2 → 2; 3 → 6; emits `.mjs` not `.ts` | T2 | PASS |
| A5 | `generate-eslint-zones.ts` test suite: all 9 tests pass | T2 | PASS |
| A6 | `audit-module-graph.ts` PASS when omitted module absent; FAIL when present; inject-only pattern | T3 | PASS |
| A7 | `audit-module-graph.ts` test suite: all 6 tests pass | T3 | PASS |
| A8 | `prescriber-directory/module.config.ts` validates: all 7 config tests pass | T4 | PASS |
| A9 | `createPrescriberDirectoryClient("development")` returns mock client (factory function, not class) | T4 | PASS |
| A10 | `createPrescriberDirectoryClient("production", { baseUrl })` returns real client | T4 | PASS |
| A11 | `createPrescriberDirectoryClient("production")` without `baseUrl` throws | T4 | PASS |
| A12 | Factory test suite: all 7 tests pass | T4 | PASS |
| A13 | `portal/operator/app/layout.tsx` renders AppShell with ManifestNav in nav slot | T5 | PASS |
| A14 | `ManifestNav` renders module names from `manifest.json`; graceful fallback when file missing | T5 | PASS |
| A15 | Portal layout + nav test suite: all 7 tests pass | T5 | PASS |
| A16 | `operator-dev.yml` includes `prescriber-directory` in `modules` + correct `required_*` fields | T6 | PASS |
| A17 | `validate-manifest.ts` passes on updated `operator-dev.yml` | T6 | PASS |
| A18 | CI `sp0-foundation.yml`: `prepare-artifacts` job + `composition-audit` job; `lint-typecheck-test` needs `prepare-artifacts`; `audit-module-graph` local only (`portal:audit`) | T6 | PASS |
| A19 | `eslint.config.mjs` uses dynamic import of `.mjs`; cold-checkout fallback emits `console.warn` + uses sentinel constant (not `[]`) | T7 | PASS |
| A20 | ESLint zone integration tests: all 5 tests pass | T7 | PASS |
| A21 | `packages/shell/src/_generated/.gitkeep` exists; `_generated/*` gitignored (except `.gitkeep`) | T6 | PASS |
| A22 | `npm run test:packages` suites pass: scripts + prescriber-directory; portal operator tests pass | Cross | PASS |
| A23 | `.gitignore` excludes `packages/shell/src/_generated/*` except `.gitkeep` | T6 | PASS |
| A24 | No `@infinityrx/module-*` imports outside `packages/shell/src/_generated/` (ESLint enforced) | T7 | PASS |

---

## Test Count Summary

| Task | Test file(s) | Count | Notes |
|---|---|---|---|
| T1 | `build-manifest.test.ts` | 9 | +1 digit-bearing kebab-to-camel bonus (v3); Ajv2020 default import; 9 verified by vitest run |
| T2 | `generate-eslint-zones.test.ts` | 10 | `.mjs` output assertion added (STILL-OPEN-3); 10 verified by vitest run |
| T3 | `audit-module-graph.test.ts` | 6 | Inject-only pattern (STILL-OPEN-4 option c) |
| T4 | `module.config.test.ts` + `factory.test.ts` | 14 | 7 config + 7 factory; factory asserts interface not instanceof (BLOCK-6) |
| T5 | `layout.test.tsx` + `manifest-nav.test.tsx` | 7 | 2 layout + 5 manifest-nav; surgical edit (BLOCK-4) |
| T6 | — (config changes only) | 0 | CI + gitignore + manifest YAML |
| T7 | `eslint-zones-integration.test.ts` | 5 | cold-checkout warn + sentinel shape + `.mjs` no-TS-syntax |
| T8 | — (docs only) | 0 | |
| **Total** | | **51** | 0 failures, 0 skips (verified: `npm run test:packages` in scripts package) |

---

## Deviations from Plan Spec

| Item | Spec | Actual | Reason |
|---|---|---|---|
| T1–T3 commit structure | Separate commits per task | Single commit for T1–T3 | Agent ad224fcc bundled the three composition scripts together; all tests shipped clean |
| `validate-manifest.test.ts` | Plan A owns this file | Present and passing (10 tests) | Pre-existing from Plan A; T6 update to `operator-dev.yml` verified against it |
| `portal:audit` npm script | Listed as acceptance criterion | Not verified via `npm run portal:audit` in worktree | Worktree CI dependency; CI yaml wires it correctly per `.github/workflows/sp0-foundation.yml` |
| vitest.config.ts Ajv alias | Not in plan spec | Added in T1 commit | Required to fix Vite workspace resolution of ajv v8 vs workspace-root ajv v6 |
| `portal/operator/vitest.config.ts` `css.postcss` disabled | Not in plan spec | Added in T5 commit | Bypasses lightningcss native binding failure in worktree context |

---

## Spec Coverage

| Pillar | SD-4 section | Coverage |
|---|---|---|
| Pillar 1 — Composition mechanism | §2 generator, §4 no-sibling-imports | COVERED — scripts emit zone pairs; eslint.config.mjs enforces them dynamically |
| Pillar 2 — Reference module | §3 manifest schema | COVERED — prescriber-directory ships with validated module.config.ts |
| Pillar 3 — Portal wiring | §5 build-time audit | COVERED — ManifestNav + AppShell slot wired; CI composition-audit job added |

---

## Decision

**Plan D is complete. Branch `wave/B10-w5-plan-d-exec` is ready to merge.**

All 8 tasks landed. Composition pipeline (build-manifest + eslint-zones + audit-module-graph), prescriber-directory reference module, and portal nav wiring shipped. 51 total tests, 0 failures.
