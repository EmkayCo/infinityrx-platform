/**
 * DB cleanup helper for PaySync Playwright E2E tests.
 *
 * Provides the truncation order for billing tables (children first, parents
 * last) and a helper that calls the billing seed endpoint's cleanup path.
 *
 * Direct DB access is not available from the browser process; the cleanup
 * helper calls the backend seed endpoint with cleanup=true, which runs the
 * TRUNCATE sequence server-side. This keeps the helper environment-agnostic
 * (no pg driver dependency in the browser context).
 */

/**
 * Billing tables in dependency order for TRUNCATE (children first).
 * Order is enforced by the db-cleanup.test.ts assertions.
 *
 * Schema prefix matches the PostgreSQL schema name used in billing migrations.
 */
export const BILLING_TRUNCATE_ORDER: readonly string[] = [
  "billing.file_artifacts",
  "billing.payment_runs",
  "billing.payment_batches",
  "billing.journal_entries",
  "billing.reconciliations",
  "billing.invoices",
  "billing.carryovers",
  "billing.bank_settlements",
  "billing.uploads",
  "billing.payment_cycles",
] as const;

export interface DbCleanupOptions {
  /** Base URL of the billing backend, e.g. "http://localhost:8001". */
  baseURL: string;
  /** Tenant ID whose data should be truncated. */
  tenantId?: string;
  /** Bearer token (test-auth JWT). */
  token?: string;
}

/**
 * Truncates all billing tables for the given tenant by calling the billing
 * seed endpoint with cleanup=true.
 *
 * Intended for Playwright afterAll hooks so each test suite starts clean.
 * Silently ignores 404 (no data to clean) but throws on other errors.
 */
export async function cleanupBillingData(opts: DbCleanupOptions): Promise<void> {
  const { baseURL, tenantId = "t0000000-0000-0000-0000-000000000001", token } = opts;
  const url = `${baseURL}/api/v1/billing/seed`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Tenant-ID": tenantId,
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    method: "DELETE",
    headers,
    body: JSON.stringify({ tenant_id: tenantId }),
  });

  if (response.status === 404) {
    return; // nothing to clean
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      `cleanupBillingData: DELETE ${url} returned ${response.status} — ${JSON.stringify(body)}`
    );
  }
}
