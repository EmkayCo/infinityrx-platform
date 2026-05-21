/**
 * Auth-gate tests for GET /api/paysync/reconciliations and GET /api/paysync/reconciliations/[id].
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListReconciliations, mockHandleGetReconciliation } = vi.hoisted(() => ({
  mockHandleListReconciliations: vi.fn(), mockHandleGetReconciliation: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListReconciliations: mockHandleListReconciliations, handleGetReconciliation: mockHandleGetReconciliation,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealReconciliationsClient } = vi.hoisted(() => ({ mockCreateRealReconciliationsClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealReconciliationsClient: mockCreateRealReconciliationsClient }));

import { GET as listGET } from "@/app/api/paysync/reconciliations/route";
import { GET as detailGET } from "@/app/api/paysync/reconciliations/[id]/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/reconciliations", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListReconciliations.mockReset(); mockCreateRealReconciliationsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/reconciliations"))).status).toBe(401);
    expect(mockHandleListReconciliations).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealReconciliationsClient.mockReturnValue({});
    mockHandleListReconciliations.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/reconciliations"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealReconciliationsClient.mockReturnValue({});
    mockHandleListReconciliations.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/reconciliations"))).status).toBe(502);
  });
});

describe("GET /api/paysync/reconciliations/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetReconciliation.mockReset(); mockCreateRealReconciliationsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/reconciliations/r1"), { params: Promise.resolve({ id: "r1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetReconciliation).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealReconciliationsClient.mockReturnValue({});
    mockHandleGetReconciliation.mockResolvedValue({ data: { id: "r1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/reconciliations/r1"), { params: Promise.resolve({ id: "r1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealReconciliationsClient.mockReturnValue({});
    mockHandleGetReconciliation.mockRejectedValue(new Error("down"));
    expect((await detailGET(new NextRequest("http://localhost/api/paysync/reconciliations/r1"), { params: Promise.resolve({ id: "r1" }) })).status).toBe(502);
  });
});
