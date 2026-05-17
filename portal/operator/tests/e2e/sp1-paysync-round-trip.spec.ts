/**
 * SP-1 PaySync E2E round-trip spec.
 *
 * Exercises the full Operator -> Approver -> Auditor workflow on synthetic
 * fixture data seeded via the billing seed endpoint.
 *
 * PREREQUISITE: Full docker-compose stack must be running:
 *   docker-compose up -d postgres redis rabbitmq core-platform billing
 *
 * SKIP MARKER: Tests are skipped when E2E_STACK_READY !== "true" so the
 * suite can be imported into CI without failing on environments that don't
 * have the full backend stack.  To run locally:
 *   E2E_STACK_READY=true PW_REUSE_SERVER=true npx playwright test sp1-paysync-round-trip
 *
 * Role switching is done by closing the current context and opening a new one
 * authenticated as the next user via the test-auth shortcut endpoint
 * (POST /api/v1/core/test-auth/token — blocked in production).
 *
 * Scenario reference: docs/superpowers/plans/2026-05-16-sp1-plan-e-reports-setup-e2e.md §Task 5
 */

import { test, expect, Browser, BrowserContext, Page } from "@playwright/test";
import path from "path";

// ── Environment gate ──────────────────────────────────────────────────────────

const E2E_READY = process.env["E2E_STACK_READY"] === "true";

const CORE_BASE_URL = process.env["CORE_BASE_URL"] ?? "http://localhost:8000";
const BILLING_BASE_URL = process.env["BILLING_BASE_URL"] ?? "http://localhost:8001";
const PORTAL_BASE_URL = process.env["PORTAL_BASE_URL"] ?? "http://localhost:3000";

// ── Fixture user IDs (from packages/modules/paysync/fixtures/seeds/users.json) ──

const OPERATOR_USER_ID = "usr-00000000-0000-0000-0000-000000000001";
const APPROVER_USER_ID = "usr-00000000-0000-0000-0000-000000000002";
const AUDITOR_USER_ID  = "usr-00000000-0000-0000-0000-000000000003";
const DEMO_TENANT_ID   = "00000000-0000-0000-0000-000000000001";

// ── Upload fixture path ───────────────────────────────────────────────────────

const UPLOAD_CSV = path.resolve(
  __dirname,
  "../../../../packages/modules/paysync/fixtures/uploads/upload-001-healthy.csv"
);

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Fetch a test-auth JWT for a fixture user from core-platform.
 * Requires E2E_STACK_READY and the test-auth endpoint to be mounted.
 */
async function fetchJwt(userId: string): Promise<string> {
  const resp = await fetch(`${CORE_BASE_URL}/api/v1/core/test-auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, tenant_id: DEMO_TENANT_ID }),
  });
  if (!resp.ok) {
    throw new Error(`fetchJwt: ${resp.status} for user ${userId} — ${await resp.text()}`);
  }
  const body = (await resp.json()) as { access_token: string };
  return body.access_token;
}

/**
 * Open a new browser context authenticated as the given fixture user.
 * The JWT is injected via localStorage init script + extra HTTP headers so
 * the Next.js portal picks it up on the first navigation.
 */
async function openContextAs(
  browser: Browser,
  userId: string
): Promise<{ context: BrowserContext; page: Page; token: string }> {
  const token = await fetchJwt(userId);

  const context = await browser.newContext({
    baseURL: PORTAL_BASE_URL,
    extraHTTPHeaders: {
      Authorization: `Bearer ${token}`,
      "X-Tenant-ID": DEMO_TENANT_ID,
      "X-E2E-Test": "1",
    },
  });

  await context.addInitScript((t: string) => {
    window.localStorage.setItem("irx-e2e-token", t);
  }, token);

  const page = await context.newPage();
  return { context, page, token };
}

/**
 * Seed all paysync fixtures before the test suite.
 * Returns the operator JWT so Step 1 can proceed immediately.
 */
async function seedFixtures(operatorToken: string): Promise<void> {
  const resp = await fetch(`${BILLING_BASE_URL}/api/v1/billing/seed`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${operatorToken}`,
      "X-Tenant-ID": DEMO_TENANT_ID,
    },
    body: JSON.stringify({ tenant_id: DEMO_TENANT_ID }),
  });
  if (!resp.ok) {
    throw new Error(`seedFixtures: ${resp.status} — ${await resp.text()}`);
  }
}

/**
 * Cleanup billing fixture data after the suite.
 */
async function cleanupFixtures(operatorToken: string): Promise<void> {
  await fetch(`${BILLING_BASE_URL}/api/v1/billing/seed`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${operatorToken}`,
      "X-Tenant-ID": DEMO_TENANT_ID,
    },
    body: JSON.stringify({ tenant_id: DEMO_TENANT_ID }),
  }).catch(() => {
    // best-effort cleanup; do not fail the suite
  });
}

// ── Suite ─────────────────────────────────────────────────────────────────────

// Plan E R1 C1 fix: serial ordering required because the 4 test blocks share
// uploadId and workflow state (operator step seeds, approver step consumes,
// auditor step verifies). Without .serial, Playwright parallelism could race.
test.describe.serial("SP-1 PaySync round trip: Operator -> Approver -> Auditor", () => {
  // Shared state across role blocks (all tests run in the same describe block
  // in order; Playwright serial mode enforces sequential execution).
  let operatorToken = "";
  let uploadId = "";

  test.beforeAll(async ({ browser }) => {
    if (!E2E_READY) return;

    // Step 0: get operator JWT and seed fixtures
    operatorToken = await fetchJwt(OPERATOR_USER_ID);
    await seedFixtures(operatorToken);
  });

  test.afterAll(async () => {
    if (!E2E_READY) return;
    await cleanupFixtures(operatorToken);
  });

  // ── OPERATOR BLOCK ────────────────────────────────────────────────────────

  test("Step 1-7: Operator uploads CSV, sees validated status, creates draft batch", async ({
    browser,
  }) => {
    test.skip(!E2E_READY, "SKIP: E2E_STACK_READY !== true — start docker-compose stack first");

    const { context, page } = await openContextAs(browser, OPERATOR_USER_ID);

    try {
      // Step 1: Navigate to PaySync Inbox — should be empty (or show seeded items)
      await page.goto("/admin/paysync");
      await expect(page.locator("h1").first()).toBeVisible();
      await expect(page.locator("h1").first()).toHaveText(/paysync/i);

      // Step 2: Navigate to Uploads, drag-drop upload-001-healthy.csv
      await page.goto("/admin/paysync/uploads");
      await expect(page.locator("h1").first()).toHaveText(/uploads/i);

      // Use file input for CSV upload (drag-drop emulated via setInputFiles)
      const fileInput = page.locator('input[type="file"]').first();
      await fileInput.setInputFiles(UPLOAD_CSV);

      // Submit the upload
      const submitBtn = page.locator('button[type="submit"], button:has-text("Upload"), button:has-text("Submit")').first();
      await submitBtn.click();

      // Step 3: Assert upload appears in list with status "parsing" then "validated"
      // Wait for status badge to transition to "validated" (async backend parsing)
      await page.waitForSelector('[data-testid="upload-status-badge"]:has-text("validated")', {
        timeout: 30_000,
      });

      // Capture the upload ID from the first row URL or data attribute
      const uploadRow = page.locator('[data-testid="upload-row"]').first();
      uploadId = (await uploadRow.getAttribute("data-upload-id")) ?? "";

      // Step 4: Assert Inbox shows "upload_validated_awaiting_batching"
      await page.goto("/admin/paysync");
      await page.waitForSelector(
        '[data-testid="inbox-item"]:has-text("upload_validated_awaiting_batching"), [data-testid="inbox-item"]:has-text("validated")',
        { timeout: 15_000 }
      );

      // Step 5: Click Inbox item -> UploadDetailPage -> 20 claims visible
      const inboxItem = page.locator('[data-testid="inbox-item"]').first();
      await inboxItem.click();
      await page.waitForURL(/\/admin\/paysync\/uploads\//);
      // upload-001-healthy.csv has 20 rows
      await expect(page.locator('[data-testid="claim-row"], tr[data-row-type="claim"]')).toHaveCount(20, {
        timeout: 10_000,
      });

      // Step 6: Create draft batch from upload
      const createBatchBtn = page.locator(
        'button:has-text("Create Batch"), button:has-text("Draft Batch")'
      ).first();
      await createBatchBtn.click();
      await page.waitForURL(/\/admin\/paysync\/batches\//);

      // Step 7: Assert ProvenanceBreadcrumb shows upload reference
      const breadcrumb = page.locator('[data-testid="provenance-breadcrumb"]');
      await expect(breadcrumb).toBeVisible();
      await expect(breadcrumb).toContainText(/upload/i);
    } finally {
      await context.close();
    }
  });

  // ── APPROVER BLOCK ────────────────────────────────────────────────────────

  test("Step 8-15: Approver closes cycle, sends invoice, releases batch, generates NACHA + 835", async ({
    browser,
  }) => {
    test.skip(!E2E_READY, "SKIP: E2E_STACK_READY !== true — start docker-compose stack first");

    const { context, page } = await openContextAs(browser, APPROVER_USER_ID);

    try {
      // Step 8: Open Inbox — "batch_drafted" item visible
      await page.goto("/admin/paysync");
      await page.waitForSelector(
        '[data-testid="inbox-item"]:has-text("batch_drafted"), [data-testid="inbox-item"]:has-text("drafted")',
        { timeout: 15_000 }
      );

      // Step 9: Navigate to Cycles -> close the current cycle
      await page.goto("/admin/paysync/cycles");
      await expect(page.locator("h1").first()).toHaveText(/cycles/i);
      const closeCycleBtn = page.locator(
        'button:has-text("Close Cycle"), button:has-text("Close")'
      ).first();
      await closeCycleBtn.click();
      // Confirm close dialog
      const confirmBtn = page.locator('button:has-text("Confirm"), button:has-text("Yes")').first();
      if (await confirmBtn.isVisible()) await confirmBtn.click();
      await page.waitForSelector('[data-testid="cycle-status"]:has-text("closed"), [data-status="closed"]', {
        timeout: 15_000,
      });

      // Step 10: Navigate to Invoices -> send the draft invoice
      await page.goto("/admin/paysync/invoices");
      await expect(page.locator("h1").first()).toHaveText(/invoices/i);

      // Assert MoneyDisplay shows amount in USD format
      const moneyDisplay = page.locator('[data-testid="money-display"]').first();
      await expect(moneyDisplay).toBeVisible();
      await expect(moneyDisplay).toContainText(/\$[\d,]+\.\d{2}/);

      // Send the draft invoice (requires explicit confirm step)
      const sendBtn = page.locator('button:has-text("Send Invoice"), button:has-text("Send")').first();
      await sendBtn.click();
      // Assert confirm step appears
      const confirmSend = page.locator(
        '[data-testid="confirm-send"], button:has-text("Confirm Send"), button:has-text("Confirm")'
      ).first();
      await expect(confirmSend).toBeVisible();
      await confirmSend.click();
      await page.waitForSelector('[data-testid="invoice-status"]:has-text("sent"), [data-status="sent"]', {
        timeout: 10_000,
      });

      // Step 11: Navigate to Payment Runs -> release the held payment run
      await page.goto("/admin/paysync/payment-runs");
      await expect(page.locator("h1").first()).toHaveText(/payment runs/i);
      const releaseBtn = page.locator(
        'button:has-text("Release"), button:has-text("Release Run")'
      ).first();
      await releaseBtn.click();
      await page.waitForSelector('[data-status="released"], [data-testid="run-status"]:has-text("released")', {
        timeout: 10_000,
      });

      // Step 12: Navigate to Files -> generate NACHA file
      await page.goto("/admin/paysync/files");
      await expect(page.locator("h1").first()).toHaveText(/files/i);
      const generateNachaBtn = page.locator(
        'button:has-text("Generate NACHA"), button:has-text("NACHA")'
      ).first();
      await generateNachaBtn.click();
      // Assert NACHA artifact appears in list with download link
      await page.waitForSelector(
        '[data-testid="file-artifact"]:has-text("NACHA"), [data-artifact-type="nacha"]',
        { timeout: 20_000 }
      );
      const nachaRow = page.locator(
        '[data-testid="file-artifact"]:has-text("NACHA"), [data-artifact-type="nacha"]'
      ).first();
      const downloadLink = nachaRow.locator('a[download], a:has-text("Download")');
      await expect(downloadLink).toBeVisible();

      // Step 13: Generate 835 file
      const generate835Btn = page.locator(
        'button:has-text("Generate 835"), button:has-text("835")'
      ).first();
      await generate835Btn.click();
      await page.waitForSelector(
        '[data-testid="file-artifact"]:has-text("835"), [data-artifact-type="x12_835"]',
        { timeout: 20_000 }
      );
      // Assert ProvenanceTrace shows Upload -> Cycle -> Batch -> File
      const provenanceTrace = page.locator('[data-testid="provenance-trace"]').first();
      await expect(provenanceTrace).toContainText(/upload/i);
      await expect(provenanceTrace).toContainText(/batch/i);

      // Step 14: Download NACHA file -> assert non-empty bytes received
      const [downloadResponse] = await Promise.all([
        page.waitForResponse(
          (resp) => resp.url().includes("/download") && resp.status() === 200
        ),
        downloadLink.click(),
      ]);
      const body = await downloadResponse.body();
      expect(body.byteLength).toBeGreaterThan(0);

      // Step 15: Navigate to Reconciliations -> finalize
      await page.goto("/admin/paysync/reconciliations");
      await expect(page.locator("h1").first()).toHaveText(/reconciliations/i);
      const finalizeBtn = page.locator(
        'button:has-text("Finalize"), button:has-text("Accept")'
      ).first();
      if (await finalizeBtn.isVisible()) {
        await finalizeBtn.click();
        await page.waitForSelector(
          '[data-status="finalized"], [data-testid="recon-status"]:has-text("finalized")',
          { timeout: 10_000 }
        );
      }
    } finally {
      await context.close();
    }
  });

  // ── AUDITOR BLOCK ─────────────────────────────────────────────────────────

  test("Step 16-22: Auditor views journal, verifies hash chain, views files and reports", async ({
    browser,
  }) => {
    test.skip(!E2E_READY, "SKIP: E2E_STACK_READY !== true — start docker-compose stack first");

    const { context, page } = await openContextAs(browser, AUDITOR_USER_ID);

    try {
      // Step 16: Open Inbox -> "journal_periodic_review" item visible
      await page.goto("/admin/paysync");
      await page.waitForSelector(
        '[data-testid="inbox-item"]:has-text("journal_periodic_review"), [data-testid="inbox-item"]:has-text("review")',
        { timeout: 15_000 }
      );

      // Step 17: Navigate to Journal -> JournalLedgerView shows entries
      await page.goto("/admin/paysync/journal");
      await expect(page.locator("h1").first()).toHaveText(/journal/i);
      await expect(page.locator('[data-testid="journal-entry"], tr[data-row-type="journal"]').first()).toBeVisible();

      // Step 18: Click HashChainVerifierPanel -> trigger verify
      const verifyBtn = page.locator(
        '[data-testid="hash-chain-verifier"] button, button:has-text("Verify Chain"), button:has-text("Verify")'
      ).first();
      await verifyBtn.click();

      // Step 19: Assert badge shows green "Chain intact — N entries verified"
      await page.waitForSelector(
        '[data-testid="hash-chain-badge"][data-status="ok"], [data-testid="hash-chain-badge"]:has-text("intact")',
        { timeout: 20_000 }
      );
      const badge = page.locator('[data-testid="hash-chain-badge"]').first();
      await expect(badge).toContainText(/intact|verified/i);

      // Step 20: Assert generate button is disabled with tooltip "Approver role required"
      const generateJournalBtn = page.locator(
        'button:has-text("Generate"), button[data-action="generate-journal"]'
      ).first();
      if (await generateJournalBtn.isVisible()) {
        await expect(generateJournalBtn).toBeDisabled();
        await generateJournalBtn.hover();
        const tooltip = page.locator('[role="tooltip"], [data-testid="tooltip"]').first();
        await expect(tooltip).toContainText(/approver/i);
      }

      // Step 21: Navigate to Files -> all files visible; generate button disabled
      await page.goto("/admin/paysync/files");
      await expect(page.locator("h1").first()).toHaveText(/files/i);
      // At least one file artifact should be visible (NACHA from approver step)
      await expect(
        page.locator('[data-testid="file-artifact"], tr[data-row-type="file"]').first()
      ).toBeVisible();
      // Download link should work
      const fileDownloadLink = page.locator('a[download], a:has-text("Download")').first();
      await expect(fileDownloadLink).toBeVisible();
      // Generate button should be disabled for auditor
      const fileGenerateBtn = page.locator(
        'button:has-text("Generate NACHA"), button:has-text("Generate 835")'
      ).first();
      if (await fileGenerateBtn.isVisible()) {
        await expect(fileGenerateBtn).toBeDisabled();
      }

      // Step 22: Navigate to Reports -> all report pages render; no errors
      const reportPaths = [
        "/admin/paysync/reports",
        "/admin/paysync/reports/period-summary",
      ];
      for (const reportPath of reportPaths) {
        const consoleErrors: string[] = [];
        page.on("console", (msg) => {
          if (msg.type() === "error") consoleErrors.push(msg.text());
        });
        await page.goto(reportPath, { waitUntil: "networkidle", timeout: 30_000 });
        await expect(page.locator("h1").first()).toBeVisible();
        const typeErrors = consoleErrors.filter((e) =>
          /TypeError|ReferenceError|SyntaxError/.test(e)
        );
        expect(typeErrors, `${reportPath} console errors`).toHaveLength(0);
      }
    } finally {
      await context.close();
    }
  });

  // ── FINAL ASSERTIONS ──────────────────────────────────────────────────────

  test("Step 23-25: Final cross-role assertions", async ({ browser }) => {
    test.skip(!E2E_READY, "SKIP: E2E_STACK_READY !== true — start docker-compose stack first");

    const { context, page } = await openContextAs(browser, OPERATOR_USER_ID);

    try {
      // Step 23: ProvenanceBreadcrumb appears on UploadDetailPage after full workflow
      if (uploadId) {
        await page.goto(`/admin/paysync/uploads/${uploadId}`);
        const breadcrumb = page.locator('[data-testid="provenance-breadcrumb"]');
        if (await breadcrumb.isVisible()) {
          await expect(breadcrumb).toContainText(/upload/i);
        }
      }

      // Step 24: RoleSwitcherChip NOT present in page source (production build check)
      // In E2E test mode the dev server is used; we verify the component is not
      // accidentally rendered in the authenticated operator view (it should only
      // appear in explicit QA panel contexts).
      await page.goto("/admin/paysync");
      const pageSource = await page.content();
      expect(pageSource).not.toMatch(/RoleSwitcherChip/);

      // Step 25: All Inbox items are in a terminal state after workflow completes.
      // "upload_validated_awaiting_batching" should no longer be pending — it was
      // converted to a batch in Step 6.
      const pendingInboxItems = page.locator(
        '[data-testid="inbox-item"][data-status="pending"], [data-testid="inbox-item"]:has-text("upload_validated_awaiting_batching")'
      );
      // Zero pending items means the workflow completed cleanly.
      // Allow 1 for the seeded pre-existing upload that may still be open.
      expect(await pendingInboxItems.count()).toBeLessThanOrEqual(1);
    } finally {
      await context.close();
    }
  });
});
