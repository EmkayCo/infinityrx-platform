#!/usr/bin/env node
// packages/scripts/build-manifest.ts
// Usage: node --loader tsx packages/scripts/build-manifest.ts
// Env:   INFINITYRX_MANIFEST (path to instance YAML, default: infrastructure/manifests/operator-dev.yml)
//        INFINITYRX_GENERATED_OUT (output dir, default: packages/shell/src/_generated)

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createRequire } from "node:module";
// Use createRequire for ajv so that vitest/vite resolves from this package's local
// node_modules (ajv v8) rather than the workspace-root node_modules (ajv v6).
// STILL-OPEN-1: ajv/dist/2020.js CJS re-exports as both .Ajv2020 and .default.
const _require = createRequire(import.meta.url);

interface AjvInstance {
  validate(schema: unknown, data: unknown): boolean;
  errors?: Array<{ instancePath: string; message?: string }>;
}
interface AjvConstructor {
  new(opts?: Record<string, unknown>): AjvInstance;
}

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { Ajv2020 } = _require("ajv/dist/2020.js") as { Ajv2020: AjvConstructor };
// eslint-disable-next-line @typescript-eslint/no-require-imports
const addFormats = _require("ajv-formats") as (ajv: AjvInstance) => void;
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
  // Mix in each module.config.ts content for staleness detection.
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
  const schema = JSON.parse(readFileSync(schemaPath, "utf8")) as unknown;
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

  // 6d. Emit eslint-zones.mjs placeholder (overwritten by Task 2's generate-eslint-zones.ts).
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

if (import.meta.url === new URL(process.argv[1] ?? "", "file://").href ||
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
