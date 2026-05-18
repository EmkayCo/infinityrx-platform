// tests/unit/quality/QualityDashboardPanel.test.tsx
// QualityDashboardPanel component tests (SP-2 Plan D Task D-3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { QualityDashboardPanel } from "../../../src/quality/QualityDashboardPanel.js";

const mockFetch = vi.fn();

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function wrap(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>,
  );
}

function isoDateDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

const FULL_QUALITY_RESPONSE = {
  datasets: [
    {
      source: "nppes",
      cluster: "prescribers",
      last_run_at: isoDateDaysAgo(1),
      last_success_at: isoDateDaysAgo(1),
      last_run_status: "completed",
      records_inserted: 7000000,
      records_errored: 0,
      cron_expression: "0 3 1 * *",
      next_run_at: isoDateDaysAgo(-30),
      is_dismissed: false,
      no_loader: false,
      b9_blocked: false,
    },
    {
      source: "ncpdp",
      cluster: "pharmacies",
      last_run_at: isoDateDaysAgo(10),
      last_success_at: isoDateDaysAgo(10),
      last_run_status: "completed",
      records_inserted: 65000,
      records_errored: 0,
      cron_expression: null,
      next_run_at: null,
      is_dismissed: false,
      no_loader: false,
      b9_blocked: false,
    },
    {
      source: "fdb",
      cluster: "drugs",
      last_run_at: null,
      last_success_at: null,
      last_run_status: null,
      records_inserted: null,
      records_errored: null,
      cron_expression: null,
      next_run_at: null,
      is_dismissed: false,
      no_loader: true,
      b9_blocked: true,
    },
  ],
  as_of: new Date().toISOString(),
  is_partial: false,
};

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => FULL_QUALITY_RESPONSE,
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("QualityDashboardPanel", () => {
  it("renders loading state initially", () => {
    // Make fetch never resolve to hold in loading state.
    mockFetch.mockReturnValue(new Promise(() => {}));
    wrap(<QualityDashboardPanel />);
    expect(screen.getByText(/loading data quality/i)).toBeTruthy();
  });

  it("renders one FreshnessChip row per dataset after loading", async () => {
    wrap(<QualityDashboardPanel />);
    await waitFor(() =>
      expect(screen.getByText(/nppes/)).toBeTruthy(),
    );
    // Three rows in the fixture.
    const rows = document.querySelectorAll("[data-source]");
    expect(rows.length).toBeGreaterThanOrEqual(3);
  });

  it("source loaded today shows green chip (0 days ago)", async () => {
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/nppes/));
    // The FreshnessChip for nppes (last_run_at = 1 day ago → green) should render green class.
    const nppesChip = document.querySelector('[data-source="nppes"] .freshness-chip');
    expect(nppesChip?.className).toMatch(/green/i);
  });

  it("source loaded 10 days ago shows yellow chip", async () => {
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/ncpdp/));
    const ncpdpChip = document.querySelector('[data-source="ncpdp"] .freshness-chip');
    expect(ncpdpChip?.className).toMatch(/yellow/i);
  });

  it("source with null last_run_at shows red chip and 'Never loaded'", async () => {
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/fdb/));
    const fdbChip = document.querySelector('[data-source="fdb"] .freshness-chip');
    expect(fdbChip?.className).toMatch(/red/i);
    expect(fdbChip?.textContent).toMatch(/never loaded/i);
  });

  it("source with records_errored > 0 shows error badge", async () => {
    const responseWithErrors = {
      ...FULL_QUALITY_RESPONSE,
      datasets: [
        {
          ...FULL_QUALITY_RESPONSE.datasets[0],
          records_errored: 42,
        },
      ],
    };
    mockFetch.mockResolvedValue({ ok: true, json: async () => responseWithErrors });
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/42 errors/i));
    expect(screen.getByText(/42 errors/i)).toBeTruthy();
  });

  it("source with last_run_status 'failed' appears in alert list", async () => {
    const responseWithFailed = {
      ...FULL_QUALITY_RESPONSE,
      datasets: [
        {
          ...FULL_QUALITY_RESPONSE.datasets[0],
          last_run_status: "failed",
          // Within 7-day window.
          last_run_at: isoDateDaysAgo(1),
        },
      ],
    };
    mockFetch.mockResolvedValue({ ok: true, json: async () => responseWithFailed });
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/run failed/i));
    expect(screen.getByText(/run failed/i)).toBeTruthy();
  });

  it("shows partial banner when is_partial is true", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ...FULL_QUALITY_RESPONSE, is_partial: true }),
    });
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/some backend services were unreachable/i));
    expect(screen.getByText(/some backend services were unreachable/i)).toBeTruthy();
  });

  it("shows error state when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("network error"));
    wrap(<QualityDashboardPanel />);
    await waitFor(() => screen.getByText(/unable to load quality data/i));
    expect(screen.getByText(/unable to load quality data/i)).toBeTruthy();
  });
});
