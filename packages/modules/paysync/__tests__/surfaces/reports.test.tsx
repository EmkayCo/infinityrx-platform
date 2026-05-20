// packages/modules/paysync/__tests__/surfaces/reports.test.tsx
// RTL tests for the reports surface: CycleReportsPage, JournalEntriesReportPage,
// PeriodSummaryPage, ReportsListPage, and BFF handlers.
// Read-only surface -- no mutation tests, no RbacGate mutation flows.
// Uses happy-dom. cleanup() in afterEach.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Cycle, JournalEntry } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeCycle(overrides: Partial<Cycle> = {}): Cycle {
  return {
    id: "c0000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    period_label: "2026-05",
    status: "closed",
    window_closed_at: NOW,
    origin_upload_id: null,
    total_billed_amount: "98765.43",
    claim_count: 150,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

function makeJournalEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: "j0000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    entry_date: "2026-05-01",
    entry_timestamp: NOW,
    entry_type: "rebate",
    client_id: null,
    client_name: null,
    program_id: null,
    program_name: null,
    pay_to_entity_id: null,
    pay_to_entity_name: null,
    amount: "1234.56",
    category: "rebate",
    gl_account_code: "4000",
    gl_class: null,
    reference_type: null,
    reference_id: null,
    description: "Rebate payment",
    exported_to_accounting: false,
    exported_at: null,
    export_reference: null,
    created_at: NOW,
    entry_hash: "abc12345def67890abc12345def67890abc12345def67890abc12345def67890",
    prev_hash: null,
    ...overrides,
  };
}

// ── ReportsListPage ──────────────────────────────────────────────────────

describe("ReportsListPage", () => {
  let ReportsListPage: typeof import("../../src/surfaces/reports/ReportsListPage.js").ReportsListPage;

  beforeEach(async () => {
    ({ ReportsListPage } = await import("../../src/surfaces/reports/ReportsListPage.js"));
  });

  it("renders the reports list page container", () => {
    render(<ReportsListPage />);
    expect(screen.getByTestId("reports-list-page")).toBeTruthy();
  });

  it("renders a link to cycle reports", () => {
    render(<ReportsListPage />);
    expect(screen.getByTestId("reports-link-cycles")).toBeTruthy();
  });

  it("renders a link to journal entries report", () => {
    render(<ReportsListPage />);
    expect(screen.getByTestId("reports-link-journal")).toBeTruthy();
  });

  it("renders a link to period summary report", () => {
    render(<ReportsListPage />);
    expect(screen.getByTestId("reports-link-period-summary")).toBeTruthy();
  });

  it("renders a heading for the reports index", () => {
    render(<ReportsListPage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeTruthy();
  });
});

// ── CycleReportsPage ─────────────────────────────────────────────────────

describe("CycleReportsPage", () => {
  let CycleReportsPage: typeof import("../../src/surfaces/reports/CycleReportsPage.js").CycleReportsPage;

  beforeEach(async () => {
    ({ CycleReportsPage } = await import("../../src/surfaces/reports/CycleReportsPage.js"));
  });

  it("renders the cycle reports page container", () => {
    render(<CycleReportsPage cycles={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("cycle-reports-page")).toBeTruthy();
  });

  it("renders a row for each cycle", () => {
    const cycles = [makeCycle({ id: "c1" }), makeCycle({ id: "c2", period_label: "2026-04" })];
    render(<CycleReportsPage cycles={cycles} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("cycle-report-row")).toHaveLength(2);
  });

  it("renders period_label for each cycle", () => {
    render(<CycleReportsPage cycles={[makeCycle()]} isLoading={false} error={null} />);
    expect(screen.getByText("2026-05")).toBeTruthy();
  });

  it("renders status badge per cycle", () => {
    render(<CycleReportsPage cycles={[makeCycle({ status: "open" })]} isLoading={false} error={null} />);
    const badge = screen.getByTestId("cycle-report-status-badge");
    expect(badge.getAttribute("data-status")).toBe("open");
  });

  it("renders MoneyDisplay for total_billed_amount", () => {
    render(<CycleReportsPage cycles={[makeCycle()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders dash when total_billed_amount is null (open cycle)", () => {
    render(<CycleReportsPage cycles={[makeCycle({ total_billed_amount: null, status: "open" })]} isLoading={false} error={null} />);
    expect(screen.getByLabelText("not yet available")).toBeTruthy();
  });

  it("renders loading state when isLoading=true", () => {
    render(<CycleReportsPage cycles={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("cycle-reports-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<CycleReportsPage cycles={[]} isLoading={false} error="Backend unavailable" />);
    expect(screen.getByTestId("cycle-reports-error")).toBeTruthy();
  });

  it("renders empty state when no cycles", () => {
    render(<CycleReportsPage cycles={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("cycle-reports-empty")).toBeTruthy();
  });

  it("renders export button as disabled (not hidden)", () => {
    render(<CycleReportsPage cycles={[]} isLoading={false} error={null} />);
    const exportNotice = screen.getByTestId("export-disabled-notice");
    const btn = exportNotice.querySelector("button");
    expect(btn).toBeTruthy();
    expect(btn?.disabled).toBe(true);
  });

  it("export button title mentions future release", () => {
    render(<CycleReportsPage cycles={[]} isLoading={false} error={null} />);
    const btn = screen.getByTitle(/future release/i);
    expect(btn).toBeTruthy();
  });
});

// ── JournalEntriesReportPage ──────────────────────────────────────────────

describe("JournalEntriesReportPage", () => {
  let JournalEntriesReportPage: typeof import("../../src/surfaces/reports/JournalEntriesReportPage.js").JournalEntriesReportPage;

  beforeEach(async () => {
    ({ JournalEntriesReportPage } = await import("../../src/surfaces/reports/JournalEntriesReportPage.js"));
  });

  it("renders the journal entries report page container", () => {
    render(<JournalEntriesReportPage entries={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-entries-report-page")).toBeTruthy();
  });

  it("renders a row for each journal entry", () => {
    const entries = [makeJournalEntry({ id: "j1" }), makeJournalEntry({ id: "j2" })];
    render(<JournalEntriesReportPage entries={entries} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("journal-report-entry-row")).toHaveLength(2);
  });

  it("renders MoneyDisplay for each entry amount", () => {
    render(<JournalEntriesReportPage entries={[makeJournalEntry()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders gl_account_code for each entry", () => {
    render(<JournalEntriesReportPage entries={[makeJournalEntry()]} isLoading={false} error={null} />);
    expect(screen.getByText("4000")).toBeTruthy();
  });

  it("renders entry_type for each entry", () => {
    render(<JournalEntriesReportPage entries={[makeJournalEntry()]} isLoading={false} error={null} />);
    expect(screen.getByText("rebate")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<JournalEntriesReportPage entries={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("journal-entries-report-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<JournalEntriesReportPage entries={[]} isLoading={false} error="Fetch failed" />);
    expect(screen.getByTestId("journal-entries-report-error")).toBeTruthy();
  });

  it("renders empty state when no entries", () => {
    render(<JournalEntriesReportPage entries={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-entries-report-empty")).toBeTruthy();
  });

  it("renders export button as disabled with future-release title", () => {
    render(<JournalEntriesReportPage entries={[]} isLoading={false} error={null} />);
    const btn = screen.getByTitle(/future release/i);
    expect(btn).toBeTruthy();
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });
});

// ── PeriodSummaryPage ─────────────────────────────────────────────────────

describe("PeriodSummaryPage", () => {
  let PeriodSummaryPage: typeof import("../../src/surfaces/reports/PeriodSummaryPage.js").PeriodSummaryPage;

  beforeEach(async () => {
    ({ PeriodSummaryPage } = await import("../../src/surfaces/reports/PeriodSummaryPage.js"));
  });

  it("renders the period summary page container", () => {
    render(
      <PeriodSummaryPage
        periodLabel="2026-05"
        totalBilled="98765.43"
        totalPaid="95000.00"
        totalVariance="3765.43"
        totalAdjustments="500.00"
        totalFees="250.00"
        claimCount={150}
        cycleCount={2}
        invoiceCount={5}
        paymentRunCount={3}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("period-summary-page")).toBeTruthy();
  });

  it("renders the period label", () => {
    render(
      <PeriodSummaryPage
        periodLabel="2026-04"
        totalBilled="10000.00"
        totalPaid="9500.00"
        totalVariance="500.00"
        totalAdjustments="0.00"
        totalFees="100.00"
        claimCount={50}
        cycleCount={1}
        invoiceCount={2}
        paymentRunCount={1}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("period-summary-period-label")).toBeTruthy();
    expect(screen.getByText("2026-04")).toBeTruthy();
  });

  it("renders MoneyDisplay for totalBilled", () => {
    render(
      <PeriodSummaryPage
        periodLabel="2026-05"
        totalBilled="98765.43"
        totalPaid="95000.00"
        totalVariance="3765.43"
        totalAdjustments="500.00"
        totalFees="250.00"
        claimCount={150}
        cycleCount={2}
        invoiceCount={5}
        paymentRunCount={3}
        isLoading={false}
        error={null}
      />,
    );
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(3);
  });

  it("renders claim count", () => {
    render(
      <PeriodSummaryPage
        periodLabel="2026-05"
        totalBilled="98765.43"
        totalPaid="95000.00"
        totalVariance="3765.43"
        totalAdjustments="500.00"
        totalFees="250.00"
        claimCount={150}
        cycleCount={2}
        invoiceCount={5}
        paymentRunCount={3}
        isLoading={false}
        error={null}
      />,
    );
    expect(screen.getByTestId("period-summary-claim-count")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(
      <PeriodSummaryPage
        periodLabel=""
        totalBilled={null}
        totalPaid={null}
        totalVariance={null}
        totalAdjustments={null}
        totalFees={null}
        claimCount={0}
        cycleCount={0}
        invoiceCount={0}
        paymentRunCount={0}
        isLoading={true}
        error={null}
      />,
    );
    expect(screen.getByTestId("period-summary-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <PeriodSummaryPage
        periodLabel=""
        totalBilled={null}
        totalPaid={null}
        totalVariance={null}
        totalAdjustments={null}
        totalFees={null}
        claimCount={0}
        cycleCount={0}
        invoiceCount={0}
        paymentRunCount={0}
        isLoading={false}
        error="Period not found"
      />,
    );
    expect(screen.getByTestId("period-summary-error")).toBeTruthy();
  });
});

// ── BFF: handleListCycleReports ────────────────────────────────────────────

describe("BFF handleListCycleReports", () => {
  let handleListCycleReports: typeof import("../../src/surfaces/reports/bff/reports.js").handleListCycleReports;
  let handleListJournalEntriesReport: typeof import("../../src/surfaces/reports/bff/reports.js").handleListJournalEntriesReport;
  let handleGetPeriodSummary: typeof import("../../src/surfaces/reports/bff/reports.js").handleGetPeriodSummary;

  beforeEach(async () => {
    ({ handleListCycleReports, handleListJournalEntriesReport, handleGetPeriodSummary } =
      await import("../../src/surfaces/reports/bff/reports.js"));
  });

  it("handleListCycleReports returns 200 with data from client", async () => {
    const mockClient = {
      list: vi.fn().mockResolvedValue({ results: [makeCycle()], total: 1, next_cursor: null }),
    };
    const result = await handleListCycleReports(
      { headers: {}, searchParams: new URLSearchParams() },
      mockClient as never,
    );
    expect(result.status).toBe(200);
    expect(result.data.results).toHaveLength(1);
  });

  it("handleListCycleReports passes limit from searchParams", async () => {
    const mockClient = {
      list: vi.fn().mockResolvedValue({ results: [], total: 0, next_cursor: null }),
    };
    await handleListCycleReports(
      { headers: {}, searchParams: new URLSearchParams("limit=25") },
      mockClient as never,
    );
    expect(mockClient.list).toHaveBeenCalledWith(expect.objectContaining({ limit: 25 }));
  });

  it("handleListJournalEntriesReport returns 200 with data from client", async () => {
    const mockClient = {
      list: vi.fn().mockResolvedValue({ results: [makeJournalEntry()], total: 1, next_cursor: null }),
    };
    const result = await handleListJournalEntriesReport(
      { headers: {}, searchParams: new URLSearchParams() },
      mockClient as never,
    );
    expect(result.status).toBe(200);
    expect(result.data.results).toHaveLength(1);
  });

  it("handleGetPeriodSummary returns 404 when summary is null", async () => {
    const mockClient = {
      getPeriodSummary: vi.fn().mockResolvedValue(null),
    };
    const result = await handleGetPeriodSummary(
      "2026-05",
      { headers: {} },
      mockClient as never,
    );
    expect(result.status).toBe(404);
  });

  it("handleGetPeriodSummary returns 200 with no-store header", async () => {
    const summary = {
      period_label: "2026-05",
      tenant_id: TENANT,
      total_claims: 100,
      total_billed: "10000.00",
      total_paid: "9500.00",
      total_adjustments: "0.00",
      total_fees: "100.00",
      total_variance: "400.00",
      cycle_count: 1,
      invoice_count: 2,
      payment_run_count: 1,
      generated_at: NOW,
    };
    const mockClient = {
      getPeriodSummary: vi.fn().mockResolvedValue(summary),
    };
    const result = await handleGetPeriodSummary(
      "2026-05",
      { headers: {} },
      mockClient as never,
    );
    expect(result.status).toBe(200);
    expect(result.headers["Cache-Control"]).toBe("no-store");
  });
});
