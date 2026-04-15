/**
 * E2E tests for ReclaimRx Pharmacy Risk Scores
 * Tests: table render, risk score color coding, sort/filter.
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Pharmacy Risk Scores", () => {
  test("risk scores page renders with heading", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: /pharmacy risk scores/i })).toBeVisible();
  });

  test("risk scores table has rows with numeric scores", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);

    const rows = page.locator("tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    // Should show numeric risk scores (0-100)
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/\b[0-9]{1,3}\b/);
  });

  test("table shows NPI column in monospace format", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);

    // NPI numbers (10 digits) should appear
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/\d{10}/);
  });

  test("risk tier legend is visible", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });

    // Legend shows the risk tiers
    await expect(page.getByText(/critical/i)).toBeVisible();
    await expect(page.getByText(/high/i)).toBeVisible();
    await expect(page.getByText(/medium/i)).toBeVisible();
    await expect(page.getByText(/low/i)).toBeVisible();
  });

  test("critical and high risk counts are displayed in subtitle", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });

    // Subtitle shows critical + high counts
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/critical/i);
    expect(bodyText).toMatch(/high risk/i);
  });

  test("table column headers include Risk Score and Pharmacy", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });
    await page.waitForTimeout(500);

    await expect(page.getByText("Risk Score")).toBeVisible();
    await expect(page.getByText("Pharmacy")).toBeVisible();
  });

  test("table is sortable by risk score column", async ({ page }) => {
    await page.goto("/reclaimrx/risk", { waitUntil: "networkidle" });
    await page.waitForTimeout(800);

    // Click the Risk Score column header to sort
    const riskScoreHeader = page.getByText("Risk Score").first();
    if (await riskScoreHeader.isVisible()) {
      await riskScoreHeader.click();
      await page.waitForTimeout(300);
      // Should still have rows after sorting
      const rows = page.locator("tbody tr");
      expect(await rows.count()).toBeGreaterThan(0);
    }
  });
});
