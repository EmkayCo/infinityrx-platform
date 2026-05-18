// tests/unit/surfaces/pricing.test.tsx
// Task B-5: Pricing cluster — PricingPage render and interaction tests.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { PricingPage } from "../../../src/surfaces/pricing/PricingPage.js";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}
function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>);
}

describe("PricingPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ records: [] }),
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders page root and title", () => {
    wrap(<PricingPage />);
    expect(screen.getByTestId("pricing-page")).toBeTruthy();
    expect(screen.getByTestId("pricing-title").textContent).toBe("Pricing Reference");
  });

  it("renders tab bar with all 4 tabs", () => {
    wrap(<PricingPage />);
    expect(screen.getByTestId("tab-cms_asp")).toBeTruthy();
    expect(screen.getByTestId("tab-cms_nadac")).toBeTruthy();
    expect(screen.getByTestId("tab-medicaid_bins")).toBeTruthy();
    expect(screen.getByTestId("tab-bpg")).toBeTruthy();
  });

  it("defaults to CMS-ASP tab", () => {
    wrap(<PricingPage />);
    const aspTab = screen.getByTestId("tab-cms_asp");
    expect(aspTab.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByTestId("cms-asp-tab")).toBeTruthy();
  });

  it("renders NDC input on CMS-ASP tab", () => {
    wrap(<PricingPage />);
    expect(screen.getByTestId("ndc-input-wrapper")).toBeTruthy();
    expect(screen.getByTestId("ndc-input")).toBeTruthy();
  });

  it("shows hint text when NDC is empty on CMS-ASP tab", () => {
    wrap(<PricingPage />);
    expect(screen.getByTestId("asp-hint")).toBeTruthy();
  });

  it("renders FreshnessChip for cms_asp source", () => {
    wrap(<PricingPage cms_asp_last_run_at="2024-03-01" />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.textContent).toContain("cms_asp");
  });

  it("renders FreshnessChip in red when no cms_asp run date", () => {
    wrap(<PricingPage cms_asp_last_run_at={null} />);
    expect(document.querySelector(".freshness-chip")?.className).toContain("red");
  });

  it("shows NDC invalid hint for partial input", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.type(screen.getByTestId("ndc-input"), "123");
    expect(screen.getByTestId("ndc-invalid-hint")).toBeTruthy();
  });

  it("fetches CMS-ASP pricing when valid 11-digit NDC entered", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        records: [{ ndc: "12345678901", effective_date: "2024-01-01", price: "$10.00", source: "cms_asp" }],
      }),
    });
    vi.stubGlobal("fetch", mockFetch);
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.type(screen.getByTestId("ndc-input"), "12345678901");
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [calledUrl] = mockFetch.mock.calls[0] as [string];
    expect(calledUrl).toContain("/api/v1/drugs/pricing/12345678901");
    expect(calledUrl).not.toContain("/history");
  });

  it("renders CMS-ASP pricing rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        records: [{ ndc: "12345678901", effective_date: "2024-01-01", price: "$10.00", source: "cms_asp" }],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.type(screen.getByTestId("ndc-input"), "12345678901");
    await waitFor(() => {
      expect(screen.getAllByTestId("asp-pricing-row").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByTestId("asp-date")[0]?.textContent).toBe("2024-01-01");
    expect(screen.getAllByTestId("asp-price")[0]?.textContent).toBe("$10.00");
  });

  it("shows empty message when CMS-ASP returns no records for valid NDC", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ records: [] }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.type(screen.getByTestId("ndc-input"), "12345678901");
    await waitFor(() => {
      expect(screen.getByTestId("asp-empty")).toBeTruthy();
    });
  });

  it("switches to CMS-NADAC tab and shows NADAC content", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-cms_nadac"));
    expect(screen.getByTestId("cms-nadac-tab")).toBeTruthy();
    expect(screen.getByTestId("tab-cms_nadac").getAttribute("aria-selected")).toBe("true");
  });

  it("shows NDC input on CMS-NADAC tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-cms_nadac"));
    expect(screen.getByTestId("ndc-input-wrapper")).toBeTruthy();
    expect(screen.getByTestId("nadac-hint")).toBeTruthy();
  });

  it("fetches CMS-NADAC history when valid NDC entered on NADAC tab", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        records: [{ ndc: "12345678901", effective_date: "2024-02-01", price: "$9.50", source: "cms_nadac" }],
      }),
    });
    vi.stubGlobal("fetch", mockFetch);
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-cms_nadac"));
    await userEvent.type(screen.getByTestId("ndc-input"), "12345678901");
    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [calledUrl] = mockFetch.mock.calls[0] as [string];
    expect(calledUrl).toContain("/api/v1/drugs/pricing/12345678901/history");
  });

  it("renders CMS-NADAC pricing rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        records: [{ ndc: "12345678901", effective_date: "2024-02-01", price: "$9.50", source: "cms_nadac" }],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-cms_nadac"));
    await userEvent.type(screen.getByTestId("ndc-input"), "12345678901");
    await waitFor(() => {
      expect(screen.getAllByTestId("nadac-pricing-row").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByTestId("nadac-date")[0]?.textContent).toBe("2024-02-01");
    expect(screen.getAllByTestId("nadac-price")[0]?.textContent).toBe("$9.50");
  });

  it("switches to Medicaid BINs tab and shows static reference card", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-medicaid_bins"));
    expect(screen.getByTestId("medicaid-bins-tab")).toBeTruthy();
    expect(screen.getByTestId("medicaid-bins-card")).toBeTruthy();
    expect(screen.getByTestId("medicaid-bins-title").textContent).toBe("State Medicaid BINs");
    expect(screen.getByTestId("medicaid-bins-count").textContent).toContain("219");
  });

  it("hides NDC input on Medicaid BINs tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-medicaid_bins"));
    expect(screen.queryByTestId("ndc-input-wrapper")).toBeNull();
  });

  it("switches to BPG tab and shows live API reference card", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-bpg"));
    expect(screen.getByTestId("bpg-tab")).toBeTruthy();
    expect(screen.getByTestId("bpg-card")).toBeTruthy();
    expect(screen.getByTestId("bpg-title").textContent).toBe("BPG PatientLens");
    expect(screen.getByTestId("bpg-live-api-label").textContent).toBe("Live API — no ingestion schedule");
  });

  it("renders BPG doc link on BPG tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-bpg"));
    const link = screen.getByTestId("bpg-doc-link");
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toContain("BPG_Translator_API_Documentation");
  });

  it("hides NDC input on BPG tab", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PricingPage />);
    await userEvent.click(screen.getByTestId("tab-bpg"));
    expect(screen.queryByTestId("ndc-input-wrapper")).toBeNull();
  });
});
