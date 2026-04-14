/**
 * Auth boundary E2E tests.
 *
 * Verifies:
 *   - Every protected route redirects unauthenticated users to /login
 *   - The redirect preserves the original path in ?callbackUrl=
 *   - Dev-bypass login succeeds
 *   - After login, protected routes render (no redirect)
 *   - Forged x-ifx-authenticated header is stripped by middleware
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

const PROTECTED = ["/", "/reclaimrx", "/billing/claims", "/admin/users", "/settings/profile"];

test.describe("Auth — unauthenticated", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  for (const path of PROTECTED) {
    test(`${path} redirects to /login with callbackUrl preserved`, async ({ page }) => {
      const resp = await page.goto(path, { waitUntil: "domcontentloaded" });
      expect(resp?.status()).toBeLessThan(400);
      expect(page.url()).toContain("/login");
      expect(page.url()).toContain(`callbackUrl=${encodeURIComponent(path)}`);
    });
  }

  test("/login itself is accessible", async ({ page }) => {
    const resp = await page.goto("/login");
    expect(resp?.status()).toBe(200);
    expect(page.url()).toMatch(/\/login$/);
  });

  test("forged x-ifx-authenticated: 1 header still redirects (middleware strips it)", async ({
    request,
  }) => {
    const resp = await request.get("/admin/users", {
      headers: { "x-ifx-authenticated": "1" },
      maxRedirects: 0,
    });
    // Should be a 307 redirect to /login, NOT a 200
    expect(resp.status()).toBe(307);
    expect(resp.headers().location).toContain("/login");
  });
});

test.describe("Auth — dev-bypass", () => {
  test("dev-bypass authenticates and protected routes become reachable", async ({
    browser,
  }) => {
    const context = await browser.newContext();
    await authenticateDevBypass(context, "http://localhost:3000");

    const page = await context.newPage();
    await page.goto("/");
    // After auth, `/` should not redirect to /login
    expect(page.url()).not.toContain("/login");

    // Session endpoint returns a real user
    const sessionResp = await context.request.get("/api/auth/session");
    const session = await sessionResp.json();
    expect(session.user).toBeDefined();
    expect(session.user.email).toBe("dev@infinityrx.local");
    expect(session.user.role).toBe("platform_admin");

    await context.close();
  });

  test("session persists across multiple route navigations", async ({ browser }) => {
    const context = await browser.newContext();
    await authenticateDevBypass(context, "http://localhost:3000");

    const page = await context.newPage();
    for (const route of ["/", "/reclaimrx", "/billing/claims", "/admin/users"]) {
      const resp = await page.goto(route, { waitUntil: "domcontentloaded" });
      expect(resp?.status()).toBe(200);
      expect(page.url(), `after navigating to ${route}`).not.toContain("/login");
    }
    await context.close();
  });
});
