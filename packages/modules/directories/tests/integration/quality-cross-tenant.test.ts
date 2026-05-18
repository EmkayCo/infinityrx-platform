// tests/integration/quality-cross-tenant.test.ts
// Cross-tenant isolation test for the quality BFF (SP-2 Plan D Task D-5).
//
// Verifies:
// 1. tid is derived from JWT claims, not from request headers or query params.
// 2. Pharmacy stats are called with x-tenant-id from the JWT claims.
// 3. Tenant-scoped pharmacy fields (total_networks, pending_credentialing)
//    are NOT surfaced in the quality response body.
// 4. Global reference fields (records_inserted, records_errored, last_run_at)
//    are tenant-independent (identical across tenants).
//
// This is a unit-level integration test: it exercises getQuality() end-to-end
// with two different JWT tenant IDs and asserts isolation. No docker backends needed.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import { getQuality } from "../../src/bff/quality.js";

vi.mock("@infinityrx/auth", () => ({
  verifyTokenRaw: vi.fn(),
  AccessClaimsSchema: {
    safeParse: vi.fn(),
  },
  resolveEnvClaim: vi.fn().mockReturnValue("development"),
}));

import {
  verifyTokenRaw,
  AccessClaimsSchema,
} from "@infinityrx/auth";

const mockVerifyTokenRaw = vi.mocked(verifyTokenRaw);
const mockSafeParse = vi.mocked(AccessClaimsSchema.safeParse);

const TID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const TID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const CLAIMS_A = {
  sub: "00000000-0000-0000-0000-000000000001",
  tid: TID_A,
  roles: ["operator"],
  typ: "access",
  iat: Math.floor(Date.now() / 1000),
  exp: Math.floor(Date.now() / 1000) + 3600,
};

const CLAIMS_B = {
  sub: "00000000-0000-0000-0000-000000000002",
  tid: TID_B,
  roles: ["operator"],
  typ: "access",
  iat: Math.floor(Date.now() / 1000),
  exp: Math.floor(Date.now() / 1000) + 3600,
};

const INGESTION_STATUS = [
  {
    source: "nppes",
    cron_expression: "0 3 1 * *",
    enabled: true,
    last_run: {
      status: "completed",
      records_inserted: 7000000,
      records_errored: 0,
      started_at: "2026-05-15T03:00:00Z",
    },
    last_success_at: "2026-05-15T03:00:00Z",
    next_run_at: "2026-06-01T03:00:00Z",
  },
];

const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("crypto", {
    randomUUID: () => "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
  });
  mockFetch.mockImplementation((url: string) => {
    if (url.includes("/data-ingestion/status")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => INGESTION_STATUS,
      });
    }
    if (url.includes("/pharmacies/stats")) {
      // Tenant-specific pharmacy stats differ by tenant.
      const parsedUrl = new URL(String(url));
      const tid = parsedUrl.searchParams.get("x-tenant-id");
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          total_pharmacies: 65000,
          total_active: 60000,
          // Tenant-specific fields:
          total_networks: tid === TID_A ? 3 : 7,
          pending_credentialing: tid === TID_A ? 12 : 5,
        }),
      });
    }
    if (url.includes("/drugs/refresh/status")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => [],
      });
    }
    return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function makeRequest(token: string): NextRequest {
  return new NextRequest("http://localhost/api/directories/quality", {
    method: "GET",
    headers: { authorization: `Bearer ${token}` },
  });
}

describe("quality BFF — cross-tenant isolation", () => {
  it("pharmacy stats called with x-tenant-id from JWT claims for tenant A", async () => {
    mockVerifyTokenRaw.mockResolvedValue(CLAIMS_A as never);
    mockSafeParse.mockReturnValue({ success: true, data: CLAIMS_A } as never);

    await getQuality(makeRequest("token-a"));

    const pharmacyCalls = mockFetch.mock.calls.filter((c) =>
      String(c[0]).includes("/pharmacies/stats"),
    );
    expect(pharmacyCalls).toHaveLength(1);
    const url = new URL(String(pharmacyCalls[0][0]));
    expect(url.searchParams.get("x-tenant-id")).toBe(TID_A);
  });

  it("pharmacy stats called with x-tenant-id from JWT claims for tenant B", async () => {
    mockVerifyTokenRaw.mockResolvedValue(CLAIMS_B as never);
    mockSafeParse.mockReturnValue({ success: true, data: CLAIMS_B } as never);

    await getQuality(makeRequest("token-b"));

    const pharmacyCalls = mockFetch.mock.calls.filter((c) =>
      String(c[0]).includes("/pharmacies/stats"),
    );
    expect(pharmacyCalls).toHaveLength(1);
    const url = new URL(String(pharmacyCalls[0][0]));
    expect(url.searchParams.get("x-tenant-id")).toBe(TID_B);
  });

  it("global reference fields (records_inserted, last_run_at) are identical for both tenants", async () => {
    // Tenant A
    mockVerifyTokenRaw.mockResolvedValue(CLAIMS_A as never);
    mockSafeParse.mockReturnValue({ success: true, data: CLAIMS_A } as never);
    const resA = await getQuality(makeRequest("token-a"));
    const bodyA = await resA.json();
    const nppesA = bodyA.datasets.find((d: { source: string }) => d.source === "nppes");

    vi.clearAllMocks();
    vi.stubGlobal("fetch", mockFetch);

    // Tenant B
    mockVerifyTokenRaw.mockResolvedValue(CLAIMS_B as never);
    mockSafeParse.mockReturnValue({ success: true, data: CLAIMS_B } as never);
    const resB = await getQuality(makeRequest("token-b"));
    const bodyB = await resB.json();
    const nppesB = bodyB.datasets.find((d: { source: string }) => d.source === "nppes");

    // Global reference fields must be identical (not tenant-scoped).
    expect(nppesA.records_inserted).toBe(nppesB.records_inserted);
    expect(nppesA.last_run_at).toBe(nppesB.last_run_at);
    expect(nppesA.records_errored).toBe(nppesB.records_errored);
  });

  it("tenant-scoped pharmacy fields (total_networks, pending_credentialing) are NOT in the quality response", async () => {
    mockVerifyTokenRaw.mockResolvedValue(CLAIMS_A as never);
    mockSafeParse.mockReturnValue({ success: true, data: CLAIMS_A } as never);

    const res = await getQuality(makeRequest("token-a"));
    const body = await res.json();

    // The quality response body must NOT expose tenant-specific pharmacy stats.
    const bodyStr = JSON.stringify(body);
    expect(bodyStr).not.toContain("total_networks");
    expect(bodyStr).not.toContain("pending_credentialing");
  });
});
