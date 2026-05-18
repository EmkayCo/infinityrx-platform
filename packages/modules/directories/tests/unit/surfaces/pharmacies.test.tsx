// tests/unit/surfaces/pharmacies.test.tsx
// Task B-2: Pharmacies cluster — PharmaciesListPage, PharmacyDetailPage.
// Also covers BFF pharmacies.ts auth paths (100% coverage requirement).
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, cleanup } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NextRequest } from "../../../src/__mocks__/next-server.js";

import { PharmaciesListPage } from "../../../src/surfaces/pharmacies/PharmaciesListPage.js";
import { PharmacyDetailPage } from "../../../src/surfaces/pharmacies/PharmacyDetailPage.js";
import { GET as pharmaciesStatsGET } from "../../../src/bff/pharmacies.js";

// ── Mock @infinityrx/auth for BFF tests ──────────────────────────────────────
vi.mock("@infinityrx/auth", () => ({
  verifyTokenRaw: vi.fn(),
  AccessClaimsSchema: { safeParse: vi.fn() },
  resolveEnvClaim: vi.fn().mockReturnValue("development"),
}));

import { verifyTokenRaw, AccessClaimsSchema } from "@infinityrx/auth";

function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}
function wrap(ui: React.ReactElement) {
  return render(<QueryClientProvider client={makeClient()}>{ui}</QueryClientProvider>);
}

// ── PharmaciesListPage ────────────────────────────────────────────────────────

describe("PharmaciesListPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [] }),
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders page root", () => {
    wrap(<PharmaciesListPage />);
    expect(screen.getByTestId("pharmacies-list-page")).toBeTruthy();
  });

  it("renders FreshnessChip for ncpdp source", () => {
    wrap(<PharmaciesListPage ncpdp_last_run_at="2024-03-01" />);
    expect(document.querySelector(".freshness-chip")).toBeTruthy();
  });

  it("renders FreshnessChip in red when no run date provided", () => {
    wrap(<PharmaciesListPage ncpdp_last_run_at={null} />);
    const chip = document.querySelector(".freshness-chip");
    expect(chip).toBeTruthy();
    expect(chip?.className).toContain("red");
  });

  it("renders search input", () => {
    wrap(<PharmaciesListPage />);
    expect(screen.getByTestId("pharmacies-search-input")).toBeTruthy();
  });

  it("renders pharmacy rows when results returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: [
          { npi: "1234509876", name: "Test Pharmacy", city: "Chicago", state: "IL" },
        ],
      }),
    }));
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PharmaciesListPage />);
    await userEvent.type(screen.getByTestId("pharmacies-search-input"), "Test");
    await waitFor(() => {
      expect(screen.getAllByTestId("pharmacy-row").length).toBeGreaterThan(0);
    });
  });

  it("calls onNavigate when pharmacy row clicked", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [{ npi: "9876543210", name: "CVS Pharmacy" }] }),
    }));
    const navigate = vi.fn();
    const { default: userEvent } = await import("@testing-library/user-event");
    wrap(<PharmaciesListPage onNavigate={navigate} />);
    await userEvent.type(screen.getByTestId("pharmacies-search-input"), "CV");
    await waitFor(() => {
      expect(screen.getAllByTestId("pharmacy-row").length).toBeGreaterThan(0);
    });
    const row = screen.getAllByTestId("pharmacy-row")[0];
    const btn = row.querySelector("button")!;
    await userEvent.click(btn);
    expect(navigate).toHaveBeenCalledWith("/directories/pharmacies/9876543210");
  });
});

// ── PharmacyDetailPage ────────────────────────────────────────────────────────

describe("PharmacyDetailPage", () => {
  const mockPharmacy = {
    npi: "1234567890",
    name: "MedPlus Pharmacy",
    city: "Chicago",
    state: "IL",
    network_status: "in_network",
    source_date: "2024-03-10",
    run_id: "run-xyz-456",
  };

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("relationships")) {
        return Promise.resolve({ ok: true, json: async () => ({ prescribers: [] }) });
      }
      return Promise.resolve({ ok: true, json: async () => mockPharmacy });
    }));
  });
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("renders pharmacy name after loading", async () => {
    wrap(<PharmacyDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("pharmacy-name")?.textContent).toBe("MedPlus Pharmacy");
    });
  });

  it("renders ProvenanceBadge with source key ncpdp", async () => {
    wrap(<PharmacyDetailPage npi="1234567890" />);
    await waitFor(() => expect(screen.queryByTestId("pharmacy-detail-page")).toBeTruthy());
    expect(document.querySelector(".provenance-badge__source")?.textContent).toContain("ncpdp");
  });

  it("renders FreshnessChip for ncpdp source", async () => {
    wrap(<PharmacyDetailPage npi="1234567890" ncpdp_last_run_at="2024-03-10" />);
    await waitFor(() => expect(screen.queryByTestId("pharmacy-detail-page")).toBeTruthy());
    expect(document.querySelector(".freshness-chip")).toBeTruthy();
  });

  it("shows prescriber relationships when returned", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url.includes("relationships")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            prescribers: [{ npi: "0987654321", display_name: "Dr. Smith", claim_count: 42 }],
          }),
        });
      }
      return Promise.resolve({ ok: true, json: async () => mockPharmacy });
    }));
    wrap(<PharmacyDetailPage npi="1234567890" />);
    await waitFor(() => {
      expect(screen.queryByTestId("prescriber-relationships")).toBeTruthy();
    });
    expect(screen.getAllByTestId("relationship-row").length).toBeGreaterThan(0);
  });
});

// ── BFF pharmacies stats — auth paths (100% coverage) ────────────────────────

describe("BFF GET /api/directories/pharmacies/stats — auth paths", () => {
  beforeEach(() => {
    vi.mocked(verifyTokenRaw).mockReset();
    vi.mocked(AccessClaimsSchema.safeParse).mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => { vi.restoreAllMocks(); });

  it("returns 401 when no Authorization header", async () => {
    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats");
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(401);
    const body = await res.json() as { error: { code: string } };
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when token is invalid", async () => {
    vi.mocked(verifyTokenRaw).mockRejectedValue(new Error("bad token"));
    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer bad-token" },
    });
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(401);
  });

  it("returns 401 when claims fail schema validation", async () => {
    vi.mocked(verifyTokenRaw).mockResolvedValue({ sub: "not-a-claims" });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({ success: false, error: {} } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer some-token" },
    });
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(401);
  });

  it("passes x-tenant-id from JWT tid claim to backend (tenant isolation)", async () => {
    const tenantId = "11111111-1111-1111-1111-111111111111";
    vi.mocked(verifyTokenRaw).mockResolvedValue({ tid: tenantId });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({
      success: true,
      data: { tid: tenantId },
    } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ total_pharmacies: 1500, total_networks: 3 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer valid-token" },
    });
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(200);
    // Backend must be called with x-tenant-id query param
    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).toContain(`x-tenant-id=${tenantId}`);
  });

  it("cross-tenant isolation: different tid produces different backend URL param", async () => {
    const tenantA = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    const tenantB = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ total_pharmacies: 1500 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    // Call with tenant A
    vi.mocked(verifyTokenRaw).mockResolvedValue({ tid: tenantA });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({
      success: true,
      data: { tid: tenantA },
    } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    const reqA = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer token-a" },
    });
    await pharmaciesStatsGET(reqA);
    const urlA = mockFetch.mock.calls[0][0] as string;

    // Call with tenant B
    vi.mocked(verifyTokenRaw).mockResolvedValue({ tid: tenantB });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({
      success: true,
      data: { tid: tenantB },
    } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    const reqB = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer token-b" },
    });
    await pharmaciesStatsGET(reqB);
    const urlB = mockFetch.mock.calls[1][0] as string;

    // Both URLs must differ by tenant id
    expect(urlA).toContain(tenantA);
    expect(urlB).toContain(tenantB);
    expect(urlA).not.toBe(urlB);
  });

  it("returns 502 when backend fetch throws", async () => {
    const tenantId = "22222222-2222-2222-2222-222222222222";
    vi.mocked(verifyTokenRaw).mockResolvedValue({ tid: tenantId });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({
      success: true,
      data: { tid: tenantId },
    } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));

    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer valid-token" },
    });
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(502);
  });

  it("propagates upstream error status from backend", async () => {
    const tenantId = "33333333-3333-3333-3333-333333333333";
    vi.mocked(verifyTokenRaw).mockResolvedValue({ tid: tenantId });
    vi.mocked(AccessClaimsSchema.safeParse).mockReturnValue({
      success: true,
      data: { tid: tenantId },
    } as ReturnType<typeof AccessClaimsSchema.safeParse>);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ detail: "missing x-tenant-id" }),
    }));

    const req = new NextRequest("http://localhost/api/directories/pharmacies/stats", {
      headers: { Authorization: "Bearer valid-token" },
    });
    const res = await pharmaciesStatsGET(req);
    expect(res.status).toBe(422);
  });
});
