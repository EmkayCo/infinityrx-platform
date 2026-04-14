import type { Session } from "next-auth";

/**
 * Returns a valid NextAuth session object matching the shape returned by
 * /api/auth/session in the dev-bypass flow.
 */
export function mockSession(): Session {
  return {
    user: {
      id: "dev-admin-00000000-0000-0000-0000-000000000001",
      email: "dev@infinityrx.local",
      name: "Dev Admin",
      role: "platform_admin",
      tenant_id: "00000000-0000-0000-0000-000000000001",
      permissions: ["*"],
      mfa_enrolled: true,
    },
    expires: new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString(),
  } as unknown as Session;
}

/**
 * Playwright helper: authenticates a browser context via the dev-bypass
 * credentials provider, returning after the session cookie is set.
 *
 * Retries once with a short delay if /api/auth/csrf returns a non-JSON body —
 * this happens occasionally when the Next.js dev server is mid-compile during
 * test startup and returns an HTML error page.
 */
export async function authenticateDevBypass(
  context: import("@playwright/test").BrowserContext,
  baseURL = "http://localhost:3000"
): Promise<void> {
  let csrfToken: string | undefined;
  let lastError: unknown;

  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const csrfResp = await context.request.get(`${baseURL}/api/auth/csrf`);
      if (csrfResp.status() !== 200) {
        throw new Error(`CSRF endpoint returned status ${csrfResp.status()}`);
      }
      const contentType = csrfResp.headers()["content-type"] ?? "";
      if (!contentType.includes("application/json")) {
        const body = await csrfResp.text();
        throw new Error(
          `CSRF endpoint returned non-JSON content-type="${contentType}", body starts: ${body.slice(0, 100)}`
        );
      }
      const parsed = (await csrfResp.json()) as { csrfToken?: string };
      if (!parsed.csrfToken) {
        throw new Error(`CSRF response missing csrfToken field: ${JSON.stringify(parsed)}`);
      }
      csrfToken = parsed.csrfToken;
      break;
    } catch (err) {
      lastError = err;
      if (attempt < 2) {
        await new Promise((r) => setTimeout(r, 1500));
      }
    }
  }

  if (!csrfToken) {
    throw new Error(
      `authenticateDevBypass: could not fetch CSRF token after 3 attempts. Last error: ${String(lastError)}`
    );
  }

  await context.request.post(`${baseURL}/api/auth/callback/dev-bypass`, {
    form: {
      csrfToken,
      callbackUrl: "/",
      json: "true",
    },
    maxRedirects: 0,
  });
}
