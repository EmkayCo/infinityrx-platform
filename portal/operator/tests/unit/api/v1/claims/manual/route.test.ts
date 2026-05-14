/**
 * B11 w2.x.1 — Real route-handler unit tests for POST /api/v1/claims/manual.
 *
 * Codex adversarial R2 BLOCK #3: previously only had an `export {};` stub
 * + an e2e Playwright assertion. This file adds direct route-handler
 * coverage with NextRequest mocks for:
 *
 *   - pharmacy/compound → adjudication-engine routing
 *   - medical → medical-claims routing
 *   - missing/invalid claim_type → 400 INVALID_CLAIM_TYPE
 *   - 422 from backend → propagated as 422 (upstream validation surfaced)
 *   - 500 from backend → 500 (not propagated as 5xx; backend error)
 *   - TIMEOUT/NETWORK → 502 (backend unreachable, infra issue)
 *   - PARSE_ERROR → 500 (backend contract regression)
 *   - Unauth (no session) → 401 from BFF
 *   - Invalid JSON body → 400 INVALID_JSON
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

import { POST } from "@/app/api/v1/claims/manual/route";

function makeJwt(claims: Record<string, unknown>): string {
  const header = Buffer.from(
    JSON.stringify({ alg: "HS256", typ: "JWT" })
  ).toString("base64url");
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `${header}.${payload}.fake_signature`;
}

function authedSession() {
  authMock.mockResolvedValue({
    user: {
      id: "u1",
      tenant_id: "tenant-alpha",
      permissions: ["platform_admin"],
    },
    access_token: makeJwt({ tid: "tenant-alpha", sub: "u1" }),
  });
}

function makeRequest(body: unknown): NextRequest {
  return new NextRequest("http://localhost:3000/api/v1/claims/manual", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

describe("POST /api/v1/claims/manual", () => {
  beforeEach(() => {
    authMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await POST(makeRequest({ claim_type: "pharmacy" }));
    expect(resp.status).toBe(401);
  });

  it("returns 400 when body is not valid JSON", async () => {
    authedSession();
    // Construct a request with body that's not valid JSON.
    const req = new NextRequest("http://localhost:3000/api/v1/claims/manual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "this is not json",
    });
    const resp = await POST(req);
    expect(resp.status).toBe(400);
    const json = (await resp.json()) as { error: { code: string } };
    expect(json.error.code).toBe("INVALID_JSON");
  });

  it("returns 400 INVALID_CLAIM_TYPE when claim_type is missing", async () => {
    authedSession();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const resp = await POST(makeRequest({ first_name: "Test", last_name: "Patient" }));
    expect(resp.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled(); // never reached upstream
    const json = (await resp.json()) as { error: { code: string; received: unknown } };
    expect(json.error.code).toBe("INVALID_CLAIM_TYPE");
    expect(json.error.received).toBeNull();
  });

  it("returns 400 INVALID_CLAIM_TYPE when claim_type is unknown", async () => {
    authedSession();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const resp = await POST(makeRequest({ claim_type: "DENTAL" }));
    expect(resp.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
    const json = (await resp.json()) as { error: { received: string } };
    expect(json.error.received).toBe("dental");
  });

  it("forwards pharmacy claim_type to adjudication-engine /claims/adjudicate", async () => {
    authedSession();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ id: "adj-1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const resp = await POST(makeRequest({ claim_type: "pharmacy", first_name: "Test" }));
    expect(resp.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toBe("http://localhost:8013/claims/adjudicate");
  });

  it("forwards compound claim_type to adjudication-engine /claims/adjudicate", async () => {
    authedSession();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ id: "adj-2" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const resp = await POST(makeRequest({ claim_type: "compound", first_name: "Test" }));
    expect(resp.status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8013/claims/adjudicate");
  });

  it("forwards medical claim_type to medical-claims /api/v1/medical-claims/claims", async () => {
    authedSession();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ id: "mc-1" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const resp = await POST(makeRequest({ claim_type: "medical", first_name: "Test" }));
    expect(resp.status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://localhost:8006/api/v1/medical-claims/claims"
    );
  });

  it("propagates upstream 4xx (e.g., 422 validation) to the caller", async () => {
    authedSession();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("validation failed", { status: 422 }))
    );

    const resp = await POST(makeRequest({ claim_type: "pharmacy" }));
    expect(resp.status).toBe(422);
    const json = (await resp.json()) as {
      error: { code: string; upstream_status: number };
    };
    expect(json.error.code).toBe("UPSTREAM_ERROR");
    expect(json.error.upstream_status).toBe(422);
  });

  it("returns 502 on TIMEOUT/NETWORK (backend unreachable, infra issue)", async () => {
    authedSession();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed: ECONNREFUSED"))
    );

    const resp = await POST(makeRequest({ claim_type: "pharmacy" }));
    expect(resp.status).toBe(502);
    const json = (await resp.json()) as { error: { code: string } };
    expect(json.error.code).toBe("NETWORK");
  });

  it("returns 500 on upstream 5xx (backend bug)", async () => {
    authedSession();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("backend went boom", { status: 500 }))
    );

    const resp = await POST(makeRequest({ claim_type: "medical" }));
    expect(resp.status).toBe(500);
  });

  it("returns 500 on PARSE_ERROR (backend contract drift)", async () => {
    authedSession();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not-json-at-all", { status: 200 }))
    );

    const resp = await POST(makeRequest({ claim_type: "pharmacy" }));
    expect(resp.status).toBe(500);
    const json = (await resp.json()) as { error: { code: string } };
    expect(json.error.code).toBe("PARSE_ERROR");
  });
});
