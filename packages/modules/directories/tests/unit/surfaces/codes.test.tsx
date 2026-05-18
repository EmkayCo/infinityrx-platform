// tests/unit/surfaces/codes.test.tsx
// Task B-4: Codes cluster — HcpcsListPage, Icd10ListPage render tests.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { HcpcsListPage } from "../../../src/surfaces/codes/HcpcsListPage.js";
import { Icd10ListPage } from "../../../src/surfaces/codes/Icd10ListPage.js";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}
function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>);
}

// ── HcpcsListPage ─────────────────────────────────────────────────────────────

describe("HcpcsListPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders page root with title", () => {
    wrap(<HcpcsListPage />);
    expect(screen.getByTestId("hcpcs-list-page")).toBeTruthy();
    expect(screen.getByTestId("hcpcs-title").textContent).toBe("HCPCS Codes");
  });

  it("renders FreshnessChip for hcpcs source", () => {
    wrap(<HcpcsListPage hcpcs_last_run_at="2024-03-01" />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.textContent).toContain("hcpcs");
  });

  it("renders FreshnessChip in red when no run date", () => {
    wrap(<HcpcsListPage hcpcs_last_run_at={null} />);
    expect(document.querySelector(".freshness-chip")?.className).toContain("red");
  });

  it("renders search input", () => {
    wrap(<HcpcsListPage />);
    expect(screen.getByTestId("hcpcs-search-input")).toBeTruthy();
  });

  it("shows search hint when fewer than 2 characters typed", () => {
    wrap(<HcpcsListPage />);
    expect(screen.getByTestId("search-hint")).toBeTruthy();
  });

  it("fetches codes when 2+ chars entered", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { hcpcs_code: "J0001", proprietary_name: "Injection A", therapeutic_class: "Oncology" },
        ],
      }),
    });
    vi.stubGlobal("fetch", mockFetch);
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<HcpcsListPage />);
    await userEvent.type(screen.getByTestId("hcpcs-search-input"), "J0");
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
  });

  it("renders code rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { hcpcs_code: "J0001", proprietary_name: "Injection Adrenalin", therapeutic_class: "Cardiovascular" },
        ],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<HcpcsListPage />);
    await userEvent.type(screen.getByTestId("hcpcs-search-input"), "J0");
    await waitFor(() => {
      expect(screen.getAllByTestId("hcpcs-row").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByTestId("hcpcs-code")[0]?.textContent).toBe("J0001");
  });

  it("calls onNavigate with code query param when row clicked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [{ hcpcs_code: "J0001", proprietary_name: "Injection A" }],
      }),
    }));
    const navigate = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<HcpcsListPage onNavigate={navigate} />);
    await userEvent.type(screen.getByTestId("hcpcs-search-input"), "J0");
    await waitFor(() => expect(screen.getAllByTestId("hcpcs-row").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("hcpcs-row")[0].querySelector("button")!);
    expect(navigate).toHaveBeenCalledWith("/directories/codes/hcpcs?code=J0001");
  });

  it("shows no-results message when search returns empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<HcpcsListPage />);
    await userEvent.type(screen.getByTestId("hcpcs-search-input"), "XX");
    await waitFor(() => {
      expect(screen.queryByTestId("no-results")).toBeTruthy();
    });
  });
});

// ── Icd10ListPage ─────────────────────────────────────────────────────────────

describe("Icd10ListPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders page root with title", () => {
    wrap(<Icd10ListPage />);
    expect(screen.getByTestId("icd10-list-page")).toBeTruthy();
    expect(screen.getByTestId("icd10-title").textContent).toBe("ICD-10-CM Codes");
  });

  it("renders FreshnessChip for icd10_cm source", () => {
    wrap(<Icd10ListPage icd10_last_run_at="2024-03-01" />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.textContent).toContain("icd10_cm");
  });

  it("renders FreshnessChip in red when no run date", () => {
    wrap(<Icd10ListPage icd10_last_run_at={null} />);
    expect(document.querySelector(".freshness-chip")?.className).toContain("red");
  });

  it("renders search input", () => {
    wrap(<Icd10ListPage />);
    expect(screen.getByTestId("icd10-search-input")).toBeTruthy();
  });

  it("shows search hint when fewer than 2 characters", () => {
    wrap(<Icd10ListPage />);
    expect(screen.getByTestId("search-hint")).toBeTruthy();
  });

  it("renders icd10 code rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { icd10_code: "E11.9", description: "Type 2 diabetes mellitus without complications" },
        ],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<Icd10ListPage />);
    await userEvent.type(screen.getByTestId("icd10-search-input"), "E1");
    await waitFor(() => {
      expect(screen.getAllByTestId("icd10-row").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByTestId("icd10-code")[0]?.textContent).toBe("E11.9");
  });

  it("calls onNavigate with code query param when row clicked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [{ icd10_code: "E11.9", description: "Type 2 diabetes" }],
      }),
    }));
    const navigate = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<Icd10ListPage onNavigate={navigate} />);
    await userEvent.type(screen.getByTestId("icd10-search-input"), "E1");
    await waitFor(() => expect(screen.getAllByTestId("icd10-row").length).toBeGreaterThan(0));
    await userEvent.click(screen.getAllByTestId("icd10-row")[0].querySelector("button")!);
    expect(navigate).toHaveBeenCalledWith("/directories/codes/icd10?code=E11.9");
  });
});
