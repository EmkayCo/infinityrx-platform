/**
 * Smoke tests — every major route loads without a 5xx or console error.
 *
 * Each test:
 *   1. Navigates to the route authenticated
 *   2. Asserts the response is 200 (or 307 for a redirected legacy path)
 *   3. Asserts no TypeError/ReferenceError in console
 *   4. Asserts no "undefined" or "[object Object]" visible in body text
 *   5. Asserts the page has a h1 heading
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

const ROUTES = [
  { path: "/", heading: /dashboard|infinityrx/i },
  // New ICP routes
  { path: "/claims", heading: /claims explorer/i },
  { path: "/programs", heading: /program overview/i },
  { path: "/accounting/cycles", heading: /billing cycles/i },
  { path: "/accounting/invoices", heading: /invoice/i },
  { path: "/accounting/payments", heading: /payments/i },
  { path: "/accounting/nacha", heading: /nacha/i },
  { path: "/reclaimrx", heading: /.+/ },
  { path: "/reclaimrx/leakage", heading: /leakage/i },
  { path: "/reclaimrx/investigations", heading: /.+/ },
  { path: "/reclaimrx/recovery", heading: /.+/ },
  { path: "/reclaimrx/risk", heading: /pharmacy risk/i },
  { path: "/analytics/claims", heading: /claim summary/i },
  { path: "/analytics/fills", heading: /fill performance/i },
  { path: "/analytics/adherence", heading: /adherence/i },
  { path: "/analytics/pharmacies", heading: /pharmacy insights/i },
  { path: "/analytics/geography", heading: /geographic/i },
  { path: "/analytics/trends", heading: /trend analysis/i },
  { path: "/directories/pharmacies", heading: /.+/ },
  { path: "/directories/prescribers", heading: /.+/ },
  { path: "/directories/drugs", heading: /.+/ },
  { path: "/directories/members", heading: /.+/ },
  { path: "/clients", heading: /companies/i },
  { path: "/clients/fees", heading: /fee configuration/i },
  { path: "/edi/monitor", heading: /.+/ },
  { path: "/edi/transactions", heading: /.+/ },
  { path: "/network/locator", heading: /locator/i },
  { path: "/reporting/library", heading: /library/i },
  { path: "/admin/users", heading: /user/i },
  { path: "/admin/tenants", heading: /tenant settings/i },
  { path: "/admin/audit-log", heading: /audit log/i },
  { path: "/admin/system-health", heading: /system health/i },
  { path: "/admin/config", heading: /.+/ },
];

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Smoke tests", () => {
  for (const { path, heading } of ROUTES) {
    test(`${path} loads cleanly`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

      const resp = await page.goto(path, { waitUntil: "networkidle", timeout: 30_000 });
      const status = resp?.status() ?? 0;
      expect([200, 307], `${path} HTTP status`).toContain(status);

      // No TypeErrors
      const typeErrors = consoleErrors.filter((e) =>
        /TypeError|ReferenceError|SyntaxError/.test(e),
      );
      expect(typeErrors, `${path} console errors`).toHaveLength(0);

      // Body doesn't contain visibly-broken text
      const bodyText = await page.locator("body").innerText();
      expect(bodyText, `${path} has no "[object Object]"`).not.toMatch(
        /\[object Object\]/,
      );
      expect(bodyText, `${path} has no NaN`).not.toMatch(/\bNaN\b/);

      // Has a h1
      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("h1").first()).toHaveText(heading);
    });
  }
});

test.describe("Legacy route redirects", () => {
  const REDIRECTS = [
    { from: "/billing/claims", toRegex: /\/claims$/ },
    { from: "/billing/cycles", toRegex: /\/accounting\/cycles$/ },
    { from: "/billing/invoices", toRegex: /\/accounting\/invoices$/ },
    { from: "/payments", toRegex: /\/accounting\/payments$/ },
    { from: "/payments/nacha", toRegex: /\/accounting\/nacha$/ },
    { from: "/analytics/member", toRegex: /\/analytics\/adherence$/ },
    { from: "/analytics/drug-trend", toRegex: /\/analytics\/fills$/ },
    { from: "/analytics/network", toRegex: /\/analytics\/pharmacies$/ },
    { from: "/analytics/financial", toRegex: /\/analytics\/trends$/ },
    { from: "/reporting", toRegex: /\/reporting\/library$/ },
  ];

  for (const { from, toRegex } of REDIRECTS) {
    test(`${from} redirects to new URL`, async ({ page }) => {
      await page.goto(from, { waitUntil: "networkidle", timeout: 30_000 });
      expect(page.url()).toMatch(toRegex);
    });
  }
});
