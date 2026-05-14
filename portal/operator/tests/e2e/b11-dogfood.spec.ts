/**
 * B11 w0 — full-portal dogfood (Playwright headed harness).
 *
 * Walks every route in NAV_MODULES, captures screenshot + network HAR +
 * console errors + navigation timing. Reproduces issue #1 (login-redirect)
 * and issue #2 (sidebar accordion stays open).
 *
 * Outputs land in test-results/b11-dogfood/ as one folder per route.
 *
 * Intentionally tolerant — collects evidence even when pages 5xx or render
 * empty, because that IS the test. Soft assertions only.
 */
import { test, expect, Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// NAV_MODULES mirrored here to keep the test independent of import-resolution
// issues across the monorepo. Updated 2026-05-13.
const ROUTES: { module: string; route: string }[] = [
  { module: "Dashboard", route: "/" },
  { module: "Programs", route: "/programs" },
  { module: "Programs", route: "/programs/enrollment" },
  { module: "Programs", route: "/programs/budget" },
  { module: "Programs", route: "/programs/config" },
  { module: "Claims", route: "/claims" },
  { module: "Claims", route: "/claims/lookup" },
  { module: "Claims", route: "/claims/manual" },
  { module: "Claims", route: "/claims/pa-override" },
  { module: "Accounting", route: "/accounting/cycles" },
  { module: "Accounting", route: "/accounting/invoices" },
  { module: "Accounting", route: "/accounting/payments" },
  { module: "Accounting", route: "/accounting/nacha" },
  { module: "Accounting", route: "/accounting/journal-entries" },
  { module: "ReclaimRx", route: "/reclaimrx" },
  { module: "ReclaimRx", route: "/reclaimrx/leakage" },
  { module: "ReclaimRx", route: "/reclaimrx/investigations" },
  { module: "ReclaimRx", route: "/reclaimrx/risk" },
  { module: "ReclaimRx", route: "/reclaimrx/recovery" },
  { module: "ReclaimRx", route: "/reclaimrx/wizard" },
  { module: "Analytics", route: "/analytics/claims" },
  { module: "Analytics", route: "/analytics/fills" },
  { module: "Analytics", route: "/analytics/adherence" },
  { module: "Analytics", route: "/analytics/pharmacies" },
  { module: "Analytics", route: "/analytics/geography" },
  { module: "Analytics", route: "/analytics/trends" },
  { module: "Directories", route: "/directories/pharmacies" },
  { module: "Directories", route: "/directories/prescribers" },
  { module: "Directories", route: "/directories/drugs" },
  { module: "Directories", route: "/directories/members" },
  { module: "Clients", route: "/clients" },
  { module: "Clients", route: "/clients/programs" },
  { module: "Clients", route: "/clients/fees" },
  { module: "Clients", route: "/clients/networks" },
  { module: "Clients", route: "/clients/exceptions" },
  { module: "Clients", route: "/clients/cardholders" },
  { module: "Clients", route: "/clients/states" },
  { module: "Clients", route: "/clients/portal-access" },
  { module: "EDI", route: "/edi/monitor" },
  { module: "EDI", route: "/edi/transactions" },
  { module: "EDI", route: "/edi/partners" },
  { module: "EDI", route: "/edi/certs" },
  { module: "Network", route: "/network/locator" },
  { module: "Network", route: "/network/credentialing" },
  { module: "Reporting", route: "/reporting/library" },
  { module: "Reporting", route: "/reporting/builder" },
  { module: "Reporting", route: "/reporting/scheduled" },
  { module: "PaySync", route: "/admin/paysync" },
  { module: "PaySync", route: "/admin/paysync/cycles" },
  { module: "PaySync", route: "/admin/paysync/batches" },
  { module: "PaySync", route: "/admin/paysync/invoices" },
  { module: "PaySync", route: "/admin/paysync/reconciliations" },
  { module: "PaySync", route: "/admin/paysync/carryovers" },
  { module: "PaySync", route: "/admin/paysync/bank-settlements" },
  { module: "PaySync", route: "/admin/paysync/manual-ap" },
  { module: "PaySync", route: "/admin/paysync/echo" },
  { module: "NetworkAdmin", route: "/admin/network/pay-to-entities" },
  { module: "NetworkAdmin", route: "/admin/network/chain-membership" },
  { module: "NetworkAdmin", route: "/admin/network/banking-discrepancies" },
  { module: "NetworkAdmin", route: "/admin/network/tenant-ach-origination" },
  { module: "PaySyncConfig", route: "/admin/paysync/cycle-schedules" },
  { module: "PaySyncConfig", route: "/admin/paysync/export-templates" },
  { module: "PaySyncConfig", route: "/admin/paysync/email-templates" },
  { module: "PaySyncConfig", route: "/admin/paysync/email-recipients" },
  { module: "PaySyncConfig", route: "/admin/paysync/gl-account-mappings" },
  { module: "PaySyncConfig", route: "/admin/paysync/invoice-sequences" },
  { module: "Admin", route: "/admin/users" },
  { module: "Admin", route: "/admin/tenants" },
  { module: "Admin", route: "/admin/system-health" },
  { module: "Admin", route: "/admin/config" },
  { module: "Admin", route: "/admin/audit-log" },
  { module: "Admin", route: "/admin/encryption" },
];

const EVIDENCE_DIR = path.join(
  process.cwd(),
  "test-results",
  "b11-dogfood"
);

function evidencePath(route: string, file: string): string {
  const safe = route.replace(/\//g, "_").replace(/^_/, "root_");
  const dir = path.join(EVIDENCE_DIR, safe);
  fs.mkdirSync(dir, { recursive: true });
  return path.join(dir, file);
}

async function loginViaDevBypass(page: Page): Promise<void> {
  await page.goto("http://localhost:3000/login");
  // The dev-bypass button reads "Sign in as Dev Admin (mock)" — see
  // portal/operator/app/(auth)/login/page.tsx line 221.
  const devButton = page.getByRole("button", { name: /sign in as dev admin/i });
  await devButton.waitFor({ state: "visible", timeout: 10000 });
  await devButton.click();
  // Wait for navigation away from /login.
  await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
    timeout: 15000,
  });
}

test.describe("B11 w0 — full-portal dogfood", () => {
  test.describe.configure({ mode: "serial" });

  test("F-ISSUE-1 — login → wrong-page-before-refresh reproduction", async ({
    page,
  }) => {
    const consoleErrors: string[] = [];
    const networkFailures: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("requestfailed", (req) =>
      networkFailures.push(`${req.method()} ${req.url()} :: ${req.failure()?.errorText ?? "unknown"}`)
    );

    // 1. Start at root, expect redirect to /login
    const t0 = Date.now();
    await page.goto("http://localhost:3000/");
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await page.screenshot({ path: evidencePath("issue-1", "01-login-page.png"), fullPage: true });

    // 2. Click dev-bypass — button text "Sign in as Dev Admin (mock)"
    const devButton = page.getByRole("button", { name: /sign in as dev admin/i });
    await devButton.waitFor({ state: "visible", timeout: 10000 });
    await devButton.click();

    // 3. Capture FIRST page that loads after login (this is where the
    //    'wrong page' bug manifests). Wait for nav away from /login.
    await page.waitForURL((url) => !url.pathname.startsWith("/login"), {
      timeout: 15000,
    });
    const postLoginUrl = page.url();
    await page.screenshot({ path: evidencePath("issue-1", "02-post-login-initial.png"), fullPage: true });

    // 4. Check if the sidebar is visible WITHOUT refreshing.
    //    Sidebar should have <nav> or role=navigation with NAV_MODULES rendered.
    const sidebarVisible = await page
      .locator('[data-testid="operator-sidebar"], nav[aria-label*="navigation" i], aside nav')
      .first()
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    // 5. Now refresh and re-check
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => {});
    await page.screenshot({ path: evidencePath("issue-1", "03-after-refresh.png"), fullPage: true });
    const sidebarVisibleAfterRefresh = await page
      .locator('[data-testid="operator-sidebar"], nav[aria-label*="navigation" i], aside nav')
      .first()
      .isVisible({ timeout: 2000 })
      .catch(() => false);

    // Write findings
    fs.writeFileSync(
      evidencePath("issue-1", "findings.json"),
      JSON.stringify(
        {
          ttfb_ms_to_login: Date.now() - t0,
          post_login_url: postLoginUrl,
          sidebar_visible_before_refresh: sidebarVisible,
          sidebar_visible_after_refresh: sidebarVisibleAfterRefresh,
          bug_reproduced: !sidebarVisible && sidebarVisibleAfterRefresh,
          console_errors: consoleErrors,
          network_failures: networkFailures,
        },
        null,
        2
      )
    );
  });

  test("F-ISSUE-2 — sidebar accordion: only one category open at a time", async ({
    page,
  }) => {
    await loginViaDevBypass(page);
    await page.reload({ waitUntil: "domcontentloaded" });

    // Helper: read which top-level modules are currently expanded.
    const readExpanded = async (): Promise<string[]> => {
      return await page.evaluate(() => {
        const expanded: string[] = [];
        // Most accordion implementations set aria-expanded or data-state on the trigger.
        document.querySelectorAll("[aria-expanded='true'], [data-state='open']").forEach((el) => {
          const label = el.textContent?.trim().slice(0, 40) ?? "";
          if (label) expanded.push(label);
        });
        return expanded;
      });
    };

    const observations: Array<{ click: string; expanded_after: string[] }> = [];

    // Click each top-level module in turn. After each click, record what's open.
    for (const moduleName of ["Programs", "Claims", "Accounting", "ReclaimRx", "Analytics"]) {
      const trigger = page.getByRole("button", { name: new RegExp(`^${moduleName}$`, "i") }).first();
      if ((await trigger.count()) === 0) continue;
      await trigger.click();
      await page.waitForTimeout(300);
      observations.push({
        click: moduleName,
        expanded_after: await readExpanded(),
      });
      await page.screenshot({ path: evidencePath("issue-2", `after-${moduleName}.png`), fullPage: true });
    }

    // Bug reproduction: after clicking 5 different categories sequentially,
    // how many are still expanded? Should be 1.
    const finalExpanded = observations[observations.length - 1]?.expanded_after ?? [];
    fs.writeFileSync(
      evidencePath("issue-2", "findings.json"),
      JSON.stringify(
        {
          observations,
          final_expanded_count: finalExpanded.length,
          bug_reproduced: finalExpanded.length > 1,
          final_expanded: finalExpanded,
        },
        null,
        2
      )
    );
  });

  for (const { module, route } of ROUTES) {
    test(`F-ROUTE — ${module} ${route}`, async ({ page }) => {
      const consoleErrors: string[] = [];
      const networkLog: Array<{
        method: string;
        url: string;
        status?: number;
        timing_ms?: number;
        failure?: string;
      }> = [];
      page.on("console", (msg) => {
        if (msg.type() === "error") consoleErrors.push(msg.text());
      });
      page.on("requestfailed", (req) =>
        networkLog.push({
          method: req.method(),
          url: req.url(),
          failure: req.failure()?.errorText,
        })
      );
      page.on("response", async (resp) => {
        const req = resp.request();
        const timing = req.timing();
        networkLog.push({
          method: req.method(),
          url: req.url(),
          status: resp.status(),
          timing_ms: Math.round(timing.responseEnd - timing.startTime),
        });
      });

      await loginViaDevBypass(page);

      const t0 = Date.now();
      const navResp = await page.goto(`http://localhost:3000${route}`, {
        waitUntil: "domcontentloaded",
        timeout: 30000,
      });
      const ttDOMContent = Date.now() - t0;
      await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {});
      const ttNetIdle = Date.now() - t0;
      await page.screenshot({ path: evidencePath(route, "page.png"), fullPage: true });

      // Heuristic: did the page render any data table / chart / list of cards?
      const hasTable = await page.locator("table tbody tr").count();
      const hasCards = await page.locator('[class*="card" i], [data-slot*="card" i]').count();
      const hasEmptyState = await page
        .getByText(/no data|nothing here|empty|coming soon/i)
        .count();
      const hasError = await page
        .getByText(/something went wrong|error|failed to load/i)
        .count();

      fs.writeFileSync(
        evidencePath(route, "findings.json"),
        JSON.stringify(
          {
            module,
            route,
            nav_status: navResp?.status() ?? null,
            tt_dom_content_ms: ttDOMContent,
            tt_network_idle_ms: ttNetIdle,
            console_errors: consoleErrors,
            api_calls: networkLog.filter((n) => n.url.match(/:80\d\d/) || n.url.match(/\/api\//)),
            failed_calls: networkLog.filter((n) => n.failure || (n.status && n.status >= 400)),
            heuristic_table_rows: hasTable,
            heuristic_card_count: hasCards,
            heuristic_empty_state_visible: hasEmptyState > 0,
            heuristic_error_visible: hasError > 0,
          },
          null,
          2
        )
      );
    });
  }

  test("F-MPI-LOOKUP — prescriber MPI/NPI lookup smoke test", async ({ page }) => {
    await loginViaDevBypass(page);
    await page.goto("http://localhost:3000/directories/prescribers");
    await page.waitForLoadState("domcontentloaded");
    await page.screenshot({ path: evidencePath("mpi-lookup", "01-list.png"), fullPage: true });

    // Try typing into the most likely search box.
    const searchBox = page
      .locator(
        'input[placeholder*="NPI" i], input[placeholder*="search" i], input[type="search"]'
      )
      .first();
    const found = (await searchBox.count()) > 0;
    if (found) {
      await searchBox.fill("1234567893"); // arbitrary 10-digit NPI for echo test
      await page.waitForTimeout(1000);
      await page.screenshot({ path: evidencePath("mpi-lookup", "02-after-type.png"), fullPage: true });
    }
    fs.writeFileSync(
      evidencePath("mpi-lookup", "findings.json"),
      JSON.stringify({ search_box_found: found, url: page.url() }, null, 2)
    );
  });
});
