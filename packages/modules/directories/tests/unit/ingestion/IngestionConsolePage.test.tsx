// tests/unit/ingestion/IngestionConsolePage.test.tsx
// IngestionConsolePage unit tests (SP-2 Plan C Task C-3).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}));

import { IngestionConsolePage } from "../../../src/ingestion/IngestionConsolePage.js";

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

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  // Default: status returns empty list
  mockFetch.mockResolvedValue({
    ok: true,
    json: async () => [],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Row count and structure
// ---------------------------------------------------------------------------

describe("IngestionConsolePage row structure", () => {
  it("renders the page root", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-console-page")).toBeTruthy(),
    );
  });

  it("renders a table with one row per source (22 total: 20 triggerable + bpg + fdb)", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-console-table")).toBeTruthy(),
    );

    const rows = screen.getAllByTestId(/^ingestion-row-/);
    expect(rows.length).toBe(22);
  });

  it("includes bpg row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-bpg")).toBeTruthy(),
    );
  });

  it("includes fdb row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-fdb")).toBeTruthy(),
    );
  });

  it("does NOT include relay-health row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-console-table")).toBeTruthy(),
    );
    expect(screen.queryByTestId("ingestion-row-relay-health")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Non-loader source treatment
// ---------------------------------------------------------------------------

describe("Non-loader source static status", () => {
  it("shows 'Live API — no schedule' for bpg row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("status-static-bpg")).toBeTruthy(),
    );
    expect(screen.getByTestId("status-static-bpg").textContent).toBe(
      "Live API — no schedule",
    );
  });

  it("shows 'Pending B9' for fdb row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("status-static-fdb")).toBeTruthy(),
    );
    expect(screen.getByTestId("status-static-fdb").textContent).toBe(
      "Pending B9",
    );
  });

  it("does NOT render a trigger button in the bpg row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-bpg")).toBeTruthy(),
    );
    expect(screen.queryByTestId("trigger-refresh-bpg")).toBeNull();
  });

  it("does NOT render a trigger button in the fdb row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-fdb")).toBeTruthy(),
    );
    expect(screen.queryByTestId("trigger-refresh-fdb")).toBeNull();
  });

  it("does NOT render a history link in the bpg row", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-bpg")).toBeTruthy(),
    );
    expect(screen.queryByTestId("view-history-bpg")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Errors badge
// ---------------------------------------------------------------------------

describe("Errors badge", () => {
  it("shows orange errors badge when records_errored > 0", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          source: "fda_ndc",
          cron_expression: "0 2 * * *",
          enabled: true,
          last_run: {
            id: "run-1",
            status: "completed",
            started_at: "2026-05-17T02:00:00Z",
            finished_at: "2026-05-17T03:00:00Z",
            records_inserted: 1000,
            records_updated: 0,
            records_errored: 5,
            records_in_source: null,
            error_message: null,
          },
          next_run_at: null,
        },
      ],
    });

    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("errors-badge-fda_ndc")).toBeTruthy(),
    );
    expect(screen.getByTestId("errors-badge-fda_ndc").textContent).toBe("5");
  });

  it("does not show errors badge when records_errored is 0", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          source: "fda_ndc",
          cron_expression: "0 2 * * *",
          enabled: true,
          last_run: {
            id: "run-1",
            status: "completed",
            started_at: "2026-05-17T02:00:00Z",
            finished_at: null,
            records_inserted: 500,
            records_updated: 0,
            records_errored: 0,
            records_in_source: null,
            error_message: null,
          },
          next_run_at: null,
        },
      ],
    });

    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("ingestion-row-fda_ndc")).toBeTruthy(),
    );
    expect(screen.queryByTestId("errors-badge-fda_ndc")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Trigger buttons on triggerable sources
// ---------------------------------------------------------------------------

describe("Trigger buttons on triggerable sources", () => {
  it("renders TriggerRefreshButton for fda_ndc", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("trigger-refresh-fda_ndc")).toBeTruthy(),
    );
  });

  it("renders history link for nppes", async () => {
    wrap(<IngestionConsolePage />);
    await waitFor(() =>
      expect(screen.getByTestId("view-history-nppes")).toBeTruthy(),
    );
  });
});
