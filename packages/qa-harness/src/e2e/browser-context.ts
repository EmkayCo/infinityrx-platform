/**
 * Browser context factory for PaySync Playwright E2E tests.
 *
 * Creates a Playwright BrowserContext pre-configured for a given fixture user:
 * - Fetches a test-auth JWT for the user from core-platform
 * - Injects the JWT via localStorage + extra HTTP headers
 * - Returns the context ready for page navigation
 *
 * Roles are switched by calling createPaysyncContext() with a different userId.
 * Do not use RoleSwitcherChip for role switching in E2E tests — it is a
 * dev-panel component excluded from production bundles.
 */

import { fetchTestAuthToken, injectJwtIntoContext, DEMO_TENANT_ID } from "./auth-helpers.js";

/** Default base URLs. Override via env vars in CI. */
export const PAYSYNC_E2E_BASE_URLS = {
  portal: process.env["PORTAL_BASE_URL"] ?? "http://localhost:3000",
  billing: process.env["BILLING_BASE_URL"] ?? "http://localhost:8001",
  core: process.env["CORE_BASE_URL"] ?? "http://localhost:8000",
} as const;

export interface PaysyncContextOptions {
  /** Playwright Browser instance. */
  browser: import("@playwright/test").Browser;
  /**
   * Fixture user ID from users.json.
   * Use OPERATOR_USER_ID / APPROVER_USER_ID / AUDITOR_USER_ID from auth-helpers.
   */
  userId: string;
  /** Tenant ID. Defaults to canonical demo tenant. */
  tenantId?: string;
  /** Base URLs. Defaults to PAYSYNC_E2E_BASE_URLS. */
  baseURLs?: typeof PAYSYNC_E2E_BASE_URLS;
}

export interface PaysyncContext {
  context: import("@playwright/test").BrowserContext;
  page: import("@playwright/test").Page;
  token: string;
}

/**
 * Creates a Playwright BrowserContext authenticated as the given fixture user.
 *
 * Usage in Playwright test:
 *   const { page, context } = await createPaysyncContext({ browser, userId: OPERATOR_USER_ID });
 *   await page.goto("/admin/paysync");
 *   // ... test steps ...
 *   await context.close();
 */
export async function createPaysyncContext(
  opts: PaysyncContextOptions
): Promise<PaysyncContext> {
  const {
    browser,
    userId,
    tenantId = DEMO_TENANT_ID,
    baseURLs = PAYSYNC_E2E_BASE_URLS,
  } = opts;

  const token = await fetchTestAuthToken({
    baseURL: baseURLs.core,
    userId,
    tenantId,
  });

  const context = await browser.newContext({
    baseURL: baseURLs.portal,
    extraHTTPHeaders: {
      Authorization: `Bearer ${token}`,
      "X-E2E-Test": "1",
      "X-Tenant-ID": tenantId,
    },
  });

  await injectJwtIntoContext(context, token, baseURLs.portal);

  const page = await context.newPage();

  return { context, page, token };
}
