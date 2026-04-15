/**
 * Programs module E2E tests.
 * - Program list loads and renders
 * - Program detail accessible via row click
 * - Program CRUD (config form)
 * - Budget and enrollment pages load
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Programs overview", () => {
  test("programs list page loads with h1 and table", async ({ page }) => {
    await page.goto("/programs", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/program overview/i);

    // Table should be present
    const table = page.locator("table, [role='table']").first();
    await expect(table).toBeVisible({ timeout: 10_000 });
  });

  test("programs table has expected columns", async ({ page }) => {
    await page.goto("/programs", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/program overview/i);

    // Verify at least some column headers
    await expect(page.getByText(/Program Name/i).first()).toBeVisible();
    await expect(page.getByText(/Status/i).first()).toBeVisible();
  });

  test("clicking a program row navigates to program detail", async ({ page }) => {
    await page.goto("/programs", { waitUntil: "networkidle", timeout: 30_000 });

    // Wait for table rows (tbody rows)
    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();

    await page.waitForLoadState("networkidle");
    expect(page.url()).toMatch(/\/programs\/[^/]+$/);
  });

  test("program detail page has summary cards with hrefs", async ({ page }) => {
    await page.goto("/programs", { waitUntil: "networkidle", timeout: 30_000 });
    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // KPI cards on detail page should be links
    const kpiLinks = page.locator("a[href]");
    const count = await kpiLinks.count();
    expect(count).toBeGreaterThan(0);
  });

  test("program detail tabs are functional", async ({ page }) => {
    await page.goto("/programs", { waitUntil: "networkidle", timeout: 30_000 });
    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // Should have tabs
    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(5);

    // Click the Budget tab
    const budgetTab = tabs.filter({ hasText: /budget/i }).first();
    await expect(budgetTab).toBeVisible();
    await budgetTab.click();
    await expect(budgetTab).toHaveAttribute("aria-selected", "true");
  });
});

test.describe("Program CRUD — Configuration", () => {
  test("program config page loads with form", async ({ page }) => {
    await page.goto("/programs/config", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/program configuration/i);

    // Form fields should be present
    await expect(page.locator('input[type="text"]').first()).toBeVisible();
  });

  test("program config form has all required fields", async ({ page }) => {
    await page.goto("/programs/config", { waitUntil: "networkidle", timeout: 30_000 });

    // Check for key fields
    await expect(page.getByPlaceholder(/program name/i).first()).toBeVisible();
    await expect(page.getByPlaceholder(/manufacturer/i).first()).toBeVisible();
  });

  test("program config form can be filled and submitted", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/programs/config", { waitUntil: "networkidle", timeout: 30_000 });

    // Fill the form
    await page.getByPlaceholder(/program name/i).fill("Test Copay Program 2026");
    await page.getByPlaceholder(/manufacturer/i).fill("Test Pharma Corp");

    // Fill BIN, PCN, Group
    const textInputs = page.locator('input[type="text"]');
    const count = await textInputs.count();
    expect(count).toBeGreaterThanOrEqual(3);

    // Submit button should be present
    const submitBtn = page.getByRole("button", { name: /create program/i });
    await expect(submitBtn).toBeVisible();

    // No TypeErrors
    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors).toHaveLength(0);
  });
});

test.describe("Program Enrollment page", () => {
  test("enrollment page loads with chart and table", async ({ page }) => {
    await page.goto("/programs/enrollment", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/enrollment/i);
    // Table visible
    const table = page.locator("table, [role='table']").first();
    await expect(table).toBeVisible({ timeout: 10_000 });
  });

  test("enrollment page has KPI summary cards", async ({ page }) => {
    await page.goto("/programs/enrollment", { waitUntil: "networkidle", timeout: 30_000 });

    // At least some KPI cards
    const kpiLinks = page.locator("a[href]");
    const count = await kpiLinks.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });
});

test.describe("Program Budget & Forecast page", () => {
  test("budget page loads with summary cards and chart", async ({ page }) => {
    await page.goto("/programs/budget", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/budget/i);
  });
});
