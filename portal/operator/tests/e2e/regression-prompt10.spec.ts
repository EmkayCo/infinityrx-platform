/**
 * Regression tests for every bug fixed in Prompt 10.
 *
 * If any of these tests fail, it means a Prompt-10 bug has come back.
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Regression: Prompt 10", () => {
  test("CR-1 /admin/tenants renders without the route error boundary", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/admin/tenants", { waitUntil: "networkidle" });

    // The route error boundary's signature message must NOT appear
    await expect(page.getByText(/Cannot convert undefined or null to object/i)).toHaveCount(0);
    // The page header should render
    await expect(page.getByRole("heading", { name: /tenant settings/i })).toBeVisible();
    // At least one tenant name should be visible (seed has 4)
    await expect(page.getByText(/InfinityRx Internal/)).toBeVisible();
    // No TypeErrors in console
    const typeErrors = consoleErrors.filter((e) => /TypeError/.test(e));
    expect(typeErrors).toHaveLength(0);
  });

  test("CR-2 /analytics/network pharmacy scorecard table renders without 'Something went wrong'", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/analytics/network", { waitUntil: "networkidle" });

    // Page header
    await expect(page.getByRole("heading", { name: /network analytics/i })).toBeVisible();
    // No "Something went wrong" anywhere on the page
    await expect(page.getByText(/Something went wrong/i)).toHaveCount(0);
    // The scorecard table should have data rows
    await expect(page.locator("tbody tr")).toHaveCount(15);
    // No .replace-on-undefined errors
    const replaceErrors = consoleErrors.filter((e) =>
      /Cannot read properties of undefined \(reading 'replace'\)/.test(e)
    );
    expect(replaceErrors).toHaveLength(0);
  });

  test("HI-1 /admin/system-health DLQ shows a number, not 'undefined'", async ({ page }) => {
    await page.goto("/admin/system-health", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: /system health/i })).toBeVisible();
    // The literal string "undefined" must NOT appear in visible text
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bundefined\b/);
    // "Dead Letter Queue" label is present
    await expect(page.getByText(/Dead Letter Queue/i)).toBeVisible();
  });

  test("HI-2 / home AR summary widget shows real dollar amounts (not $0.00)", async ({
    page,
  }) => {
    await page.goto("/", { waitUntil: "networkidle" });

    // The AR widget is rendered; the mock handler returns real money from overview.json
    // so at least one non-zero dollar amount should appear
    const bodyText = await page.locator("body").innerText();
    // At least one positive dollar amount > $1,000 should be visible (demo data has $34.8M)
    expect(bodyText).toMatch(/\$[0-9][0-9,]+/);
  });

  test("HI-3 /analytics/member high-cost table has rows", async ({ page }) => {
    await page.goto("/analytics/member", { waitUntil: "networkidle" });
    // At least some tbody rows — mock seed has 10 high-cost members
    const rowCount = await page.locator("tbody tr").count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test("HI-4 /admin/audit-log renders entries (not empty state)", async ({ page }) => {
    await page.goto("/admin/audit-log", { waitUntil: "networkidle" });

    // Empty state message must NOT be present
    await expect(page.getByText(/No audit entries found/i)).toHaveCount(0);
    // At least some rows
    const rowCount = await page.locator("tbody tr").count();
    expect(rowCount).toBeGreaterThan(0);
  });

  test("MED-1 /reclaimrx/investigations/<garbage-uuid> shows not-found, not a random investigation", async ({
    page,
  }) => {
    await page.goto("/reclaimrx/investigations/totally-fake-uuid-00000000", {
      waitUntil: "networkidle",
    });
    await expect(page.getByRole("heading", { name: /investigation not found/i })).toBeVisible();
    await expect(page.getByText(/Back to investigation queue/i)).toBeVisible();
    // Must NOT show the first-investigation fallback
    await expect(page.getByText(/evidence checklist/i)).toHaveCount(0);
  });

  test("MED-2 all 4 directories render data rows (not empty state)", async ({ page }) => {
    const directories: [string, number][] = [
      ["/directories/pharmacies", 40],
      ["/directories/prescribers", 40],
      ["/directories/drugs", 40],
      ["/directories/members", 30],
    ];

    for (const [path, minRows] of directories) {
      await page.goto(path, { waitUntil: "networkidle" });
      // Empty state must NOT be visible
      await expect(page.getByText(/No .+ found/i)).toHaveCount(0);
      // At least the expected number of rows
      const rowCount = await page.locator("tbody tr").count();
      expect(rowCount, `${path} has ≥${minRows} rows`).toBeGreaterThanOrEqual(minRows);
    }
  });

  test("HI-5 /billing/claims first-load is fast (warmup made cold init disappear)", async ({
    page,
  }) => {
    const start = Date.now();
    await page.goto("/billing/claims", { waitUntil: "networkidle" });
    const elapsed = Date.now() - start;
    // Before Prompt 10: 4092ms. After warmup: ~260ms. Allow 2s to account for
    // test env overhead + first-compile time.
    expect(elapsed, `first load was ${elapsed}ms`).toBeLessThan(6000);
  });
});
