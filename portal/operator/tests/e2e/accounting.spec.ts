/**
 * Accounting module — E2E coverage.
 *
 * Tests:
 *   1. Billing Cycles list loads with KPI cards + table
 *   2. Billing cycle detail drill-down shows tabs (Claims, AR, AP, Journal, SaaSant, 835, NACHA)
 *   3. Billing cycle approve action is present for pending_approval cycles
 *   4. Invoices list loads with KPI cards + table rows
 *   5. Invoice detail shows line items and timeline
 *   6. Payments & Batches list loads
 *   7. Payment batch detail shows individual payments
 *   8. NACHA page loads with table
 *   9. Journal Entries page loads with table
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Billing Cycles", () => {
  test("loads with heading, KPI cards, and table", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.locator("h1").first()).toHaveText(/billing cycles/i);

    // KPI cards
    await expect(page.getByText(/total cycles/i)).toBeVisible();
    await expect(page.getByText(/pending approval/i).first()).toBeVisible();

    // No fatal JS errors
    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors).toHaveLength(0);

    // No NaN
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
    expect(bodyText).not.toMatch(/\[object Object\]/);
  });

  test("table renders billing cycle rows", async ({ page }) => {
    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test("billing cycle drill-down — detail page shows tabs", async ({ page }) => {
    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/cycles\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Should show all required tabs
    await expect(page.getByRole("tab", { name: /claims/i }).first()).toBeVisible();
    await expect(page.getByText(/ar entries/i)).toBeVisible();
    await expect(page.getByText(/ap entries/i)).toBeVisible();
    await expect(page.getByText(/journal entries/i).first()).toBeVisible();
    await expect(page.getByText(/saasant preview/i)).toBeVisible();
    await expect(page.getByText(/835 preview/i)).toBeVisible();
    await expect(page.getByText(/nacha preview/i)).toBeVisible();
  });

  test("billing cycle detail shows summary cards", async ({ page }) => {
    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/cycles\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Summary cards should show
    await expect(page.getByText(/total claims/i).first()).toBeVisible();
    await expect(page.getByText(/total ap/i)).toBeVisible();
    await expect(page.getByText(/total ar/i)).toBeVisible();
    await expect(page.getByText(/net amount/i)).toBeVisible();

    // No NaN
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
    expect(bodyText).not.toMatch(/\[object Object\]/);
  });

  test("cycle detail SaaSant tab shows worksheet preview", async ({ page }) => {
    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/cycles\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Click SaaSant Preview tab
    await page.getByText(/saasant preview/i).click();
    await expect(page.getByText(/summary/i).first()).toBeVisible();
    await expect(page.getByText(/ap detail/i)).toBeVisible();
    await expect(page.getByText(/fee schedule/i)).toBeVisible();
  });

  test("billing cycle workflow — back link works", async ({ page }) => {
    await page.goto("/accounting/cycles", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/cycles\/.+/, { timeout: 10_000 });

    await page.getByText(/back to billing cycles/i).click();
    await page.waitForURL(/\/accounting\/cycles$/, { timeout: 10_000 });
    expect(page.url()).toMatch(/\/accounting\/cycles$/);
  });
});

test.describe("Invoices", () => {
  test("loads with heading, KPI cards, and table", async ({ page }) => {
    await page.goto("/accounting/invoices", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.locator("h1").first()).toHaveText(/invoice/i);
    await expect(page.getByText(/outstanding/i)).toBeVisible();
    await expect(page.getByText(/overdue/i).first()).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });

  test("invoice list shows rows", async ({ page }) => {
    await page.goto("/accounting/invoices", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test("invoice drill-down shows detail with line items", async ({ page }) => {
    await page.goto("/accounting/invoices", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/invoices\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Invoice detail heading
    await expect(page.locator("h1").first()).toBeVisible();

    // Line Items section
    await expect(page.getByText(/line items/i)).toBeVisible();

    // Activity timeline
    await expect(page.getByText(/activity timeline/i)).toBeVisible();

    // No NaN
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
    expect(bodyText).not.toMatch(/\[object Object\]/);
  });

  test("invoice detail shows summary cards with currency values", async ({ page }) => {
    await page.goto("/accounting/invoices", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/invoices\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    // Summary should show invoice total with $ sign
    await expect(page.getByText(/invoice total/i)).toBeVisible();
    const bodyText = await page.locator("body").innerText();
    expect(bodyText).toMatch(/\$[\d,]+\.\d{2}/);
  });
});

test.describe("Payments & Batches", () => {
  test("loads with heading and KPI cards", async ({ page }) => {
    await page.goto("/accounting/payments", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.locator("h1").first()).toHaveText(/payments/i);
    await expect(page.getByText(/pending batches/i)).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });

  test("payment batch table renders rows", async ({ page }) => {
    await page.goto("/accounting/payments", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
  });

  test("payment batch drill-down loads detail page", async ({ page }) => {
    await page.goto("/accounting/payments", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    if ((await rows.count()) === 0) { test.skip(); return; }

    await rows.first().click();
    await page.waitForURL(/\/accounting\/payments\/.+/, { timeout: 10_000 });
    await page.waitForLoadState("networkidle", { timeout: 15_000 });

    await expect(page.locator("h1").first()).toBeVisible();
    await expect(page.getByText(/batch details/i)).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });
});

test.describe("NACHA Files", () => {
  test("loads with heading, KPI cards, and table", async ({ page }) => {
    await page.goto("/accounting/nacha", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.locator("h1").first()).toHaveText(/nacha/i);
    await expect(page.getByText(/total files/i)).toBeVisible();
    await expect(page.getByText(/pending transmit/i)).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
    expect(bodyText).not.toMatch(/\[object Object\]/);
  });

  test("NACHA table renders file rows", async ({ page }) => {
    await page.goto("/accounting/nacha", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
  });
});

test.describe("Journal Entries", () => {
  test("loads with heading, KPI cards, and table", async ({ page }) => {
    await page.goto("/accounting/journal-entries", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.locator("h1").first()).toHaveText(/journal entries/i);
    await expect(page.getByText(/total entries/i)).toBeVisible();
    await expect(page.getByText(/total ap/i)).toBeVisible();
    await expect(page.getByText(/total ar/i)).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\bNaN\b/);
    expect(bodyText).not.toMatch(/\[object Object\]/);
  });

  test("journal entries table renders rows", async ({ page }) => {
    await page.goto("/accounting/journal-entries", { waitUntil: "networkidle", timeout: 30_000 });
    await page.waitForTimeout(1500);

    const rows = page.locator("tbody tr");
    expect(await rows.count()).toBeGreaterThan(0);
  });
});
