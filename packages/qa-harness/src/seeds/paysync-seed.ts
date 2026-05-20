/**
 * PaySync fixture seed loader for the QA harness.
 *
 * Calls POST /api/v1/billing/seed on the billing backend, which reads the
 * committed JSON fixtures from packages/modules/paysync/fixtures/seeds/ and
 * inserts them into the test DB (idempotent by primary key).
 *
 * Dev/staging only. Never import from production code. Tree-shaking
 * enforcement is verified by the CI bundle check added in Task 4.
 */

export interface PaysyncSeedOptions {
  /** Base URL of the billing backend, e.g. "http://localhost:8001". */
  baseURL: string;
  /**
   * Tenant ID for the seeded records. Defaults to the canonical demo tenant
   * from packages/modules/paysync/fixtures/seeds/tenant.json.
   */
  tenantId?: string;
  /**
   * Bearer token for the seed endpoint. In Playwright tests this is a
   * test-auth JWT from POST /api/v1/core/test-auth/token.
   */
  token?: string;
}

export interface PaysyncSeedResult {
  ok: boolean;
  status: number;
  body: unknown;
}

/** Canonical demo tenant committed in fixtures/seeds/tenant.json */
export const DEMO_TENANT_ID = "t0000000-0000-0000-0000-000000000001";

/**
 * Seeds all paysync fixture data via the billing seed endpoint.
 * Throws on network errors or non-2xx responses so Playwright beforeAll
 * surfaces a clear failure rather than cascading missing-data errors.
 */
export async function seedPaysync(opts: PaysyncSeedOptions): Promise<PaysyncSeedResult> {
  const { baseURL, tenantId = DEMO_TENANT_ID, token } = opts;
  const url = `${baseURL}/api/v1/billing/seed`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify({ tenant_id: tenantId }),
  });

  const body: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(
      `seedPaysync: POST ${url} returned ${response.status} — ${JSON.stringify(body)}`
    );
  }

  return { ok: true, status: response.status, body };
}

/**
 * SeedBinding descriptor for use with the FactoryBindings component.
 * Pass in the bindings array; call seedPaysync inside the seed callback
 * when kind === "paysync".
 */
export const PAYSYNC_SEED_BINDING = {
  kind: "paysync",
  label: "Seed PaySync fixtures (tenant + uploads + cycles + batches + invoices + files + journal)",
} as const;
