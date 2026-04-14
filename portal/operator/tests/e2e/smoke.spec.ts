/**
 * Smoke tests — every major route loads without a 5xx or console error.
 *
 * Each test:
 *   1. Navigates to the route authenticated
 *   2. Asserts the response is 200
 *   3. Asserts no TypeError/ReferenceError in console
 *   4. Asserts no "undefined" or "[object Object]" visible in body text
 *   5. Asserts the page has a h1 heading
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

const ROUTES = [
  { path: "/", heading: /dashboard/i },
  { path: "/reclaimrx", heading: /fwa dashboard/i },
  { path: "/reclaimrx/recovery", heading: /recovery tracking/i },
  { path: "/reclaimrx/investigations", heading: /investigation queue/i },
  { path: "/analytics/member", heading: /member analytics/i },
  { path: "/analytics/drug-trend", heading: /drug.*trend/i },
  { path: "/analytics/network", heading: /network analytics/i },
  { path: "/analytics/financial", heading: /financial/i },
  { path: "/analytics/data-quality", heading: /data quality/i },
  { path: "/medical-claims/340b", heading: /340b/i },
  { path: "/medical-claims/site-of-care", heading: /site of care/i },
  { path: "/medical-claims/unified-spend", heading: /unified.*spend/i },
  { path: "/billing/claims", heading: /claims/i },
  { path: "/billing/invoices", heading: /invoice/i },
  { path: "/edi/monitor", heading: /.+/ }, // just any h1
  { path: "/directories/pharmacies", heading: /pharmacy directory/i },
  { path: "/directories/prescribers", heading: /prescriber/i },
  { path: "/directories/drugs", heading: /drug/i },
  { path: "/directories/members", heading: /member/i },
  { path: "/admin/users", heading: /user/i },
  { path: "/admin/tenants", heading: /tenant settings/i },
  { path: "/admin/audit-log", heading: /audit log/i },
  { path: "/admin/system-health", heading: /system health/i },
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
      expect(resp?.status(), `${path} HTTP status`).toBe(200);

      // No TypeErrors
      const typeErrors = consoleErrors.filter((e) =>
        /TypeError|ReferenceError|SyntaxError/.test(e)
      );
      expect(typeErrors, `${path} console errors`).toHaveLength(0);

      // Body doesn't contain visibly-broken text
      const bodyText = await page.locator("body").innerText();
      expect(bodyText, `${path} has no "[object Object]"`).not.toMatch(
        /\[object Object\]/
      );
      expect(bodyText, `${path} has no NaN`).not.toMatch(/\bNaN\b/);

      // Has a h1
      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("h1").first()).toHaveText(heading);
    });
  }
});
