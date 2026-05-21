/**
 * Auth-gate tests for GET /api/paysync/cycles and GET /api/paysync/cycles/[id].
 *
 * Pattern mirrors portal/operator/tests/unit/api/paysync/uploads/route.test.ts.
 * Each route: unauthenticated → 401 (handler not called), authenticated → delegates
 * to BFF handler, handler throws → 502 UPSTREAM_ERROR.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListCycles, mockHandleGetCycle } = vi.hoisted(() => ({
  mockHandleListCycles: vi.fn(),
  mockHandleGetCycle: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListCycles: mockHandleListCycles,
  handleGetCycle: mockHandleGetCycle,
  handleCloseCycle: vi.fn(),
  // other handlers stubbed to prevent missing-export errors
  handleListUploads: vi.fn(),
  handleCreateUpload: vi.fn(),
  handleGetUpload: vi.fn(),
  handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealCyclesClient } = vi.hoisted(() => ({
  mockCreateRealCyclesClient: vi.fn(),
}));
vi.mock("@infinityrx/contract", () => ({
  createRealCyclesClient: mockCreateRealCyclesClient,
}));

import { GET as listGET } from "@/app/api/paysync/cycles/route";
import { GET as detailGET } from "@/app/api/paysync/cycles/[id]/route";

function makeJwt(claims: Record<string, unknown>): string {
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `${header}.${payload}.fake_sig`;
}

function authedSession() {
  authMock.mockResolvedValue({
    user: { id: "u1", tenant_id: "tenant-alpha", permissions: ["operator"] },
    access_token: makeJwt({ tid: "tenant-alpha", sub: "u1" }),
  });
}

// --- GET /api/paysync/cycles ---
describe("GET /api/paysync/cycles", () => {
  beforeEach(() => {
    authMock.mockReset();
    mockHandleListCycles.mockReset();
    mockCreateRealCyclesClient.mockReset();
  });

  it("returns 401 when no session (handler never called)", async () => {
    authMock.mockResolvedValue(null);
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles");
    const resp = await listGET(req);
    expect(resp.status).toBe(401);
    expect(mockHandleListCycles).not.toHaveBeenCalled();
  });

  it("delegates to handleListCycles when authenticated", async () => {
    authedSession();
    mockCreateRealCyclesClient.mockReturnValue({});
    mockHandleListCycles.mockResolvedValue({ data: { results: [], total: 0 }, status: 200, headers: {} });
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles");
    const resp = await listGET(req);
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    expect(mockHandleListCycles).toHaveBeenCalledOnce();
  });

  it("returns 502 UPSTREAM_ERROR when handler throws", async () => {
    authedSession();
    mockCreateRealCyclesClient.mockReturnValue({});
    mockHandleListCycles.mockRejectedValue(new Error("backend down"));
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles");
    const resp = await listGET(req);
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UPSTREAM_ERROR");
  });
});

// --- GET /api/paysync/cycles/[id] ---
describe("GET /api/paysync/cycles/[id]", () => {
  beforeEach(() => {
    authMock.mockReset();
    mockHandleGetCycle.mockReset();
    mockCreateRealCyclesClient.mockReset();
  });

  it("returns 401 when no session (handler never called)", async () => {
    authMock.mockResolvedValue(null);
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles/cyc-1");
    const resp = await detailGET(req, { params: Promise.resolve({ id: "cyc-1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetCycle).not.toHaveBeenCalled();
  });

  it("delegates to handleGetCycle when authenticated", async () => {
    authedSession();
    mockCreateRealCyclesClient.mockReturnValue({});
    mockHandleGetCycle.mockResolvedValue({ data: { id: "cyc-1" }, status: 200, headers: {} });
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles/cyc-1");
    const resp = await detailGET(req, { params: Promise.resolve({ id: "cyc-1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    expect(mockHandleGetCycle).toHaveBeenCalledOnce();
  });

  it("returns 502 UPSTREAM_ERROR when handler throws", async () => {
    authedSession();
    mockCreateRealCyclesClient.mockReturnValue({});
    mockHandleGetCycle.mockRejectedValue(new Error("backend down"));
    const req = new NextRequest("http://localhost:3000/api/paysync/cycles/cyc-1");
    const resp = await detailGET(req, { params: Promise.resolve({ id: "cyc-1" }) });
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UPSTREAM_ERROR");
  });
});
