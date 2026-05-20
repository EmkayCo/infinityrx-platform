/**
 * Wave 40 paysync route smoke tests.
 *
 * Asserts each new paysync + network management page loads cleanly
 * (200 / no TypeError / has h1 / no broken text). Backend API calls
 * are mocked at the network layer; these tests validate the UI shell
 * and route table — not full operator flows. Full flow tests live in
 * paysync-flows.spec.ts (gated behind a backend fixture).
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

const PAYSYNC_ROUTES = [
  { path: "/admin/paysync", heading: /paysync dashboard/i },
  { path: "/admin/paysync/cycles", heading: /cycles/i },
  { path: "/admin/paysync/batches", heading: /payment batches/i },
  { path: "/admin/paysync/invoices", heading: /invoices/i },
  { path: "/admin/paysync/reconciliations", heading: /reconciliations/i },
  { path: "/admin/paysync/carryovers", heading: /carryovers/i },
  { path: "/admin/paysync/bank-settlements", heading: /bank settlements/i },
  { path: "/admin/paysync/bank-settlements/manual-entry", heading: /manual settlement entry/i },
  { path: "/admin/paysync/manual-ap", heading: /manual ap records/i },
  { path: "/admin/paysync/echo", heading: /echo spec 400/i },
  { path: "/admin/paysync/setup/cycle-schedules", heading: /cycle schedules/i },
  { path: "/admin/paysync/setup/export-templates", heading: /export templates/i },
  { path: "/admin/paysync/setup/email-templates", heading: /email templates/i },
  { path: "/admin/paysync/setup/email-recipients", heading: /email recipients/i },
  { path: "/admin/paysync/setup/gl-account-mappings", heading: /gl account mappings/i },
  { path: "/admin/paysync/setup/invoice-sequences", heading: /invoice sequences/i },
  { path: "/admin/network/pay-to-entities", heading: /pay-to entities/i },
  { path: "/admin/network/banking-discrepancies", heading: /banking discrepancies/i },
  { path: "/admin/network/tenant-ach-origination", heading: /tenant ach origination/i },
  { path: "/admin/network/chain-membership", heading: /chain membership/i },
];

test.beforeEach(async ({ context, page }) => {
  await authenticateDevBypass(context, "http://localhost:3000");

  // Mock paysync API — every list endpoint returns an empty page; every
  // detail endpoint 404s. Smoke tests don't exercise data, just the UI
  // shell.
  await page.route(/\/admin\/(paysync|network)\/.+/, async (route) => {
    const url = route.request().url();
    const isPaginated = /\/(cycles|batches|invoices|carryovers|bank-settlements|pay-to-entities|banking-discrepancy-reviews|manual-ap-records)(\?|$)/.test(url);
    if (isPaginated) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], total: 0, page: 1, page_size: 50 }),
      });
    }
    if (url.endsWith("/dashboard")) {
      return route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          open_cycles_count: 0,
          open_cycles_claim_count: 0,
          pending_close_count: 0,
          pending_reconciliation_count: 0,
          open_carryovers_count: 0,
          open_carryovers_we_owe: "0.00",
          open_carryovers_pharmacy_owes: "0.00",
          banking_discrepancies_pending: 0,
          recent_activity: [],
        }),
      });
    }
    if (url.endsWith("/tenant-ach-origination")) {
      return route.fulfill({
        status: 200, contentType: "application/json", body: "null",
      });
    }
    return route.fulfill({
      status: 200, contentType: "application/json", body: "[]",
    });
  });
});

test.describe("PaySync route smoke", () => {
  for (const { path, heading } of PAYSYNC_ROUTES) {
    test(`${path} loads cleanly`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

      const resp = await page.goto(path, { waitUntil: "networkidle", timeout: 30_000 });
      expect([200, 307]).toContain(resp?.status() ?? 0);

      const typeErrors = consoleErrors.filter((e) =>
        /TypeError|ReferenceError|SyntaxError/.test(e));
      expect(typeErrors, `${path} console errors`).toHaveLength(0);

      const bodyText = await page.locator("body").innerText();
      expect(bodyText).not.toMatch(/\[object Object\]/);
      expect(bodyText).not.toMatch(/\bNaN\b/);

      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("h1").first()).toHaveText(heading);
    });
  }
});
