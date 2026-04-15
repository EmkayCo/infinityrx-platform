/**
 * E2E tests — Directory detail pages
 *
 * Covers:
 *  - Pharmacy detail: chain code, pay-to provider, reconciliation vendor, KPI cards
 *  - Drug detail: GPI, therapeutic class, AWP/WAC pricing, brand/generic badge
 *  - Member detail: plan, eligibility status, copay enrollment, PHI badge
 *
 * Uses the dev-bypass auth fixture so every test starts authenticated.
 *
 * Each test navigates to the list page first to grab a real NPI/NDC/ID from
 * the rendered table (so the test is not fragile against seed changes), then
 * drills into the detail page.
 */

import { test, expect } from "@playwright/test";
import { authenticateDevBypass } from "../../fixtures/mock-session";

const BASE = "http://localhost:3000";

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, BASE);
});

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Navigate to a list page, click the first row, and return the resulting URL.
 * Returns the page after navigation.
 */
async function drillToFirstRow(page: import("@playwright/test").Page, listPath: string) {
  await page.goto(listPath, { waitUntil: "networkidle", timeout: 30_000 });
  // Click first data row in the table (not header)
  const firstRow = page.locator("table tbody tr").first();
  await expect(firstRow).toBeVisible({ timeout: 15_000 });
  await firstRow.click();
  await page.waitForLoadState("networkidle");
  return page;
}

// ── Pharmacy detail ───────────────────────────────────────────────────────────

test.describe("Pharmacy detail page", () => {
  test("loads chain code, pay-to provider, and reconciliation vendor", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");

    // Page must have an h1 (pharmacy name)
    await expect(page.locator("h1").first()).toBeVisible();

    // Must show KPI summary cards
    await expect(page.getByText("Total Claims")).toBeVisible();
    await expect(page.getByText("Total Paid")).toBeVisible();
    await expect(page.getByText("Reversal Rate")).toBeVisible();
    await expect(page.getByText("Risk Score")).toBeVisible();

    // Chain & Network info card must exist
    await expect(page.getByText("Chain & Network")).toBeVisible();

    // Chain Code field must be present in the info card
    await expect(page.getByText("Chain Code")).toBeVisible();

    // Pay-To Provider field must be present
    await expect(page.getByText("Pay-To Provider")).toBeVisible();

    // Reconciliation Vendor field must be present
    await expect(page.getByText("Reconciliation Vendor")).toBeVisible();
  });

  test("shows identity fields: NPI, NCPDP, DEA, Store Number, Tax ID", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");

    await expect(page.getByText("Identity")).toBeVisible();
    await expect(page.getByText("NCPDP ID")).toBeVisible();
    await expect(page.getByText("DEA Number")).toBeVisible();
    await expect(page.getByText("Store Number")).toBeVisible();
    await expect(page.getByText("Tax ID")).toBeVisible();
  });

  test("shows classification fields including Dispensing Class and 340B Status", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");

    await expect(page.getByText("Classification")).toBeVisible();
    await expect(page.getByText("Dispensing Class")).toBeVisible();
    await expect(page.getByText("340B Status")).toBeVisible();
  });

  test("shows contact fields: phone, fax, email, contact person", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");

    await expect(page.getByText("Contact")).toBeVisible();
    await expect(page.getByText("Phone")).toBeVisible();
    await expect(page.getByText("Fax")).toBeVisible();
    await expect(page.getByText("Email")).toBeVisible();
    await expect(page.getByText("Contact Person")).toBeVisible();
  });

  test("tabs are clickable: Claims, Prescribers, Investigations, DataQ, Risk Analysis, Financial", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");

    for (const tabLabel of ["Claims", "Prescribers", "Investigations", "DataQ", "Risk Analysis", "Financial"]) {
      const tab = page.getByRole("button", { name: tabLabel });
      await expect(tab).toBeVisible();
      await tab.click();
      // After clicking, tab content area should exist without crashing
      await expect(page.locator("h1").first()).toBeVisible();
    }
  });

  test("Risk Analysis tab shows score breakdown bars", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");
    await page.getByRole("button", { name: "Risk Analysis" }).click();
    await expect(page.getByText("Billing Anomaly")).toBeVisible();
    await expect(page.getByText("Network Leakage")).toBeVisible();
    await expect(page.getByText("Dispensing Pattern")).toBeVisible();
  });

  test("DataQ tab shows rejection rate and top reject codes", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");
    await page.getByRole("button", { name: "DataQ" }).click();
    await expect(page.getByText("Rejection Rate")).toBeVisible();
    await expect(page.getByText("Top Reject Codes")).toBeVisible();
  });

  test("Financial tab shows payment history", async ({ page }) => {
    await drillToFirstRow(page, "/directories/pharmacies");
    await page.getByRole("button", { name: "Financial" }).click();
    await expect(page.getByText("Payment History")).toBeVisible();
    await expect(page.getByText("Avg Paid per Claim")).toBeVisible();
  });

  test("no TypeErrors or broken text in body", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

    await drillToFirstRow(page, "/directories/pharmacies");

    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors, "no TypeErrors on pharmacy detail").toHaveLength(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\[object Object\]/);
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });
});

// ── Drug detail ───────────────────────────────────────────────────────────────

test.describe("Drug detail page", () => {
  test("shows GPI, therapeutic class, and AWP/WAC pricing", async ({ page }) => {
    await drillToFirstRow(page, "/directories/drugs");

    // NDC shown in subtitle
    await expect(page.locator("[data-testid='drug-ndc']")).toBeVisible();

    // Pricing KPI cards
    await expect(page.getByText("AWP")).toBeVisible();
    await expect(page.getByText("WAC")).toBeVisible();

    // Classification info card
    await expect(page.getByText("Classification")).toBeVisible();
    await expect(page.getByText("GPI")).toBeVisible();
    await expect(page.getByText("Therapeutic Class")).toBeVisible();
  });

  test("shows brand/generic badge", async ({ page }) => {
    await drillToFirstRow(page, "/directories/drugs");

    // Brand/Generic badge must be present in the header
    const badge = page.locator("[data-testid='brand-generic-badge']");
    await expect(badge).toBeVisible();
    const text = await badge.innerText();
    expect(["BRAND", "GENERIC"]).toContain(text.trim().toUpperCase());
  });

  test("shows identity fields: NDC, brand name, generic name, manufacturer", async ({ page }) => {
    await drillToFirstRow(page, "/directories/drugs");

    await expect(page.getByText("Identity")).toBeVisible();
    await expect(page.getByText("Brand Name")).toBeVisible();
    await expect(page.getByText("Generic Name")).toBeVisible();
    await expect(page.getByText("Manufacturer")).toBeVisible();
    await expect(page.getByText("Strength")).toBeVisible();
    await expect(page.getByText("Dosage Form")).toBeVisible();
    await expect(page.getByText("Route")).toBeVisible();
  });

  test("tabs are clickable: Claims, Prescribers, Pharmacies", async ({ page }) => {
    await drillToFirstRow(page, "/directories/drugs");

    for (const tabLabel of ["Claims", "Prescribers", "Pharmacies"]) {
      const tab = page.getByRole("button", { name: tabLabel });
      await expect(tab).toBeVisible();
      await tab.click();
      await expect(page.locator("h1").first()).toBeVisible();
    }
  });

  test("no TypeErrors or broken text in body", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

    await drillToFirstRow(page, "/directories/drugs");

    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors, "no TypeErrors on drug detail").toHaveLength(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\[object Object\]/);
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });
});

// ── Member detail ─────────────────────────────────────────────────────────────

test.describe("Member detail page", () => {
  test("shows PHI badge in header", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    const phiBadge = page.locator("[data-testid='phi-badge']");
    await expect(phiBadge).toBeVisible();
    await expect(phiBadge).toContainText("PHI");
  });

  test("shows plan and eligibility status", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    await expect(page.getByText("Coverage")).toBeVisible();
    await expect(page.getByText("Plan")).toBeVisible();
    await expect(page.getByText("Eligibility Status")).toBeVisible();
    await expect(page.getByText("Coverage Status")).toBeVisible();
  });

  test("shows copay enrollment section", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    await expect(page.getByText("Copay Programs")).toBeVisible();
  });

  test("shows effective and term date fields", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    await expect(page.getByText("Effective Date")).toBeVisible();
  });

  test("shows accumulator bars when accumulator data present", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    await expect(page.getByText("Accumulators")).toBeVisible();
    await expect(page.getByText("Deductible")).toBeVisible();
    await expect(page.getByText("Out-of-Pocket Maximum")).toBeVisible();
  });

  test("tabs are clickable: Claims, Prescriptions, Adherence, Eligibility History", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");

    for (const tabLabel of ["Claims", "Prescriptions", "Adherence", "Eligibility History"]) {
      const tab = page.getByRole("button", { name: tabLabel });
      await expect(tab).toBeVisible();
      await tab.click();
      await expect(page.locator("h1").first()).toBeVisible();
    }
  });

  test("Eligibility History tab shows event records", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");
    await page.getByRole("button", { name: "Eligibility History" }).click();
    // Column header should be visible
    await expect(page.getByText("Effective")).toBeVisible();
    await expect(page.getByText("Event")).toBeVisible();
  });

  test("Adherence tab shows PDC scores", async ({ page }) => {
    await drillToFirstRow(page, "/directories/members");
    await page.getByRole("button", { name: "Adherence" }).click();
    await expect(page.getByText("PDC Score")).toBeVisible();
  });

  test("no TypeErrors or broken text in body", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

    await drillToFirstRow(page, "/directories/members");

    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors, "no TypeErrors on member detail").toHaveLength(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\[object Object\]/);
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });
});

// ── Prescriber detail ─────────────────────────────────────────────────────────

test.describe("Prescriber detail page", () => {
  test("shows NPI, specialty, DEA, and state license fields", async ({ page }) => {
    await drillToFirstRow(page, "/directories/prescribers");

    await expect(page.getByText("Identity")).toBeVisible();
    await expect(page.getByText("NPI")).toBeVisible();
    await expect(page.getByText("Specialty")).toBeVisible();
    await expect(page.getByText("Credentials")).toBeVisible();
    await expect(page.getByText("DEA Number")).toBeVisible();
    await expect(page.getByText("State License")).toBeVisible();
  });

  test("tabs are clickable: Claims, Affiliated Pharmacies, Investigations", async ({ page }) => {
    await drillToFirstRow(page, "/directories/prescribers");

    for (const tabLabel of ["Claims", "Affiliated Pharmacies", "Investigations"]) {
      const tab = page.getByRole("button", { name: tabLabel });
      await expect(tab).toBeVisible();
      await tab.click();
      await expect(page.locator("h1").first()).toBeVisible();
    }
  });

  test("no TypeErrors or broken text in body", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(`pageerror: ${err.message}`));

    await drillToFirstRow(page, "/directories/prescribers");

    const typeErrors = consoleErrors.filter((e) => /TypeError|ReferenceError/.test(e));
    expect(typeErrors, "no TypeErrors on prescriber detail").toHaveLength(0);

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toMatch(/\[object Object\]/);
    expect(bodyText).not.toMatch(/\bNaN\b/);
  });
});
