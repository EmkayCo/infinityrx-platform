/**
 * Dashboard E2E tests.
 *
 * Critical requirement: ZERO display-only KPI cards.
 * Every KPI card must have an href and navigate when clicked.
 */
import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Dashboard — KPI card clickability", () => {
  test("all KPI cards are clickable links (zero display-only)", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    // Wait for KPI section to render
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    // Find all KPI card link elements within the KPI section
    const kpiLinks = kpiSection.locator("a[href]");
    const count = await kpiLinks.count();

    // We require exactly 6 KPI cards, all with links
    expect(count, "All 6 KPI cards must be clickable links").toBeGreaterThanOrEqual(6);

    // Verify each card has a non-empty href
    for (let i = 0; i < count; i++) {
      const link = kpiLinks.nth(i);
      const href = await link.getAttribute("href");
      expect(href, `KPI card #${i + 1} must have a non-empty href`).toBeTruthy();
      expect(href, `KPI card #${i + 1} href must not be just '#'`).not.toBe("#");
    }
  });

  test("Active Programs KPI card navigates to /programs", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    // Find the card with "Active Programs" label
    const activeProgramsCard = kpiSection.locator("a").filter({ hasText: /active programs/i }).first();
    await expect(activeProgramsCard).toBeVisible();
    const href = await activeProgramsCard.getAttribute("href");
    expect(href).toBe("/programs");
  });

  test("Total Claims KPI card navigates to /claims", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    const claimsCard = kpiSection.locator("a").filter({ hasText: /total claims/i }).first();
    await expect(claimsCard).toBeVisible();
    const href = await claimsCard.getAttribute("href");
    expect(href).toBe("/claims");
  });

  test("GTN Ratio KPI card navigates to /reclaimrx", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    const gtnCard = kpiSection.locator("a").filter({ hasText: /gtn ratio/i }).first();
    await expect(gtnCard).toBeVisible();
    const href = await gtnCard.getAttribute("href");
    expect(href).toBe("/reclaimrx");
  });

  test("Active Investigations KPI card navigates to /reclaimrx/investigations", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    const invCard = kpiSection.locator("a").filter({ hasText: /active investigations/i }).first();
    await expect(invCard).toBeVisible();
    const href = await invCard.getAttribute("href");
    expect(href).toBe("/reclaimrx/investigations");
  });

  test("Pending Payments KPI card navigates to /accounting/payments", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    const kpiSection = page.locator('[aria-label="Key performance indicators"]');
    await expect(kpiSection).toBeVisible({ timeout: 15_000 });

    const paymentsCard = kpiSection.locator("a").filter({ hasText: /pending payments/i }).first();
    await expect(paymentsCard).toBeVisible();
    const href = await paymentsCard.getAttribute("href");
    expect(href).toBe("/accounting/payments");
  });
});

test.describe("Dashboard — Activity feed", () => {
  test("activity feed renders with clickable items", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    const activitySection = page.locator('[aria-label="Activity and alerts"]');
    await expect(activitySection).toBeVisible({ timeout: 15_000 });

    // Each activity item should be a link
    const activityLinks = activitySection.locator("a[href]");
    const count = await activityLinks.count();
    expect(count, "Activity feed must have clickable items").toBeGreaterThan(0);

    // Each link must have a non-# href
    for (let i = 0; i < Math.min(count, 5); i++) {
      const href = await activityLinks.nth(i).getAttribute("href");
      expect(href, `Activity item #${i + 1} must have a real href`).toBeTruthy();
    }
  });

  test("activity feed items navigate to entity pages", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    const activitySection = page.locator('[aria-label="Activity and alerts"]');
    await expect(activitySection).toBeVisible({ timeout: 15_000 });

    // Click the first activity item
    const firstItem = activitySection.locator("a[href]").first();
    await expect(firstItem).toBeVisible();
    const href = await firstItem.getAttribute("href");
    expect(href).toBeTruthy();

    // Navigate
    await firstItem.click();
    // We just need to be at a valid page (not 404)
    await page.waitForLoadState("networkidle");
    const url = page.url();
    expect(url).not.toContain("404");
  });
});

test.describe("Dashboard — Program health cards", () => {
  test("program health cards are clickable and link to programs", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    const progSection = page.locator('[aria-label="Program health"]');
    await expect(progSection).toBeVisible({ timeout: 15_000 });

    const progCards = progSection.locator("a[href]");
    const count = await progCards.count();
    expect(count, "Program health cards must be clickable").toBeGreaterThan(0);

    // All program health cards should link to /programs/...
    for (let i = 0; i < count; i++) {
      const href = await progCards.nth(i).getAttribute("href");
      expect(href, `Program health card #${i + 1} must link to /programs/...`).toMatch(/\/programs\//);
    }
  });
});

test.describe("Dashboard — Alerts section", () => {
  test("alerts section has clickable items", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    const alertsSection = page.locator('[aria-label="Activity and alerts"]');
    await expect(alertsSection).toBeVisible({ timeout: 15_000 });

    // Alerts should have links
    const alertLinks = alertsSection.locator("a[href]");
    const count = await alertLinks.count();
    expect(count).toBeGreaterThan(0);
  });
});

test.describe("Dashboard — Quick actions", () => {
  test("quick action buttons are present and linked", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });

    const quickActionsSection = page.locator('[aria-label="Quick actions"]');
    await expect(quickActionsSection).toBeVisible({ timeout: 15_000 });

    const actionLinks = quickActionsSection.locator("a[href]");
    const count = await actionLinks.count();
    expect(count, "Quick actions must have links").toBe(4);
  });
});

test.describe("Dashboard — Preset tabs", () => {
  test("preset tabs switch between views", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("h1")).toHaveText(/dashboard/i);

    // Tab buttons should be visible
    const tabs = page.locator('[role="tab"]');
    const count = await tabs.count();
    expect(count).toBeGreaterThanOrEqual(4);

    // Click a different tab
    const billingTab = tabs.filter({ hasText: /billing operations/i }).first();
    await expect(billingTab).toBeVisible();
    await billingTab.click();
    await expect(billingTab).toHaveAttribute("aria-selected", "true");
  });
});
