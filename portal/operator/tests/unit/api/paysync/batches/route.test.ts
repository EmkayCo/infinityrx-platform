/**
 * Auth-gate tests for GET /api/paysync/batches and GET /api/paysync/batches/[id].
 * Pattern: unauthenticated → 401 (handler not called), authenticated → 200 + no-store,
 * handler throws → 502 UPSTREAM_ERROR.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListBatches, mockHandleGetBatch } = vi.hoisted(() => ({
  mockHandleListBatches: vi.fn(),
  mockHandleGetBatch: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListBatches: mockHandleListBatches,
  handleGetBatch: mockHandleGetBatch,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealBatchesClient } = vi.hoisted(() => ({ mockCreateRealBatchesClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealBatchesClient: mockCreateRealBatchesClient }));

import { GET as listGET } from "@/app/api/paysync/batches/route";
import { GET as detailGET } from "@/app/api/paysync/batches/[id]/route";

function makeJwt(claims: Record<string, unknown>) {
  const h = Buffer.from(JSON.stringify({ alg: "HS256" })).toString("base64url");
  const p = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return `${h}.${p}.sig`;
}
function authed() {
  authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) });
}

describe("GET /api/paysync/batches", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListBatches.mockReset(); mockCreateRealBatchesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/batches"));
    expect(resp.status).toBe(401);
    expect(mockHandleListBatches).not.toHaveBeenCalled();
  });

  it("delegates to handleListBatches when authenticated", async () => {
    authed(); mockCreateRealBatchesClient.mockReturnValue({});
    mockHandleListBatches.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/batches"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealBatchesClient.mockReturnValue({});
    mockHandleListBatches.mockRejectedValue(new Error("down"));
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/batches"));
    expect(resp.status).toBe(502);
  });
});

describe("GET /api/paysync/batches/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetBatch.mockReset(); mockCreateRealBatchesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/batches/b1"), { params: Promise.resolve({ id: "b1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetBatch).not.toHaveBeenCalled();
  });

  it("delegates to handleGetBatch when authenticated", async () => {
    authed(); mockCreateRealBatchesClient.mockReturnValue({});
    mockHandleGetBatch.mockResolvedValue({ data: { id: "b1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/batches/b1"), { params: Promise.resolve({ id: "b1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealBatchesClient.mockReturnValue({});
    mockHandleGetBatch.mockRejectedValue(new Error("down"));
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/batches/b1"), { params: Promise.resolve({ id: "b1" }) });
    expect(resp.status).toBe(502);
  });
});
