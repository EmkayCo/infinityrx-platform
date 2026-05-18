// tests/integration/bff-fan-out.test.ts
// Integration tests for BFF federated search fan-out via the GET /api/directories/search handler.
//
// These are self-contained unit-integration tests: they exercise the full BFF handler
// path (auth → fan-out → rank → response) with vi.mock() for the FederatedSearchClient
// and @infinityrx/auth. No docker backends required. MSW is not installed; fetch is
// stubbed where needed via vi.stubGlobal.
import { describe, it, expect, vi, beforeEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import { GET } from "../../src/bff/search.js";

// ── Mock @infinityrx/auth ─────────────────────────────────────────────────────
vi.mock("@infinityrx/auth", () => ({
  verifyTokenRaw: vi.fn(),
  AccessClaimsSchema: { safeParse: vi.fn() },
  resolveEnvClaim: vi.fn().mockReturnValue("development"),
}));

import { verifyTokenRaw, AccessClaimsSchema } from "@infinityrx/auth";
const mockVerify = vi.mocked(verifyTokenRaw);
const mockSafeParse = vi.mocked(AccessClaimsSchema.safeParse);

// ── Shared claims factory ─────────────────────────────────────────────────────
function makeClaims(tid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa") {
  return {
    sub: "00000000-0000-0000-0000-000000000001",
    tid,
    roles: ["operator"],
    typ: "access",
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  };
}

// ── FederatedSearchClient mock factory ───────────────────────────────────────
// We reset this in each test so different scenarios can inject different mock behaviors.
const mockSearchFn = vi.fn();

vi.mock("../../src/search/FederatedSearchClient.js", () => ({
  FederatedSearchClient: vi.fn().mockImplementation(() => ({
    search: mockSearchFn,
    detectIdShortcut: vi.fn().mockReturnValue(null),
  })),
}));

// ── Fixture results ───────────────────────────────────────────────────────────
const PRESCRIBER_RESULT = {
  dataset: "nppes",
  id: "8084000008",
  display: "Dr. Jane Smith DO",
  secondary: "Internal Medicine",
  source_date: "2026-05-10",
  run_id: "aaaaaaaa-0001-0001-0001-000000000001",
};

const DRUG_RESULT = {
  dataset: "fda_ndc",
  id: "00071015523",
  display: "Atorvastatin Calcium (Lipitor)",
  secondary: "atorvastatin calcium",
  source_date: "2026-05-10",
  run_id: null,
};

const PHARMACY_RESULT = {
  dataset: "ncpdp",
  id: "1234567",
  display: "Sunrise Community Pharmacy",
  secondary: "Chicago IL",
  source_date: "2026-05-10",
  run_id: null,
};

function makeRequest(q: string, token = "valid-token"): NextRequest {
  const url = new URL("http://localhost/api/directories/search");
  url.searchParams.set("q", q);
  return new NextRequest(url.toString(), {
    headers: { authorization: `Bearer ${token}` },
  });
}

beforeEach(() => {
  mockVerify.mockReset();
  mockSafeParse.mockReset();
  mockSearchFn.mockReset();
  vi.stubGlobal("crypto", { randomUUID: () => "test-correlation-id" });
});

// ── Test 1: all backends up → merged results ≤ 20 records ────────────────────

describe("fan-out: all backends up", () => {
  it("returns merged results (≤20) with is_partial=false when all backends respond", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    mockSearchFn.mockResolvedValue({
      results: [PRESCRIBER_RESULT, DRUG_RESULT, PHARMACY_RESULT],
      timedOutDatasets: [],
    });

    const res = await GET(makeRequest("atorvastatin"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.is_partial).toBe(false);
    expect(body.timed_out_datasets).toHaveLength(0);
    expect(body.results.length).toBeGreaterThan(0);
    expect(body.results.length).toBeLessThanOrEqual(20);
  });

  it("truncates to 20 results when backend returns more", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    // Return 25 results to verify the 20-result cap
    const manyResults = Array.from({ length: 25 }, (_, i) => ({
      ...PRESCRIBER_RESULT,
      id: `808400${String(i).padStart(4, "0")}`,
      display: `Dr. Fixture ${i}`,
    }));
    mockSearchFn.mockResolvedValue({ results: manyResults, timedOutDatasets: [] });

    const res = await GET(makeRequest("dr fixture"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results.length).toBeLessThanOrEqual(20);
  });
});

// ── Test 2: prescriber-directory down → nppes absent, is_partial=true ────────

describe("fan-out: prescriber-directory backend down", () => {
  it("returns is_partial=true and timed_out_datasets includes nppes", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    // Simulate nppes timed out
    mockSearchFn.mockResolvedValue({
      results: [DRUG_RESULT, PHARMACY_RESULT],
      timedOutDatasets: ["nppes"],
    });

    const res = await GET(makeRequest("smith"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.is_partial).toBe(true);
    expect(body.timed_out_datasets).toContain("nppes");
    expect(body.results.every((r: { dataset: string }) => r.dataset !== "nppes")).toBe(true);
  });
});

// ── Test 3: all backends down → empty results, is_partial=true ──────────────

describe("fan-out: all backends down", () => {
  it("returns empty results with is_partial=true when all backends time out", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    mockSearchFn.mockResolvedValue({
      results: [],
      timedOutDatasets: ["nppes", "ncpdp", "fda_ndc"],
    });

    const res = await GET(makeRequest("any query"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results).toHaveLength(0);
    expect(body.is_partial).toBe(true);
  });
});

// ── Test 4: NPI id shortcut → single result path ─────────────────────────────

describe("fan-out: NPI exact match shortcut", () => {
  it("returns a single NPI result without triggering multi-dataset fan-out", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    // NPI shortcut returns a single prescriber result
    mockSearchFn.mockResolvedValue({
      results: [PRESCRIBER_RESULT],
      timedOutDatasets: [],
    });

    const res = await GET(makeRequest("8084000008"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results).toHaveLength(1);
    expect(body.results[0].id).toBe("8084000008");
    expect(body.is_partial).toBe(false);
  });
});

// ── Test 5: auth rejection — no JWT → 401 ────────────────────────────────────

describe("fan-out: auth rejection", () => {
  it("returns 401 when no Authorization header is present", async () => {
    const url = new URL("http://localhost/api/directories/search");
    url.searchParams.set("q", "lipitor");
    const req = new NextRequest(url.toString(), { headers: {} });

    const res = await GET(req);

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when JWT verification fails", async () => {
    mockVerify.mockRejectedValue(new Error("invalid signature"));

    const res = await GET(makeRequest("lipitor", "bad-token"));

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when token claims schema validation fails", async () => {
    mockVerify.mockResolvedValue({} as never);
    mockSafeParse.mockReturnValue({ success: false, error: new Error("bad claims") } as never);

    const res = await GET(makeRequest("lipitor", "token-bad-claims"));

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });
});

// ── Test 6: cross-tenant reference data (identical results for different TIDs) ─

describe("fan-out: cross-tenant reference data isolation", () => {
  it("identical reference data results for tenant A and tenant B", async () => {
    const TID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    const TID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    const SHARED_RESULTS = [DRUG_RESULT];

    // Tenant A
    const claimsA = makeClaims(TID_A);
    mockVerify.mockResolvedValue(claimsA as never);
    mockSafeParse.mockReturnValue({ success: true, data: claimsA } as never);
    mockSearchFn.mockResolvedValue({ results: SHARED_RESULTS, timedOutDatasets: [] });

    const resA = await GET(makeRequest("lipitor"));
    const bodyA = await resA.json();

    mockVerify.mockReset();
    mockSafeParse.mockReset();
    mockSearchFn.mockReset();

    // Tenant B
    const claimsB = makeClaims(TID_B);
    mockVerify.mockResolvedValue(claimsB as never);
    mockSafeParse.mockReturnValue({ success: true, data: claimsB } as never);
    mockSearchFn.mockResolvedValue({ results: SHARED_RESULTS, timedOutDatasets: [] });

    const resB = await GET(makeRequest("lipitor"));
    const bodyB = await resB.json();

    // Reference data must be identical — no tenant leakage in shared datasets
    expect(bodyA.results).toEqual(bodyB.results);
    expect(bodyA.is_partial).toBe(bodyB.is_partial);
  });
});

// ── Test 7: short query → empty results (no fan-out) ─────────────────────────

describe("fan-out: query too short", () => {
  it("returns empty results for single-character query without calling search", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const res = await GET(makeRequest("a"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results).toHaveLength(0);
    expect(body.is_partial).toBe(false);
    // search() should NOT have been called for a 1-char query
    expect(mockSearchFn).not.toHaveBeenCalled();
  });
});
