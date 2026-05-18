// tests/integration/bff-fan-out.test.ts
// Integration tests for BFF federated search fan-out via the GET /api/directories/search handler.
//
// These are self-contained unit-integration tests: they exercise the full BFF handler
// path (auth → fan-out → rank → response) with vi.mock() for @infinityrx/auth and
// vi.stubGlobal('fetch', ...) to control backend HTTP responses.
// No docker backends required. MSW is not installed.
//
// The BFF creates a module-level FederatedSearchClient singleton. Tests control
// its behaviour by stubbing global fetch, which FederatedSearchClient uses internally.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
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

// ── Backend response helpers ───────────────────────────────────────────────────
// FederatedSearchClient calls:
//   GET {PRESCRIBER_DIRECTORY_URL}/api/v1/prescribers/search?q=...&limit=5
//   GET {PHARMACY_DIRECTORY_URL}/api/v1/pharmacies/search?q=...&limit=5
//   GET {DRUG_DATABASE_URL}/api/v1/drugs/search?q=...&limit=5
//
// It then maps backend fields to SearchResultRecord shape. We must use the
// exact field names FederatedSearchClient expects.

function prescriberBackendResponse(
  records: Array<{
    npi: string;
    name: string;
    specialty?: string;
    source_date?: string;
    run_id?: string | null;
  }>,
) {
  return { ok: true, status: 200, json: async () => ({ results: records }) };
}

function pharmacyBackendResponse(
  records: Array<{
    nabp: string;
    name: string;
    city?: string;
    source_date?: string;
    run_id?: string | null;
  }>,
) {
  return { ok: true, status: 200, json: async () => ({ results: records }) };
}

function drugBackendResponse(
  records: Array<{
    ndc: string;
    proprietary_name: string;
    nonproprietary_name?: string;
    source_date?: string;
    run_id?: string | null;
  }>,
) {
  return { ok: true, status: 200, json: async () => ({ results: records }) };
}

function timeoutBackendResponse() {
  // Returns a promise that never resolves — FederatedSearchClient's deadline will
  // race it with a 300ms timeout. The test still runs fast because budgetMs=300.
  // For test speed, we return a rejected fetch (simulating network error) which
  // the client catches and treats as "ok: false" (timed out / errored).
  return Promise.reject(new Error("connection refused"));
}

// Fixture backend records
const PRESCRIBER_BACKEND = {
  npi: "8084000008",
  name: "Dr. Jane Smith DO",
  specialty: "Internal Medicine",
  source_date: "2026-05-10",
  run_id: "aaaaaaaa-0001-0001-0001-000000000001",
};

const PHARMACY_BACKEND = {
  nabp: "1234567",
  name: "Sunrise Community Pharmacy",
  city: "Chicago IL",
  source_date: "2026-05-10",
  run_id: null,
};

const DRUG_BACKEND = {
  ndc: "00071015523",
  proprietary_name: "Lipitor",
  nonproprietary_name: "atorvastatin calcium",
  source_date: "2026-05-10",
  run_id: null,
};

const mockFetch = vi.fn();

// Helper: set up fetch mock for all three backends
function setupAllBackendsUp() {
  mockFetch.mockImplementation((url: string) => {
    if (String(url).includes("/prescribers/search")) {
      return Promise.resolve(prescriberBackendResponse([PRESCRIBER_BACKEND]));
    }
    if (String(url).includes("/pharmacies/search")) {
      return Promise.resolve(pharmacyBackendResponse([PHARMACY_BACKEND]));
    }
    if (String(url).includes("/drugs/search")) {
      return Promise.resolve(drugBackendResponse([DRUG_BACKEND]));
    }
    return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
  });
}

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
  mockFetch.mockReset();
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("crypto", { randomUUID: () => "test-correlation-id" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ── Test 1: all backends up → merged results ≤ 20 records ────────────────────

describe("fan-out: all backends up", () => {
  it("returns merged results (≤20) with is_partial=false when all backends respond", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);
    setupAllBackendsUp();

    const res = await GET(makeRequest("atorvastatin"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.is_partial).toBe(false);
    expect(body.timed_out_datasets).toHaveLength(0);
    expect(body.results.length).toBeGreaterThan(0);
    expect(body.results.length).toBeLessThanOrEqual(20);
  });

  it("truncates to 20 results when backends return more", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    // Return 10 prescribers to push total above 20 combined with pharmacy/drug
    const manyPrescribers = Array.from({ length: 10 }, (_, i) => ({
      npi: `808400000${i}`,
      name: `Dr. Fixture ${i}`,
      specialty: "Internal Medicine",
      source_date: "2026-05-10",
      run_id: null,
    }));
    const manyPharmacies = Array.from({ length: 8 }, (_, i) => ({
      nabp: `100000${i}`,
      name: `Pharmacy ${i}`,
      city: "Chicago IL",
      source_date: "2026-05-10",
      run_id: null,
    }));
    const manyDrugs = Array.from({ length: 7 }, (_, i) => ({
      ndc: `0007101552${i}`,
      proprietary_name: `Drug ${i}`,
      nonproprietary_name: "atorvastatin",
      source_date: "2026-05-10",
      run_id: null,
    }));

    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/prescribers/search")) {
        return Promise.resolve(prescriberBackendResponse(manyPrescribers));
      }
      if (String(url).includes("/pharmacies/search")) {
        return Promise.resolve(pharmacyBackendResponse(manyPharmacies));
      }
      if (String(url).includes("/drugs/search")) {
        return Promise.resolve(drugBackendResponse(manyDrugs));
      }
      return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
    });

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

    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/prescribers/search")) {
        return timeoutBackendResponse();
      }
      if (String(url).includes("/pharmacies/search")) {
        return Promise.resolve(pharmacyBackendResponse([PHARMACY_BACKEND]));
      }
      if (String(url).includes("/drugs/search")) {
        return Promise.resolve(drugBackendResponse([DRUG_BACKEND]));
      }
      return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
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
  it("returns empty results with is_partial=true when all backends fail", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    mockFetch.mockImplementation(() => timeoutBackendResponse());

    const res = await GET(makeRequest("any query"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results).toHaveLength(0);
    expect(body.is_partial).toBe(true);
  });
});

// ── Test 4: auth rejection — no JWT → 401 ────────────────────────────────────

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

// ── Test 5: short query → empty results (no fan-out) ─────────────────────────

describe("fan-out: query too short", () => {
  it("returns empty results for single-character query without calling backends", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const res = await GET(makeRequest("a"));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.results).toHaveLength(0);
    expect(body.is_partial).toBe(false);
    // No backend fetch calls should be made for a 1-char query
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ── Test 6: cross-tenant reference data ──────────────────────────────────────

describe("fan-out: cross-tenant reference data isolation", () => {
  it("identical reference data results for tenant A and tenant B", async () => {
    const TID_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    const TID_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

    // Tenant A
    const claimsA = makeClaims(TID_A);
    mockVerify.mockResolvedValue(claimsA as never);
    mockSafeParse.mockReturnValue({ success: true, data: claimsA } as never);
    mockFetch.mockImplementation((url: string) => {
      if (String(url).includes("/drugs/search")) {
        return Promise.resolve(drugBackendResponse([DRUG_BACKEND]));
      }
      return Promise.resolve(prescriberBackendResponse([]));
    });

    const resA = await GET(makeRequest("lipitor"));
    const bodyA = await resA.json();

    mockVerify.mockReset();
    mockSafeParse.mockReset();

    // Tenant B — same backends, same data
    const claimsB = makeClaims(TID_B);
    mockVerify.mockResolvedValue(claimsB as never);
    mockSafeParse.mockReturnValue({ success: true, data: claimsB } as never);

    const resB = await GET(makeRequest("lipitor"));
    const bodyB = await resB.json();

    // Reference data must be identical — no tenant leakage in shared datasets
    expect(bodyA.results).toEqual(bodyB.results);
    expect(bodyA.is_partial).toBe(bodyB.is_partial);
  });
});
