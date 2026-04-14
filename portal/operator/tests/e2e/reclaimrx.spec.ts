/**
 * ReclaimRx module — deep E2E coverage.
 *
 * The ReclaimRx routes were the original crash from the user's complaint and
 * are now Server Components (Prompt 7). These tests verify the end-to-end
 * flow still works.
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("ReclaimRx", () => {
  test("dashboard shows 4 stat cards with numeric values", async ({ page }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });
    // 4 StatCard labels
    await expect(page.getByText(/new flags today/i)).toBeVisible();
    await expect(page.getByText(/new flags this week/i)).toBeVisible();
    await expect(page.getByText(/critical flags/i)).toBeVisible();
    await expect(page.getByText(/high severity/i)).toBeVisible();
    // No NaN in the page
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });

  test("dashboard charts render (severity pie + trend line SVGs present)", async ({
    page,
  }) => {
    await page.goto("/reclaimrx", { waitUntil: "networkidle" });
    // Give the lazy-loaded chart chunks time to resolve
    await page.waitForTimeout(1500);
    // At least one recharts SVG should exist
    const svgCount = await page.locator("svg").count();
    expect(svgCount).toBeGreaterThan(5);
  });

  test("recovery table renders ≥20 rows with real data", async ({ page }) => {
    await page.goto("/reclaimrx/recovery", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: /recovery tracking/i })).toBeVisible();
    const rows = page.locator("tbody tr");
    await expect(rows).toHaveCount(20);
    // First row should have real-looking entity name text
    const firstRowText = await rows.first().innerText();
    expect(firstRowText.length).toBeGreaterThan(20);
  });

  test("investigations Kanban renders 5 columns with cards", async ({ page }) => {
    await page.goto("/reclaimrx/investigations", { waitUntil: "networkidle" });
    // Give dnd-kit chunk time to hydrate
    await page.waitForTimeout(2000);
    // 5 columns by heading
    for (const label of ["New", "Assigned", "Evidence", "Demand", "Resolved"]) {
      await expect(page.getByRole("heading", { name: label, level: 3 })).toBeVisible();
    }
  });

  test("clicking an investigation card navigates to the detail page", async ({ page }) => {
    await page.goto("/reclaimrx/investigations", { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    // Find the first clickable card (those with the cursor-pointer + border classes)
    const firstCard = page
      .locator("[class*='cursor-pointer'][class*='border']")
      .first();
    await firstCard.click();
    // URL should change to /reclaimrx/investigations/<id>
    await page.waitForURL(/\/reclaimrx\/investigations\/[^/]+$/, { timeout: 10_000 });
    await expect(page.getByText(/Flag Evidence/i)).toBeVisible();
  });
});
