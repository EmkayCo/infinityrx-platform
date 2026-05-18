// tests/integration/ingestion-trigger-idempotency.test.ts
// Integration tests for BFF ingestion trigger handler idempotency and error cases.
//
// Exercises triggerRun() end-to-end:
//   auth → SSRF source allowlist guard → backend proxy → response propagation
//
// Self-contained unit-integration tests: fetch is stubbed via vi.stubGlobal.
// No docker backends required.
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { NextRequest } from "../../src/__mocks__/next-server.js";
import { triggerRun } from "../../src/bff/ingest.js";

// ── Mock @infinityrx/auth ─────────────────────────────────────────────────────
vi.mock("@infinityrx/auth", () => ({
  verifyTokenRaw: vi.fn(),
  AccessClaimsSchema: { safeParse: vi.fn() },
  resolveEnvClaim: vi.fn().mockReturnValue("development"),
}));

import { verifyTokenRaw, AccessClaimsSchema } from "@infinityrx/auth";
const mockVerify = vi.mocked(verifyTokenRaw);
const mockSafeParse = vi.mocked(AccessClaimsSchema.safeParse);

// ── Shared mock fetch ─────────────────────────────────────────────────────────
const mockFetch = vi.fn();

function makeClaims() {
  return {
    sub: "00000000-0000-0000-0000-000000000001",
    tid: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    roles: ["operator"],
    typ: "access",
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 3600,
  };
}

function makeRequest(source: string, token = "valid-token"): NextRequest {
  return new NextRequest(
    `http://localhost/api/directories/ingest/${source}/trigger`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({ run_type: "manual_trigger" }),
    },
  );
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

// ── Test 1: trigger succeeds → 202 from backend proxied to client ─────────────

describe("ingestion trigger: successful trigger", () => {
  it("returns 202 with run_id when backend accepts the trigger", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const BACKEND_BODY = {
      run_id: "aaaaaaaa-0001-0001-0001-000000000001",
      source: "nppes",
      status: "queued",
      message: "Ingestion run queued",
    };
    mockFetch.mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => BACKEND_BODY,
    });

    const res = await triggerRun(makeRequest("nppes"), "nppes");
    const body = await res.json();

    expect(res.status).toBe(202);
    expect(body.run_id).toBe("aaaaaaaa-0001-0001-0001-000000000001");
    expect(body.source).toBe("nppes");
    expect(body.status).toBe("queued");

    // Verify the backend was called at the correct URL
    expect(mockFetch).toHaveBeenCalledOnce();
    const [calledUrl] = mockFetch.mock.calls[0] as [string, ...unknown[]];
    expect(calledUrl).toContain("/api/v1/data-ingestion/nppes/trigger");
  });
});

// ── Test 2: same source already running → backend returns 409 ────────────────

describe("ingestion trigger: duplicate trigger while run in progress", () => {
  it("returns 409 when backend reports source already running", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    mockFetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({
        error: {
          code: "RUN_IN_PROGRESS",
          message: "A run for source 'ncpdp' is already in progress",
          correlation_id: "test-correlation-id",
        },
      }),
    });

    const res = await triggerRun(makeRequest("ncpdp"), "ncpdp");
    const body = await res.json();

    expect(res.status).toBe(409);
    expect(body.error.code).toBe("RUN_IN_PROGRESS");
  });
});

// ── Test 3: non-triggerable source (bpg) → SSRF guard → 404, no backend call ─

describe("ingestion trigger: non-triggerable source returns 404", () => {
  it("returns 404 for 'bpg' without calling the backend", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const res = await triggerRun(makeRequest("bpg"), "bpg");
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.error.code).toBe("SOURCE_NOT_FOUND");
    // SSRF guard must fire before any backend fetch
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 404 for 'fdb' without calling the backend", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const res = await triggerRun(makeRequest("fdb"), "fdb");
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.error.code).toBe("SOURCE_NOT_FOUND");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ── Test 4: unknown source → SSRF guard → 404, no backend call ───────────────

describe("ingestion trigger: unknown source returns 404", () => {
  it("returns 404 for a completely unknown source string", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    const res = await triggerRun(makeRequest("nonexistent_source"), "nonexistent_source");
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.error.code).toBe("SOURCE_NOT_FOUND");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ── Test 5: unauthenticated → 401 before SSRF guard or backend ───────────────

describe("ingestion trigger: auth rejection blocks trigger", () => {
  it("returns 401 when no Authorization header is present", async () => {
    const req = new NextRequest(
      "http://localhost/api/directories/ingest/nppes/trigger",
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ run_type: "manual_trigger" }),
      },
    );

    const res = await triggerRun(req, "nppes");
    const body = await res.json();

    expect(res.status).toBe(401);
    expect(body.error.code).toBe("UNAUTHORIZED");
    // Auth must fire before any backend fetch
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("returns 401 when JWT verification fails", async () => {
    mockVerify.mockRejectedValue(new Error("invalid signature"));

    const res = await triggerRun(makeRequest("nppes", "bad-token"), "nppes");
    const body = await res.json();

    expect(res.status).toBe(401);
    expect(body.error.code).toBe("UNAUTHORIZED");
    expect(mockFetch).not.toHaveBeenCalled();
  });
});

// ── Test 6: x-correlation-id header is echoed back in response ────────────────

describe("ingestion trigger: correlation ID propagation", () => {
  it("echoes x-correlation-id from crypto.randomUUID in the response header", async () => {
    const claims = makeClaims();
    mockVerify.mockResolvedValue(claims as never);
    mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

    mockFetch.mockResolvedValue({
      ok: true,
      status: 202,
      json: async () => ({
        run_id: "aaaaaaaa-0001-0001-0001-000000000001",
        source: "fda_ndc",
        status: "queued",
      }),
    });

    const res = await triggerRun(makeRequest("fda_ndc"), "fda_ndc");

    expect(res.status).toBe(202);
    expect(res.headers.get("x-correlation-id")).toBe("test-correlation-id");
  });
});

// ── Test 7: triggerable sources spot-check — all 20 pass SSRF guard ──────────

describe("ingestion trigger: SSRF allowlist spot-check", () => {
  const TRIGGERABLE_SAMPLE = [
    "nppes",
    "nppes_monthly",
    "nppes_deactivation",
    "ncpdp",
    "fda_ndc",
    "hcpcs",
    "icd10_cm",
    "cms_asp",
    "cms_nadac",
    "ofac_sdn",
    "sam_exclusions",
    "oig_leie",
    "dea_registrations",
  ] as const;

  for (const source of TRIGGERABLE_SAMPLE) {
    it(`source '${source}' passes SSRF guard and reaches backend`, async () => {
      const claims = makeClaims();
      mockVerify.mockResolvedValue(claims as never);
      mockSafeParse.mockReturnValue({ success: true, data: claims } as never);

      mockFetch.mockResolvedValue({
        ok: true,
        status: 202,
        json: async () => ({ run_id: "test-run-id", source, status: "queued" }),
      });

      const res = await triggerRun(makeRequest(source), source);

      expect(res.status).toBe(202);
      expect(mockFetch).toHaveBeenCalledOnce();
      const [calledUrl] = mockFetch.mock.calls[0] as [string, ...unknown[]];
      expect(calledUrl).toContain(`/api/v1/data-ingestion/${source}/trigger`);

      // Reset for next iteration
      mockFetch.mockReset();
      mockVerify.mockReset();
      mockSafeParse.mockReset();
    });
  }
});
