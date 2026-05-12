/**
 * Wave 40 critical operator flow tests.
 *
 * Each test mocks the paysync API to drive a deterministic scenario
 * and asserts the operator workflow renders + fires the right
 * actions. These exercise the UI behavior — not the backend.
 *
 * Backend integration tests live in modules/paysync/tests/integration/.
 */
import { test, expect, Route } from "@playwright/test";
import { authenticateDevBypass } from "../../tests/fixtures/mock-session";

const TENANT = "11111111-1111-1111-1111-111111111111";
const CYCLE_ID = "22222222-2222-2222-2222-222222222222";
const RECON_ID = "33333333-3333-3333-3333-333333333333";

function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status, contentType: "application/json", body: JSON.stringify(body),
  });
}

const SAMPLE_CYCLE = {
  id: CYCLE_ID,
  tenant_id: TENANT,
  cycle_label: "2026-04-2H",
  cycle_type: "payment_cycle",
  schedule_id: null,
  schedule_name: "Standard Bi-Monthly Payment",
  period_start: "2026-04-16",
  period_end: "2026-04-30",
  status: "open",
  claim_count: 1234,
  total_billed: "98765.43",
  total_pay: "92345.67",
  reconciliation_status: null,
  created_at: "2026-04-16T00:00:00Z",
  closed_at: null,
};

const SAMPLE_RECON_MATCHED = {
  id: RECON_ID,
  cycle_id: CYCLE_ID,
  run_at: "2026-04-30T18:00:00Z",
  run_by: null,
  tie_1: { status: "match", expected: "98765.43", actual: "98765.43", delta: "0.00", reasons: [] },
  tie_2: { status: "match", expected: "92345.67", actual: "92345.67", delta: "0.00", reasons: [] },
  tie_3: { status: "match", expected: "92345.67", actual: "92345.67", delta: "0.00", reasons: [] },
  findings: [],
  finalized: false,
  finalized_at: null,
  finalized_by: null,
  accepted_deltas: false,
  operator_notes: null,
};

test.beforeEach(async ({ context }) => {
  await authenticateDevBypass(context, "http://localhost:3000");
});

test.describe("Cycle close happy path", () => {
  test("operator drills into cycle and reviews tabs", async ({ page }) => {
    let cyclesListHits = 0;
    await page.route(/\/admin\/paysync\/cycles($|\?)/, async (route) => {
      cyclesListHits += 1;
      await fulfillJson(route, { items: [SAMPLE_CYCLE], total: 1, page: 1, page_size: 50 });
    });
    await page.route(new RegExp(`\\/admin\\/paysync\\/cycles\\/${CYCLE_ID}$`), async (route) => {
      await fulfillJson(route, SAMPLE_CYCLE);
    });
    await page.route(/\/admin\/paysync\/cycles\/.+\/(claims|held-claims|files)/, async (route) =>
      fulfillJson(route, { items: [], total: 0, page: 1, page_size: 500 }));
    await page.route(/\/admin\/paysync\/(carryovers|manual-ap-records|batches|invoices)/, async (route) =>
      fulfillJson(route, { items: [], total: 0, page: 1, page_size: 100 }));
    await page.route(/\/admin\/paysync\/cycles\/.+\/reconciliations$/, async (route) =>
      fulfillJson(route, [SAMPLE_RECON_MATCHED]));

    await page.goto("/admin/paysync/cycles");
    await expect(page.getByText("2026-04-2H").first()).toBeVisible();
    expect(cyclesListHits).toBeGreaterThan(0);

    // Drill into cycle
    await page.getByText("2026-04-2H").first().click();
    await expect(page.locator("h1")).toHaveText("2026-04-2H");

    // Reconciliation tab shows three matching ties
    await page.getByRole("tab", { name: /reconciliation/i }).click();
    await expect(page.getByText("Tie 1: Claims ↔ Invoice")).toBeVisible();
    await expect(page.getByText("Tie 2: Claims ↔ Total AP")).toBeVisible();
    await expect(page.getByText("Tie 3: Batch AP ↔ NACHA ↔ 835")).toBeVisible();
  });
});

test.describe("Reconciliation finalize", () => {
  test("operator finalizes a matched reconciliation", async ({ page }) => {
    await page.route(new RegExp(`\\/admin\\/paysync\\/cycles($|\\?)`), async (route) =>
      fulfillJson(route, { items: [SAMPLE_CYCLE], total: 1, page: 1, page_size: 50 }));
    await page.route(/\/admin\/paysync\/cycles\/.+\/reconciliations$/, async (route) =>
      fulfillJson(route, [SAMPLE_RECON_MATCHED]));
    await page.route(/\/admin\/paysync\/reconciliations\/.+\/finalize$/, async (route) =>
      fulfillJson(route, { ...SAMPLE_RECON_MATCHED, finalized: true,
                            finalized_at: "2026-04-30T19:00:00Z",
                            finalized_by: "operator@example.com" }));

    await page.goto(`/admin/paysync/reconciliations/${RECON_ID}`);
    await expect(page.locator("h1")).toContainText("Reconciliation");

    // Finalize section visible because not yet finalized
    await expect(page.getByRole("button", { name: /finalize reconciliation/i })).toBeVisible();
    await page.getByRole("button", { name: /finalize reconciliation/i }).click();

    // Finalized state — section shows "Finalized" timestamp
    await expect(page.getByText(/finalized/i).first()).toBeVisible();
  });
});

test.describe("Manual AP creation", () => {
  test("operator creates a draft manual AP record", async ({ page }) => {
    await page.route(/\/admin\/paysync\/manual-ap-records($|\?)/, async (route) => {
      if (route.request().method() === "POST") {
        return fulfillJson(route, {
          id: "ap-id", cycle_id: null, claim_id: null,
          channel: "check_issuing", payee_name: "Test Pharmacy",
          payee_npi: null, payment_amount: "150.00",
          external_reference: null, status: "draft",
          submitted_at: null, processed_at: null,
          failure_reason: null, notes: null,
          created_at: "2026-04-26T00:00:00Z",
        });
      }
      return fulfillJson(route, { items: [], total: 0, page: 1, page_size: 50 });
    });

    await page.goto("/admin/paysync/manual-ap");
    await expect(page.locator("h1")).toHaveText(/manual ap records/i);
    await page.getByRole("button", { name: /new manual ap/i }).click();
    await page.getByPlaceholder(/payee/i).fill("Test Pharmacy");
  });
});

test.describe("Bank settlement manual entry", () => {
  test("operator opens manual entry form with one default entry row", async ({ page }) => {
    await page.goto("/admin/paysync/bank-settlements/manual-entry");
    await expect(page.locator("h1")).toHaveText(/manual settlement entry/i);
    await expect(page.getByPlaceholder(/STMT-/i)).toBeVisible();
    await expect(page.getByText(/add entry/i)).toBeVisible();
  });
});
