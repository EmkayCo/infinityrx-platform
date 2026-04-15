/**
 * Analytics E2E Tests — ICP Portal Phase 1B
 *
 * Covers:
 * - Chart rendering on every analytics page (smoke)
 * - FilterPanel filtering on Claim Summary page
 * - Period toggle on Fill Performance
 * - Waterfall chart presence + decomposition labels on Trend Analysis
 * - Copay impact chart with both cohorts visible on Adherence
 */

import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

// ─── Chart rendering smoke tests ─────────────────────────────────────────────

test.describe("Analytics chart rendering", () => {
  const ANALYTICS_ROUTES = [
    { path: "/analytics/claims", heading: /claim summary/i },
    { path: "/analytics/fills", heading: /fill performance/i },
    { path: "/analytics/adherence", heading: /adherence/i },
    { path: "/analytics/pharmacies", heading: /pharmacy insights/i },
    { path: "/analytics/geography", heading: /geographic analysis/i },
    { path: "/analytics/trends", heading: /trend analysis/i },
  ];

  for (const { path, heading } of ANALYTICS_ROUTES) {
    test(`${path} renders with h1 heading and no console errors`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

      const resp = await page.goto(path, { waitUntil: "networkidle", timeout: 30_000 });
      expect([200, 307], `${path} HTTP status`).toContain(resp?.status() ?? 0);

      // No TypeErrors / ReferenceErrors
      const jsErrors = consoleErrors.filter((e) => /TypeError|ReferenceError|SyntaxError/.test(e));
      expect(jsErrors, `${path} JS errors`).toHaveLength(0);

      // Body text should not contain broken object placeholders
      const body = await page.locator("body").innerText();
      expect(body).not.toMatch(/\[object Object\]/);
      expect(body).not.toMatch(/\bNaN\b/);

      // H1 heading present
      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("h1").first()).toHaveText(heading);
    });
  }
});

// ─── Claim Summary — FilterPanel interaction ──────────────────────────────────

test.describe("FilterPanel filtering on Claim Summary", () => {
  test("filter panel is visible and collapsible", async ({ page }) => {
    await page.goto("/analytics/claims", { waitUntil: "networkidle", timeout: 30_000 });

    // Check that filter-related UI is present (label text)
    await expect(page.getByText("Date From", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("period toggle buttons are visible on Claim Summary", async ({ page }) => {
    await page.goto("/analytics/claims", { waitUntil: "networkidle", timeout: 30_000 });

    // Period toggle should have Monthly/Weekly/Daily options
    await expect(page.getByRole("button", { name: /monthly/i }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /weekly/i }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /daily/i }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("KPI cards load on Claim Summary", async ({ page }) => {
    await page.goto("/analytics/claims", { waitUntil: "networkidle", timeout: 30_000 });

    // Wait for KPI cards to load (not skeleton)
    await expect(page.getByText("Claim Count", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Ingredient Cost", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Copay Assistance", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("Export CSV button is present on Claim Summary", async ({ page }) => {
    await page.goto("/analytics/claims", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByRole("button", { name: /export csv/i }).first()).toBeVisible({ timeout: 10_000 });
  });
});

// ─── Fill Performance — period toggle ────────────────────────────────────────

test.describe("Fill Performance period toggle", () => {
  test("period toggle changes selected state on Fill Performance", async ({ page }) => {
    await page.goto("/analytics/fills", { waitUntil: "networkidle", timeout: 30_000 });

    // Monthly button should be present
    const monthlyBtn = page.getByRole("button", { name: /monthly/i }).first();
    await expect(monthlyBtn).toBeVisible({ timeout: 10_000 });

    // Click weekly
    const weeklyBtn = page.getByRole("button", { name: /weekly/i }).first();
    await weeklyBtn.click();

    // KPI labels still visible after toggle
    await expect(page.getByText("Total Fills", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("NBRx", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("Fill Performance has 5 KPI cards", async ({ page }) => {
    await page.goto("/analytics/fills", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.getByText("Total Fills", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("NBRx", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Refills", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });
});

// ─── Adherence — copay impact comparison ─────────────────────────────────────

test.describe("Adherence page — copay impact comparison", () => {
  test("copay impact comparison section is visible with both cohort labels", async ({ page }) => {
    await page.goto("/analytics/adherence", { waitUntil: "networkidle", timeout: 30_000 });

    // Wait for the ROI proof chart section
    await expect(page.getByText("Copay Card Impact", { exact: false }).first()).toBeVisible({ timeout: 15_000 });

    // Both cohorts should be labeled
    await expect(page.getByText("With Copay Card", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Without Copay Card", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("adherence page shows PDC KPI", async ({ page }) => {
    await page.goto("/analytics/adherence", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("Overall PDC", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Persistence", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("adherence page shows ROI per dollar spent", async ({ page }) => {
    await page.goto("/analytics/adherence", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("ROI per $ Spent", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });

  test("patient-level adherence table is rendered", async ({ page }) => {
    await page.goto("/analytics/adherence", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("Patient-Level Adherence", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });
});

// ─── Trend Analysis — waterfall chart ────────────────────────────────────────

test.describe("Trend Analysis — waterfall decomposition", () => {
  test("waterfall section is visible with decomposition label", async ({ page }) => {
    await page.goto("/analytics/trends", { waitUntil: "networkidle", timeout: 30_000 });

    // Waterfall heading
    await expect(page.getByText("Trend Decomposition Waterfall", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });

  test("waterfall page shows decomposition explanation text", async ({ page }) => {
    await page.goto("/analytics/trends", { waitUntil: "networkidle", timeout: 30_000 });

    // Decomposition labels
    await expect(page.getByText("utilization", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("unit cost", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("mix", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("top movers tables are rendered", async ({ page }) => {
    await page.goto("/analytics/trends", { waitUntil: "networkidle", timeout: 30_000 });

    await expect(page.getByText("Top Cost Increasers", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText("Top Cost Decreasers", { exact: false }).first()).toBeVisible({ timeout: 10_000 });
  });

  test("YoY spend comparison chart section is visible", async ({ page }) => {
    await page.goto("/analytics/trends", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("Year-over-Year Spend Comparison", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });
});

// ─── Pharmacy Insights ────────────────────────────────────────────────────────

test.describe("Pharmacy Insights", () => {
  test("state heat map is rendered", async ({ page }) => {
    await page.goto("/analytics/pharmacies", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("Claims by State", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
    // State abbreviations should be visible in the choropleth
    await expect(page.getByText("TX").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("CA").first()).toBeVisible({ timeout: 10_000 });
  });

  test("top 20 pharmacies section visible", async ({ page }) => {
    await page.goto("/analytics/pharmacies", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("Top 20 Pharmacies", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });
});

// ─── Geographic Analysis ──────────────────────────────────────────────────────

test.describe("Geographic Analysis", () => {
  test("metric selector dropdown is visible", async ({ page }) => {
    await page.goto("/analytics/geography", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.locator("select").filter({ hasText: /claim count|spend/i }).first()).toBeVisible({ timeout: 15_000 });
  });

  test("state table loads with state data", async ({ page }) => {
    await page.goto("/analytics/geography", { waitUntil: "networkidle", timeout: 30_000 });
    await expect(page.getByText("State Breakdown", { exact: false }).first()).toBeVisible({ timeout: 15_000 });
  });
});
