// tests/unit/bff-audit.test.ts
// BFF audit proxy handler tests (SP-2 Plan D Task D-4).
//
// Coverage targets:
//   - 100% on auth validation (_verifyAuth) — all branches
//   - 100% on JWT forwarding to core-platform (auth path)
//   - 99% overall
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import { getAuditLog } from "../../src/bff/audit.js";

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

const mockFetch = vi.fn();

const SAMPLE_AUDIT_PAGE = {
  items: [
    {
      id: 1,
      action: "POST /api/v1/data-ingestion/nppes/trigger",
      module: "prescriber_directory",
      entity_type: "ingestion_run",
      entity_id: "nppes",
      user_id: "00000000-0000-0000-0000-000000000001",
      timestamp: "2026-05-15T03:00:00Z",
      correlation_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch);
  vi.stubGlobal("crypto", {
    randomUUID: () => "dddddddd-dddd-dddd-dddd-dddddddddddd",
  });
  mockVerifyTokenRaw.mockResolvedValue(VALID_CLAIMS as never);
  mockSafeParse.mockReturnValue({ success: true, data: VALID_CLAIMS } as never);
  mockFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => SAMPLE_AUDIT_PAGE,
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function makeRequest(
  url: string,
  opts: { token?: string | null } = {},
): NextRequest {
  const { token = VALID_TOKEN } = opts;
  const headers: Record<string, string> = {};
  if (token !== null) headers["authorization"] = `Bearer ${token}`;
  return new NextRequest(url, { method: "GET", headers });
}

// ── Auth gate ────────────────────────────────────────────────────────────────

describe("getAuditLog — auth gate", () => {
  it("returns 401 when no Authorization header", async () => {
    const req = makeRequest("http://localhost/api/directories/audit", {
      token: null,
    });
    const res = await getAuditLog(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when verifyTokenRaw throws", async () => {
    mockVerifyTokenRaw.mockRejectedValueOnce(new Error("expired"));
    const req = makeRequest("http://localhost/api/directories/audit");
    const res = await getAuditLog(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });

  it("returns 401 when AccessClaimsSchema.safeParse fails", async () => {
    mockSafeParse.mockReturnValueOnce({ success: false } as never);
    const req = makeRequest("http://localhost/api/directories/audit");
    const res = await getAuditLog(req);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error.code).toBe("UNAUTHORIZED");
  });
});

// ── JWT forwarding to core-platform ──────────────────────────────────────────

describe("getAuditLog — JWT forwarding", () => {
  it("forwards the original JWT as Authorization header to core-platform", async () => {
    const req = makeRequest("http://localhost/api/directories/audit");
    await getAuditLog(req);
    const backendCalls = mockFetch.mock.calls.filter((c) =>
      String(c[0]).includes("/api/v1/audit"),
    );
    expect(backendCalls).toHaveLength(1);
    const opts = backendCalls[0][1];
    expect(opts?.headers?.Authorization).toBe(AUTH_HEADER);
  });

  it("pre-applies module=prescriber_directory filter", async () => {
    const req = makeRequest("http://localhost/api/directories/audit");
    await getAuditLog(req);
    const [backendUrl] = mockFetch.mock.calls[0];
    expect(String(backendUrl)).toContain("module=prescriber_directory");
  });

  it("pre-applies date_from 90-day window", async () => {
    const req = makeRequest("http://localhost/api/directories/audit");
    await getAuditLog(req);
    const [backendUrl] = mockFetch.mock.calls[0];
    expect(String(backendUrl)).toContain("date_from=");
    // date_from should be approximately 90 days ago.
    const url = new URL(String(backendUrl));
    const dateFrom = new Date(url.searchParams.get("date_from")!);
    const daysAgo = (Date.now() - dateFrom.getTime()) / (1000 * 60 * 60 * 24);
    expect(daysAgo).toBeGreaterThan(89);
    expect(daysAgo).toBeLessThan(91);
  });

  it("returns the core-platform response as-is (200)", async () => {
    const req = makeRequest("http://localhost/api/directories/audit");
    const res = await getAuditLog(req);
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.items).toHaveLength(1);
    expect(body.total).toBe(1);
  });

  it("forwards 403 from core-platform (user lacks audit:read) as-is", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: { code: "FORBIDDEN", message: "audit:read required" } }),
    });
    const req = makeRequest("http://localhost/api/directories/audit");
    const res = await getAuditLog(req);
    // BFF passes the 403 through — not a BFF error.
    expect(res.status).toBe(403);
  });
});

// ── Query param handling ──────────────────────────────────────────────────────

describe("getAuditLog — query param handling", () => {
  it("forwards valid limit and offset to backend", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/audit?limit=25&offset=50",
    );
    await getAuditLog(req);
    const [backendUrl] = mockFetch.mock.calls[0];
    const url = new URL(String(backendUrl));
    expect(url.searchParams.get("limit")).toBe("25");
    expect(url.searchParams.get("offset")).toBe("50");
  });

  it("uses default limit=50 when limit param is invalid", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/audit?limit=abc",
    );
    await getAuditLog(req);
    const [backendUrl] = mockFetch.mock.calls[0];
    const url = new URL(String(backendUrl));
    expect(url.searchParams.get("limit")).toBe("50");
  });

  it("uses default offset=0 when offset param is invalid", async () => {
    const req = makeRequest(
      "http://localhost/api/directories/audit?offset=xyz",
    );
    await getAuditLog(req);
    const [backendUrl] = mockFetch.mock.calls[0];
    const url = new URL(String(backendUrl));
    expect(url.searchParams.get("offset")).toBe("0");
  });
});
