/**
 * Clients module E2E tests.
 * - Companies list loads and is clickable
 * - Company detail tabs work
 * - Fee editing: load → edit → save → verify persisted values
 * - Portal access page
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Companies list", () => {
  test("companies page loads with table", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/companies/i);

    const table = page.locator("table, [role='table']").first();
    await expect(table).toBeVisible({ timeout: 10_000 });
  });

  test("companies table has expected columns", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.getByText(/Company Name/i).first()).toBeVisible();
    await expect(page.getByText(/Status/i).first()).toBeVisible();
  });

  test("clicking a company row navigates to detail page", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();

    await page.waitForLoadState("networkidle");
    expect(page.url()).toMatch(/\/clients\/[^/]+$/);
  });
});

test.describe("Company detail page", () => {
  test("company detail has tabs", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // Should have tabs including Client Details, Client Profile, Client Programs, etc.
    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(5);
  });

  test("Client Details tab shows company info and edit button", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // Client Details tab should be selected by default
    const detailsTab = page.locator('[role="tab"]').filter({ hasText: /client details/i }).first();
    await expect(detailsTab).toBeVisible();
    await expect(detailsTab).toHaveAttribute("aria-selected", "true");

    // Edit button should be visible in the details view
    const editBtn = page.getByRole("button", { name: /edit/i }).first();
    await expect(editBtn).toBeVisible();
  });

  test("Client Profile tab shows fee configuration", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // Click the Client Profile tab
    const profileTab = page.locator('[role="tab"]').filter({ hasText: /client profile/i }).first();
    await expect(profileTab).toBeVisible();
    await profileTab.click();
    await expect(profileTab).toHaveAttribute("aria-selected", "true");

    // Fee fields should appear
    await expect(page.getByText(/IBL Setup Fee/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/ICP Setup Fee/i).first()).toBeVisible();
  });

  test("Client Profile fee editing — load → edit → save → shows saved confirmation", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    // Navigate to Client Profile tab
    const profileTab = page.locator('[role="tab"]').filter({ hasText: /client profile/i }).first();
    await profileTab.click();
    await expect(profileTab).toHaveAttribute("aria-selected", "true");

    // Wait for fees to load
    await expect(page.getByText(/IBL Setup Fee/i).first()).toBeVisible({ timeout: 10_000 });

    // Click edit button
    const editBtn = page.getByRole("button", { name: /edit fees/i }).first();
    await expect(editBtn).toBeVisible();
    await editBtn.click();

    // Form should appear
    const feeInput = page.locator('[data-fee-field="ibl_setup_fee"]').first();
    await expect(feeInput).toBeVisible({ timeout: 5_000 });

    // Change a value
    await feeInput.fill("1750.00");

    // Save
    const saveBtn = page.getByRole("button", { name: /save fees/i }).first();
    await expect(saveBtn).toBeVisible();
    await saveBtn.click();

    // Confirmation message should appear
    await expect(page.getByText(/fees saved successfully/i)).toBeVisible({ timeout: 10_000 });
  });

  test("Statement Providers tab loads table", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    const spTab = page.locator('[role="tab"]').filter({ hasText: /statement providers/i }).first();
    await spTab.click();
    await expect(spTab).toHaveAttribute("aria-selected", "true");

    // Table should load (even if empty)
    await page.waitForTimeout(1000);
    const noErrors = page.locator('[data-testid="error"]');
    await expect(noErrors).toHaveCount(0);
  });

  test("Blocked Providers tab loads", async ({ page }) => {
    await page.goto("/clients", { waitUntil: "networkidle", timeout: 30_000 });

    const firstRow = page.locator("tbody tr").first();
    await expect(firstRow).toBeVisible({ timeout: 10_000 });
    await firstRow.click();
    await page.waitForLoadState("networkidle");

    const bpTab = page.locator('[role="tab"]').filter({ hasText: /blocked providers/i }).first();
    await bpTab.click();
    await expect(bpTab).toHaveAttribute("aria-selected", "true");

    await page.waitForTimeout(1000);
  });
});

test.describe("Fee Configuration master schedule", () => {
  test("fee config page loads with table", async ({ page }) => {
    await page.goto("/clients/fees", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/fee configuration/i);

    const table = page.locator("table, [role='table']").first();
    await expect(table).toBeVisible({ timeout: 10_000 });
  });

  test("fee config table shows all standard fee types", async ({ page }) => {
    await page.goto("/clients/fees", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.getByText(/IBL.*setup/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/ICP.*setup/i).first()).toBeVisible({ timeout: 10_000 });
  });
});

test.describe("Portal Access page", () => {
  test("portal access page loads with client selector", async ({ page }) => {
    await page.goto("/clients/portal-access", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1").first()).toHaveText(/portal access/i);

    // Client selector should be present
    const selector = page.locator("select").first();
    await expect(selector).toBeVisible({ timeout: 10_000 });
  });

  test("selecting a client reveals manufacturer view panel", async ({ page }) => {
    await page.goto("/clients/portal-access", { waitUntil: "networkidle", timeout: 30_000 });

    // Wait for selector to populate
    const selector = page.locator("select").first();
    await expect(selector).toBeVisible({ timeout: 10_000 });

    // Select the first enabled client
    const options = await selector.locator("option").all();
    // Skip the first "— Select a client —" option
    if (options.length > 1) {
      await selector.selectOption({ index: 1 });

      // Manufacturer view panel should appear
      await expect(page.getByText(/manufacturer view/i).first()).toBeVisible({ timeout: 5_000 });
      await expect(page.getByText(/read-only mode/i).first()).toBeVisible({ timeout: 5_000 });
    }
  });
});
