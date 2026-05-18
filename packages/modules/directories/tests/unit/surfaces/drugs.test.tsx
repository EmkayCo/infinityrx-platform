// tests/unit/surfaces/drugs.test.tsx
// Task B-3: Drugs cluster — DrugsListPage, DrugDetailPage render tests.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { DrugsListPage } from "../../../src/surfaces/drugs/DrugsListPage.js";
import { DrugDetailPage } from "../../../src/surfaces/drugs/DrugDetailPage.js";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}
function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>);
}

// ── DrugsListPage ─────────────────────────────────────────────────────────────

describe("DrugsListPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders page root", () => {
    wrap(<DrugsListPage />);
    expect(screen.getByTestId("drugs-list-page")).toBeTruthy();
  });

  it("renders FreshnessChip for fda_ndc source", () => {
    wrap(<DrugsListPage fda_ndc_last_run_at="2024-03-01" />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.textContent).toContain("fda_ndc");
  });

  it("renders FreshnessChip in red when no run date", () => {
    wrap(<DrugsListPage fda_ndc_last_run_at={null} />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip?.className).toContain("red");
  });

  it("renders search input", () => {
    wrap(<DrugsListPage />);
    expect(screen.getByTestId("drugs-search-input")).toBeTruthy();
  });

  it("renders drug rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { ndc: "12345678901", proprietary_name: "TestDrug", nonproprietary_name: "generictest" },
        ],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<DrugsListPage />);
    await userEvent.type(screen.getByTestId("drugs-search-input"), "Test");
    await waitFor(() => {
      expect(screen.getAllByTestId("drug-row").length).toBeGreaterThan(0);
    });
  });

  it("calls onNavigate with correct NDC path when row clicked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [{ ndc: "00000000001", proprietary_name: "TestRx" }],
      }),
    }));
    const navigate = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<DrugsListPage onNavigate={navigate} />);
    await userEvent.type(screen.getByTestId("drugs-search-input"), "Rx");
    await waitFor(() => expect(screen.getAllByTestId("drug-row").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("drug-row")[0].querySelector("button")!);
    expect(navigate).toHaveBeenCalledWith("/directories/drugs/00000000001");
  });
});

// ── DrugDetailPage ────────────────────────────────────────────────────────────

describe("DrugDetailPage", () => {
  const mockDrug = {
    ndc: "12345678901",
    proprietary_name: "TestDrug",
    nonproprietary_name: "testgeneric",
    strength: "10mg",
    dosage_form: "tablet",
    source_date: "2024-03-01",
    run_id: "run-drug-001",
  };

  function defaultFetch() {
    return vi.fn().mockImplementation((url: string) => {
      if (url.includes("/pricing/")) return Promise.resolve({ ok: true, json: async () => ({ records: [] }) });
      if (url.includes("/rems/")) return Promise.resolve({ ok: true, json: async () => null });
      if (url.includes("/shortages/")) return Promise.resolve({ ok: true, json: async () => null });
      return Promise.resolve({ ok: true, json: async () => mockDrug });
    });
  }

  beforeEach(() => { vi.stubGlobal("fetch", defaultFetch()); });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders drug name after loading", async () => {
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => {
      expect(screen.queryByTestId("drug-name")?.textContent).toBe("TestDrug");
    });
  });

  it("renders ProvenanceBadge for fda_ndc source", async () => {
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    expect(document.querySelector(".provenance-badge__source")?.textContent).toContain("fda_ndc");
  });

  it("renders FreshnessChip for fda_ndc source", async () => {
    wrap(<DrugDetailPage ndc="12345678901" fda_ndc_last_run_at="2024-03-01" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    expect(document.querySelector(".freshness-chip")).toBeTruthy();
  });

  it("renders all 5 tab buttons", async () => {
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    for (const tab of ["pricing", "rems", "shortages", "interactions", "formulary"]) {
      expect(screen.getByTestId(`tab-${tab}`)).toBeTruthy();
    }
  });

  it("renders Pricing tab with BPG live-API label (default tab)", async () => {
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("pricing-tab")).toBeTruthy());
    expect(screen.getByTestId("bpg-live-api-label").textContent).toBe("Live API — no ingestion schedule");
  });

  it("renders BPG doc link in Pricing tab", async () => {
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("bpg-doc-link")).toBeTruthy());
  });

  it("shows pricing rows when pricing data available", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/pricing/")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            records: [
              { effective_date: "2024-01-01", price: "12.50", source: "cms_asp" },
              { effective_date: "2024-02-01", price: "10.00", source: "cms_nadac" },
            ],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => mockDrug });
    }));
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => {
      expect(screen.getAllByTestId("pricing-row").length).toBe(2);
    });
  });

  it("renders B9PendingBanner on Interactions tab (not an error state)", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    await userEvent.click(screen.getByTestId("tab-interactions"));
    expect(screen.getByTestId("interactions-tab")).toBeTruthy();
    // B9PendingBanner renders a div with className="b9-pending-banner"
    expect(document.querySelector(".b9-pending-banner")).toBeTruthy();
  });

  it("renders B9PendingBanner on Formulary tab (not an error state)", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    await userEvent.click(screen.getByTestId("tab-formulary"));
    expect(screen.getByTestId("formulary-tab")).toBeTruthy();
    expect(document.querySelector(".b9-pending-banner")).toBeTruthy();
  });

  it("renders REMS tab content when REMS data exists", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("/rems/")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ program_name: "REMS-PROG-X", required: true, description: "Risk mgmt" }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => mockDrug });
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<DrugDetailPage ndc="12345678901" />);
    await waitFor(() => expect(screen.queryByTestId("drug-detail-page")).toBeTruthy());
    await userEvent.click(screen.getByTestId("tab-rems"));
    await waitFor(() => {
      expect(screen.queryByTestId("rems-program")?.textContent).toBe("REMS-PROG-X");
    });
  });
});
