// tests/unit/surfaces/prescribers.test.tsx
// Task B-1: Prescribers cluster — PrescribersListPage, PrescriberDetailPage,
// PrescriberMonitoringPanel render tests.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PrescribersListPage } from "../../../src/surfaces/prescribers/PrescribersListPage.js";
import { PrescriberDetailPage } from "../../../src/surfaces/prescribers/PrescriberDetailPage.js";
import { PrescriberMonitoringPanel } from "../../../src/surfaces/prescribers/PrescriberMonitoringPanel.js";

function makeClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function wrap(ui: React.ReactElement, client?: QueryClient) {
  const qc = client ?? makeClient();
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// ── PrescribersListPage ───────────────────────────────────────────────────────

describe("PrescribersListPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [], total: 0, page: 1, page_size: 50 }),
    }));
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders the page root", () => {
    wrap(<PrescribersListPage />);
    expect(screen.getByTestId("prescribers-list-page")).toBeTruthy();
  });

  it("renders search input", () => {
    wrap(<PrescribersListPage />);
    expect(screen.getByTestId("prescribers-search-input")).toBeTruthy();
  });

  it("shows empty hint when no search text", () => {
    wrap(<PrescribersListPage />);
    expect(screen.getByTestId("empty-hint")).toBeTruthy();
  });

  it("calls onNavigate when 10-digit NPI is entered", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const navigate = vi.fn();
    wrap(<PrescribersListPage onNavigate={navigate} />);
    const input = screen.getByTestId("prescribers-search-input");
    await userEvent.type(input, "1234567890");
    await waitFor(() => expect(navigate).toHaveBeenCalledWith("/directories/prescribers/1234567890"));
  });

  it("calls backend search when >= 2 non-NPI characters entered", async () => {
    // fetch is already stubbed in beforeEach — capture it and type a search term
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [], total: 0, page: 1, page_size: 50 }),
    });
    vi.stubGlobal("fetch", fetchSpy);
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PrescribersListPage />);
    await userEvent.type(screen.getByTestId("prescribers-search-input"), "Sm");
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
  });

  it("renders prescriber rows when query returns results", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [{ npi: "1234509876", display_name: "Dr. Alice Smith", status: "active" }],
        total: 1,
        page: 1,
        page_size: 50,
      }),
    });
    vi.stubGlobal("fetch", mockFetch);
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PrescribersListPage />);
    await userEvent.type(screen.getByTestId("prescribers-search-input"), "Alice");
    await waitFor(() => {
      expect(screen.getAllByTestId("prescriber-row").length).toBeGreaterThan(0);
    });
  });
});

// ── PrescriberDetailPage ──────────────────────────────────────────────────────

describe("PrescriberDetailPage", () => {
  const mockPrescriber = {
    npi: "1234567890",
    display_name: "Dr. Jane Doe",
    primary_specialty: "Internal Medicine",
    source_date: "2024-03-15",
    run_id: "run-abc-123",
  };

  function makeDefaultFetch() {
    return vi.fn().mockImplementation((url: string) => {
      if (url.includes("exclusion-check")) {
        return Promise.resolve({ ok: true, json: async () => ({ sources: [] }) });
      }
      if (url.includes("monitoring/alerts")) {
        return Promise.resolve({ ok: true, json: async () => ({ alerts: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => mockPrescriber });
    });
  }

  beforeEach(() => {
    vi.stubGlobal("fetch", makeDefaultFetch());
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders prescriber name after loading", async () => {
    wrap(<PrescriberDetailPage npi="1234567890" />);
    await waitFor(() => {
      const el = screen.queryByTestId("prescriber-name");
      expect(el).toBeTruthy();
      expect(el?.textContent).toBe("Dr. Jane Doe");
    });
  });

  it("renders ProvenanceBadge with source key nppes", async () => {
    wrap(<PrescriberDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("prescriber-detail-page")).toBeTruthy();
    });
    const badge = document.querySelector(".provenance-badge__source");
    expect(badge).toBeTruthy();
    expect(badge?.textContent).toContain("nppes");
  });

  it("renders FreshnessChip for nppes source", async () => {
    wrap(<PrescriberDetailPage npi="1234567890" nppes_last_run_at="2024-03-15" />);
    await waitFor(() => {
      expect(screen.queryByTestId("prescriber-detail-page")).toBeTruthy();
    });
    expect(document.querySelector(".freshness-chip")).toBeTruthy();
  });

  it("does NOT show ExclusionAlertBadge when no exclusion sources", async () => {
    wrap(<PrescriberDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("prescriber-detail-page")).toBeTruthy();
    });
    // Wait a bit for exclusion check to resolve (it's a separate query)
    await new Promise((r) => setTimeout(r, 50));
    expect(document.querySelector(".exclusion-alert-badge")).toBeNull();
  });

  it("shows ExclusionAlertBadge when exclusion sources are non-empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("exclusion-check")) {
        return Promise.resolve({ ok: true, json: async () => ({ sources: ["cms_opt_out"] }) });
      }
      if (url.includes("monitoring/alerts")) {
        return Promise.resolve({ ok: true, json: async () => ({ alerts: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => mockPrescriber });
    }));
    wrap(<PrescriberDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(document.querySelector(".exclusion-alert-badge")).toBeTruthy();
    });
  });

  it("renders monitoring panel (PrescriberMonitoringPanel present)", async () => {
    wrap(<PrescriberDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("prescriber-detail-page")).toBeTruthy();
    });
    expect(screen.queryByTestId("monitoring-panel")).toBeTruthy();
  });
});

// ── PrescriberMonitoringPanel ─────────────────────────────────────────────────

describe("PrescriberMonitoringPanel", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders loading state initially", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => { /* never resolves */ })));
    wrap(<PrescriberMonitoringPanel npi="1234567890" />);
    expect(screen.getByTestId("alerts-loading")).toBeTruthy();
  });

  it("renders empty state when no alerts returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ alerts: [] }),
    }));
    wrap(<PrescriberMonitoringPanel npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("no-alerts")).toBeTruthy();
    });
  });

  it("renders alert rows with type and severity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        alerts: [
          { alert_id: "a1", alert_type: "High Volume", severity: "high", created_at: "2024-01-01", description: "Volume spike" },
          { alert_id: "a2", alert_type: "Off-Label", severity: "medium", created_at: "2024-01-02", description: "Pattern detected" },
        ],
      }),
    }));
    wrap(<PrescriberMonitoringPanel npi="1234567890" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("alert-row").length).toBe(2);
    });
    expect(screen.getAllByTestId("alert-type")[0]?.textContent).toBe("High Volume");
  });

  it("does NOT render an acknowledge button (out of SP-2 scope per spec §3)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        alerts: [
          { alert_id: "a1", alert_type: "High Volume", severity: "high", created_at: "2024-01-01", description: "Test" },
        ],
      }),
    }));
    wrap(<PrescriberMonitoringPanel npi="1234567890" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("alert-row").length).toBeGreaterThan(0);
    });
    // No acknowledge button must exist
    expect(document.querySelectorAll("[data-testid='acknowledge-btn']").length).toBe(0);
  });
});
