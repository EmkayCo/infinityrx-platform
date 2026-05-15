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
