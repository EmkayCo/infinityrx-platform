// tests/unit/bff-quality.test.ts
// BFF quality aggregator + dismiss handler tests (SP-2 Plan D Task D-2).
//
// Coverage targets:
//   - 100% on auth validation (_verifyAuth) — all branches: no-token, bad-claims, throw
//   - 100% on source allowlist check (dismissAlert DISMISSIBLE_SOURCES guard)
//   - 100% on x-tenant-id extraction + pharmacy stats call path (tenant isolation)
//   - 99% overall
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import {
  getQuality,
  dismissAlert,
  QUALITY_SOURCES,
  DISMISSIBLE_SOURCES,
} from "../../src/bff/quality.js";

// ── Mock @infinityrx/auth ────────────────────────────────────────────────────
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
  resolveEnvClaim,
} from "@infinityrx/auth";

const mockVerifyTokenRaw = vi.mocked(verifyTokenRaw);
const mockSafeParse = vi.mocked(AccessClaimsSchema.safeParse);

const VALID_CLAIMS = {
  sub: "00000000-0000-0000-0000-000000000001",
  tid: "00000000-0000-0000-0000-000000000002",
  roles: ["operator"],
  typ: "access",
  iat: Math.floor(Date.now() / 1000),
  exp: Math.floor(Date.now() / 1000) + 3600,
};
const TID = VALID_CLAIMS.tid;
const VALID_TOKEN = "valid-jwt-token";

// ── Fetch mock ───────────────────────────────────────────────────────────────
const mockFetch = vi.fn();

// Sample SourceStatus array returned by ingestion backend.
const SAMPLE_STATUS = [
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
  {
    source: "ncpdp",
    cron_expression: null,
    enabled: true,
    last_run: null,
    last_success_at: null,
    next_run_at: null,
  },
];

function makeRequest(
  url: string,
  opts: { method?: string; token?: string | null } = {},
): NextRequest {
  const { method = "GET", token = VALID_TOKEN } = opts;
  const headers: Record<string, string> = {};
  if (token !== null) headers["authorization"] = `Bearer ${token}`;
  return new NextRequest(url, { method, headers });
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("crypto", {
    randomUUID: () => "cccccccc-cccc-cccc-cccc-cccccccccccc",
  });
  mockVerifyTokenRaw.mockResolvedValue(VALID_CLAIMS as never);
  mockSafeParse.mockReturnValue({ success: true, data: VALID_CLAIMS } as never);

  // Default: all backends respond successfully.
  mockFetch.mockImplementation((url: string) => {
    if (url.includes("/data-ingestion/status")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => SAMPLE_STATUS,
      });
    }
    if (url.includes("/pharmacies/stats")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({
          total_pharmacies: 65000,
          total_active: 60000,
          total_networks: 3,
          pending_credentialing: 12,
        }),
      });
    }
    if (url.includes("/drugs/refresh/status")) {
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => [{ source: "fda_ndc", status: "ok" }],
      });
    }
    return Promise.resolve({ ok: false, status: 500, json: async () => ({}) });
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

// ── Auth gate: getQuality ────────────────────────────────────────────────────

describe("getQuality — auth gate", () => {
  it("returns 401 when no Authorization header", async () => {
    const req = makeRequest("http://localhost/api/directories/quality", {
      token: null,
    });
    const res = await getQuality(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when verifyTokenRaw throws", async () => {
    mockVerifyTokenRaw.mockRejectedValueOnce(new Error("expired"));
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when AccessClaimsSchema.safeParse fails", async () => {
    mockSafeParse.mockReturnValueOnce({ success: false } as never);
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });
});

// ── Full fan-out: all backends respond ───────────────────────────────────────

describe("getQuality — fan-out aggregation", () => {
  it("returns 200 with dataset list when all backends respond", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.datasets).toBeDefined();
    expect(Array.isArray(body.datasets)).toBe(true);
    expect(body.as_of).toBeDefined();
  });

  it("returns 21 dataset rows (one per QUALITY_SOURCES key)", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    expect(body.datasets).toHaveLength(21);
  });

  it("pharmacy stats called with x-tenant-id from JWT claims (not request input)", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    await getQuality(req);
    const pharmacyCalls = mockFetch.mock.calls.filter((c) =>
      String(c[0]).includes("/pharmacies/stats"),
    );
    expect(pharmacyCalls).toHaveLength(1);
    const pharmacyUrl = String(pharmacyCalls[0][0]);
    expect(pharmacyUrl).toContain(`x-tenant-id=${encodeURIComponent(TID)}`);
  });

  it("nppes row has correct source data from SourceStatus", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    const nppes = body.datasets.find((d: { source: string }) => d.source === "nppes");
    expect(nppes).toBeDefined();
    expect(nppes.cluster).toBe("prescribers");
    expect(nppes.last_run_at).toBe("2026-05-15T03:00:00Z");
    expect(nppes.last_run_status).toBe("completed");
    expect(nppes.records_inserted).toBe(7000000);
    expect(nppes.records_errored).toBe(0);
    expect(nppes.is_dismissed).toBe(false);
  });

  it("fdb row has b9_blocked: true and no_loader: true", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    const fdb = body.datasets.find((d: { source: string }) => d.source === "fdb");
    expect(fdb).toBeDefined();
    expect(fdb.b9_blocked).toBe(true);
    expect(fdb.no_loader).toBe(true);
    expect(fdb.cluster).toBe("drugs");
  });

  it("bpg is absent from quality response (no IngestionSchedule row)", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    const bpg = body.datasets.find((d: { source: string }) => d.source === "bpg");
    expect(bpg).toBeUndefined();
  });

  it("relay-health is absent from quality response", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    const relayHealth = body.datasets.find(
      (d: { source: string }) => d.source === "relay-health",
    );
    expect(relayHealth).toBeUndefined();
  });

  it("is_partial: false when all backends respond", async () => {
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    expect(body.is_partial).toBe(false);
  });
});

// ── Partial / degraded backends ──────────────────────────────────────────────

describe("getQuality — partial results when backend is down", () => {
  it("returns is_partial: true when ingestion status backend fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/data-ingestion/status")) {
        return Promise.resolve({ ok: false, status: 503, json: async () => ({}) });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      });
    });
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    // Still returns 200 with partial flag — graceful degradation.
    expect(res.status).toBe(200);
    expect(body.is_partial).toBe(true);
  });

  it("returns is_partial: true when pharmacy backend rejects", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/pharmacies/stats")) {
        return Promise.reject(new Error("network error"));
      }
      if (url.includes("/data-ingestion/status")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => SAMPLE_STATUS,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      });
    });
    const req = makeRequest("http://localhost/api/directories/quality");
    const res = await getQuality(req);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.is_partial).toBe(true);
  });
});

// ── Dismiss: auth gate ────────────────────────────────────────────────────────

describe("dismissAlert — auth gate", () => {
  it("returns 401 when no Authorization header", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/nppes",
      { method: "POST", token: null },
    );
    const res = await dismissAlert(req, "nppes");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when token is invalid", async () => {
    mockVerifyTokenRaw.mockRejectedValueOnce(new Error("invalid"));
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/nppes",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "nppes");
    expect(res.status).toBe(401);
  });
});

// ── Dismiss: source allowlist ─────────────────────────────────────────────────

describe("dismissAlert — source allowlist (SSRF-equivalent guard)", () => {
  it("returns 404 for unknown source", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/unknown_source",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "unknown_source");
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("SOURCE_NOT_FOUND");
  });

  it("returns 404 for bpg (not in DISMISSIBLE_SOURCES)", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/bpg",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "bpg");
    expect(res.status).toBe(404);
  });

  it("returns 404 for relay-health (not in DISMISSIBLE_SOURCES)", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/relay-health",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "relay-health");
    expect(res.status).toBe(404);
  });

  it("returns 204 for valid source nppes", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/nppes",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "nppes");
    expect(res.status).toBe(204);
  });

  it("returns 204 for fdb (b9_blocked source is still dismissible)", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/quality/dismiss/fdb",
      { method: "POST" },
    );
    const res = await dismissAlert(req, "fdb");
    expect(res.status).toBe(204);
  });
});

// ── Dismiss + subsequent GET reflects is_dismissed: true ─────────────────────

describe("dismissAlert → getQuality integration", () => {
  it("dismissed source shows is_dismissed: true in subsequent GET", async () => {
    // Dismiss nppes.
    const dismissReq = makeRequest(
      "http://localhost/api/directories/quality/dismiss/nppes",
      { method: "POST" },
    );
    const dismissRes = await dismissAlert(dismissReq, "nppes");
    expect(dismissRes.status).toBe(204);

    // Subsequent GET should show nppes as dismissed.
    const getReq = makeRequest("http://localhost/api/directories/quality");
    const getRes = await getQuality(getReq);
    const body = await getRes.json();
    const nppes = body.datasets.find((d: { source: string }) => d.source === "nppes");
    expect(nppes.is_dismissed).toBe(true);
  });
});

// ── QUALITY_SOURCES and DISMISSIBLE_SOURCES exports ──────────────────────────

describe("QUALITY_SOURCES set", () => {
  it("has 21 entries", () => {
    expect(QUALITY_SOURCES.size).toBe(21);
  });

  it("includes fdb", () => {
    expect(QUALITY_SOURCES.has("fdb")).toBe(true);
  });

  it("excludes bpg", () => {
    expect(QUALITY_SOURCES.has("bpg")).toBe(false);
  });

  it("excludes relay-health", () => {
    expect(QUALITY_SOURCES.has("relay-health")).toBe(false);
  });
});

describe("DISMISSIBLE_SOURCES set", () => {
  it("fdb is dismissible (b9_blocked alerts are still operator-actionable)", () => {
    expect(DISMISSIBLE_SOURCES.has("fdb")).toBe(true);
  });

  it("bpg is NOT dismissible", () => {
    expect(DISMISSIBLE_SOURCES.has("bpg")).toBe(false);
  });
});
