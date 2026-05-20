/**
 * Auth helpers for PaySync Playwright E2E tests.
 *
 * Produces JWT tokens for fixture users by calling the test-auth shortcut
 * endpoint (POST /api/v1/core/test-auth/token). That endpoint is guarded by
 * INFINITYRX_ENV and blocked in production.
 *
 * User IDs match packages/modules/paysync/fixtures/seeds/users.json.
 */

/** alice.operator@demo.infinityrx.test */
export const OPERATOR_USER_ID = "usr-00000000-0000-0000-0000-000000000001";
/** bob.approver@demo.infinityrx.test */
export const APPROVER_USER_ID = "usr-00000000-0000-0000-0000-000000000002";
/** carol.auditor@demo.infinityrx.test */
export const AUDITOR_USER_ID = "usr-00000000-0000-0000-0000-000000000003";

export interface TestAuthOptions {
  /** Base URL of core-platform backend, e.g. "http://localhost:8000". */
  baseURL: string;
  /** Fixture user ID from users.json. Use OPERATOR_USER_ID etc. */
  userId: string;
  /** Tenant ID — defaults to the canonical demo tenant. */
  tenantId?: string;
}

export interface TestAuthResponse {
  access_token: string;
  token_type: string;
}

/** Canonical demo tenant. */
export const DEMO_TENANT_ID = "t0000000-0000-0000-0000-000000000001";

/**
 * Fetches a JWT for the given fixture user from the test-auth shortcut
 * endpoint. Throws on any non-2xx response.
 *
 * In Playwright tests, call this inside beforeAll or at the start of each
 * role block and store the token in local storage / request headers via
 * injectJwtIntoContext().
 */
export async function fetchTestAuthToken(opts: TestAuthOptions): Promise<string> {
  const { baseURL, userId, tenantId = DEMO_TENANT_ID } = opts;
  const url = `${baseURL}/api/v1/core/test-auth/token`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, tenant_id: tenantId }),
  });

  const body = (await response.json().catch(() => null)) as TestAuthResponse | null;

  if (!response.ok) {
    throw new Error(
      `fetchTestAuthToken: POST ${url} returned ${response.status} — ${JSON.stringify(body)}`
    );
  }

  if (!body?.access_token) {
    throw new Error(`fetchTestAuthToken: response missing access_token — ${JSON.stringify(body)}`);
  }

  return body.access_token;
}

/**
 * Injects a JWT token into a Playwright BrowserContext so all subsequent
 * requests include the Authorization header and the NextAuth session cookie
 * recognises the fixture user.
 *
 * Strategy: sets localStorage["auth-token"] and the Authorization header via
 * page.setExtraHTTPHeaders() after navigation to the base URL. The operator
 * portal's auth middleware reads this token on every request.
 */
export async function injectJwtIntoContext(
  context: import("@playwright/test").BrowserContext,
  token: string,
  portalBaseURL = "http://localhost:3000"
): Promise<void> {
  await context.addInitScript((t) => {
    // Store in localStorage so the Next.js auth layer picks it up on hydration.
    window.localStorage.setItem("irx-e2e-token", t);
  }, token);

  // Also add the Authorization header to every API call the browser makes
  // during the test session so backend services accept the fixture JWT.
  await context.setExtraHTTPHeaders({
    Authorization: `Bearer ${token}`,
    "X-E2E-Test": "1",
  });

  // Silence TypeScript — portalBaseURL is used by callers for context setup.
  void portalBaseURL;
}
