/**
 * E2E tests for ReclaimRx GTN Dashboard
 * Tests: KPI card drill-down, GTN ratio display, top pharmacies table.
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("GTN Dashboard", () => {
  test("dashboard shows 6 GTN KPI cards with real values", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });

    // Check all 6 KPI card labels
    await expect(page.getByText(/total copay spend/i)).toBeVisible();
    await expect(page.getByText(/identified leakage/i)).toBeVisible();
    await expect(page.getByText(/gtn ratio/i)).toBeVisible();
    await expect(page.getByText(/active investigations/i)).toBeVisible();
    await expect(page.getByText(/recovered ytd/i)).toBeVisible();
    await expect(page.getByText(/recovery rate/i)).toBeVisible();

    // No NaN values on the page
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });

  test("GTN Ratio KPI card has a percentage value", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });

    // GTN ratio should display as a percentage like "83.6%"
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/\d+\.\d+%/);
  });

  test("GTN Dashboard renders charts (SVGs present after lazy load)", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });
    await page.waitForTimeout(2000); // Allow recharts dynamic imports to resolve

    const svgCount = await page.locator("svg").count();
    expect(svgCount).toBeGreaterThan(2);
  });

  test("Total Copay Spend KPI card links to /claims", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });

    // The Total Copay Spend card should be a link to /claims
    const copayCard = page.locator("a[href='/claims']").first();
    await expect(copayCard).toBeVisible();
  });

  test("Identified Leakage KPI card links to /reclaimrx/leakage", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });

    const leakageLink = page.locator("a[href='/reclaimrx/leakage']").first();
    await expect(leakageLink).toBeVisible();
  });

  test("Active Investigations KPI card links to /reclaimrx/investigations", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });

    const invLink = page.locator("a[href='/reclaimrx/investigations']").first();
    await expect(invLink).toBeVisible();
  });

  test("top pharmacies section shows pharmacy names and risk scores", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);

    // Top flagged pharmacies heading
    await expect(page.getByText(/top flagged pharmacies/i)).toBeVisible();

    // Pharmacy NPI labels
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/NPI \d{10}/i);
  });
});
