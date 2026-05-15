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
