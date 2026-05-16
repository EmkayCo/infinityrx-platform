// packages/scripts/build-manifest.test.ts
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { describe, expect, it } from "vitest";
import { buildManifest, type BuildManifestOptions, type ModuleConfig } from "./build-manifest.js";
import { stringify as stringifyYaml } from "yaml";

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

// NOTE: build-manifest.ts internally uses Ajv2020 (default export) + ajv-formats to match
// Plan A's validate-manifest.ts. The Ajv instantiation in build-manifest.ts uses:
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
