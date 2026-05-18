// tests/unit/bff-ingest.test.ts
// BFF ingestion proxy route handler tests (SP-2 Plan C Task C-2).
//
// Coverage targets:
//   - 100% on auth validation (_verifyAuth) — all branches: no-token, bad-claims, throw
//   - 100% on SSRF guard (_guardSource) — source in set, source not in set
//   - 99% overall
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import {
  triggerRun,
  getHistory,
  getRunDetail,
  cancelRun,
  getAllStatus,
  TRIGGERABLE_SOURCES,
} from "../../src/bff/ingest.js";

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

const VALID_TOKEN = "valid-jwt-token";
const AUTH_HEADER = `Bearer ${VALID_TOKEN}`;

// ── Fetch mock ───────────────────────────────────────────────────────────────
const mockFetch = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("crypto", {
    randomUUID: () => "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  });
  mockVerifyTokenRaw.mockResolvedValue(VALID_CLAIMS as never);
  mockSafeParse.mockReturnValue({ success: true, data: VALID_CLAIMS } as never);
  mockFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ run_id: "run-1", source: "fda_ndc", status: "running", message: "ok" }),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function makeRequest(
  url: string,
  opts: { method?: string; token?: string | null; body?: unknown } = {},
): NextRequest {
  const { method = "GET", token = VALID_TOKEN, body } = opts;
  const headers: Record<string, string> = {};
  if (token !== null) headers["authorization"] = `Bearer ${token}`;
  return new NextRequest(url, {
    method,
    headers,
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}

// ── TRIGGERABLE_SOURCES shape ────────────────────────────────────────────────

describe("TRIGGERABLE_SOURCES", () => {
  it("contains 20 keys (18 DatasetKey + nppes_monthly + nppes_deactivation)", () => {
    expect(TRIGGERABLE_SOURCES.size).toBe(20);
  });

  it("excludes bpg, fdb, relay-health", () => {
    expect(TRIGGERABLE_SOURCES.has("bpg")).toBe(false);
    expect(TRIGGERABLE_SOURCES.has("fdb")).toBe(false);
    expect(TRIGGERABLE_SOURCES.has("relay-health")).toBe(false);
  });

  it("includes nppes_monthly and nppes_deactivation", () => {
    expect(TRIGGERABLE_SOURCES.has("nppes_monthly")).toBe(true);
    expect(TRIGGERABLE_SOURCES.has("nppes_deactivation")).toBe(true);
  });
});

// ── triggerRun ───────────────────────────────────────────────────────────────

describe("triggerRun", () => {
  it("returns 401 when no Authorization header", async () => {
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", {
      method: "POST",
      token: null,
    });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when verifyTokenRaw throws", async () => {
    mockVerifyTokenRaw.mockRejectedValueOnce(new Error("bad sig"));
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", { method: "POST" });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
    expect(body.error.message).toBe("Invalid token");
  });

  it("returns 401 when AccessClaimsSchema.safeParse fails", async () => {
    mockSafeParse.mockReturnValueOnce({ success: false } as never);
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", { method: "POST" });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
    expect(body.error.message).toBe("Invalid token claims");
  });

  it("returns 404 for source not in TRIGGERABLE_SOURCES (SSRF guard)", async () => {
    const req = makeRequest("http://bff/ingest/bpg/trigger", { method: "POST" });
    const res = await triggerRun(req, "bpg");
    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error.code).toBe("SOURCE_NOT_FOUND");
    // Verify fetch was NOT called (SSRF blocked)
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 404 for arbitrary injected source string (SSRF guard)", async () => {
    const req = makeRequest("http://bff/ingest/../../etc/passwd/trigger", { method: "POST" });
    const res = await triggerRun(req, "../../etc/passwd");
    expect(res.status).toBe(404);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies POST to backend and returns 200 for valid source", async () => {
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", {
      method: "POST",
      body: { run_type: "manual_trigger" },
    });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/data-ingestion/fda_ndc/trigger"),
      expect.objectContaining({ method: "POST" }),
    );
    const body = await res.json();
    expect(body.source).toBe("fda_ndc");
  });

  it("passes 409 through from backend (duplicate in-flight)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({
        detail: { error: { code: "RUN_ALREADY_IN_FLIGHT", message: "already running", correlation_id: "x" } },
      }),
    });
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", { method: "POST" });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.status).toBe(409);
  });

  it("sets x-correlation-id on response", async () => {
    const req = makeRequest("http://bff/ingest/fda_ndc/trigger", { method: "POST" });
    const res = await triggerRun(req, "fda_ndc");
    expect(res.headers.get("x-correlation-id")).toBeTruthy();
  });
});

// ── getHistory ───────────────────────────────────────────────────────────────

describe("getHistory", () => {
  it("returns 401 without Authorization header", async () => {
    const req = makeRequest("http://bff/ingest/fda_ndc/history", { token: null });
    const res = await getHistory(req, "fda_ndc");
    expect(res.status).toBe(401);
  });

  it("returns 404 for non-triggerable source", async () => {
    const req = makeRequest("http://bff/ingest/fdb/history");
    const res = await getHistory(req, "fdb");
    expect(res.status).toBe(404);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies GET to backend history endpoint", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [],
    });
    const req = makeRequest("http://bff/ingest/fda_ndc/history?limit=10");
    const res = await getHistory(req, "fda_ndc");
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/data-ingestion/fda_ndc/history"),
      expect.any(Object),
    );
  });
});

// ── getRunDetail ─────────────────────────────────────────────────────────────

describe("getRunDetail", () => {
  it("returns 401 without Authorization header", async () => {
    const req = makeRequest("http://bff/ingest/runs/run-1", { token: null });
    const res = await getRunDetail(req, "run-1");
    expect(res.status).toBe(401);
  });

  it("proxies GET to backend run detail endpoint", async () => {
    const runId = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: runId, source: "fda_ndc", status: "completed" }),
    });
    const req = makeRequest(`http://bff/ingest/runs/${runId}`);
    const res = await getRunDetail(req, runId);
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining(`/api/v1/data-ingestion/runs/${runId}`),
      expect.any(Object),
    );
  });

  it("does NOT apply source SSRF guard (run IDs are not source keys)", async () => {
    // run IDs are server-generated UUIDs — no allowlist check needed
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: { error: { code: "RUN_NOT_FOUND" } } }),
    });
    const req = makeRequest("http://bff/ingest/runs/no-such-run");
    const res = await getRunDetail(req, "no-such-run");
    // fetch was called (no SSRF block for run IDs)
    expect(mockFetch).toHaveBeenCalled();
    expect(res.status).toBe(404);
  });
});

// ── cancelRun ────────────────────────────────────────────────────────────────

describe("cancelRun", () => {
  it("returns 401 without Authorization header", async () => {
    const req = makeRequest("http://bff/ingest/fda_ndc/cancel", {
      method: "POST",
      token: null,
    });
    const res = await cancelRun(req, "fda_ndc");
    expect(res.status).toBe(401);
  });

  it("returns 404 for non-triggerable source (SSRF guard)", async () => {
    const req = makeRequest("http://bff/ingest/bpg/cancel", { method: "POST" });
    const res = await cancelRun(req, "bpg");
    expect(res.status).toBe(404);
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("proxies POST to backend cancel endpoint", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ run_id: "r", source: "fda_ndc", status: "cancelled", message: "done" }),
    });
    const req = makeRequest("http://bff/ingest/fda_ndc/cancel", {
      method: "POST",
      body: { reason: "test cancel" },
    });
    const res = await cancelRun(req, "fda_ndc");
    expect(res.status).toBe(200);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/data-ingestion/fda_ndc/cancel"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});

// ── getAllStatus ──────────────────────────────────────────────────────────────

describe("getAllStatus", () => {
  it("returns 401 without Authorization header", async () => {
    const req = makeRequest("http://bff/ingest/status", { token: null });
    const res = await getAllStatus(req);
    expect(res.status).toBe(401);
  });

  it("proxies GET to backend status endpoint and returns list", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => [{ source: "fda_ndc", enabled: true, cron_expression: "0 2 * * *" }],
    });
    const req = makeRequest("http://bff/ingest/status");
    const res = await getAllStatus(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    expect(body[0].source).toBe("fda_ndc");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/data-ingestion/status"),
      expect.any(Object),
    );
  });
});
