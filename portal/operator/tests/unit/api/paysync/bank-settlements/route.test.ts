/**
 * Auth-gate tests for GET /api/paysync/bank-settlements and GET /api/paysync/bank-settlements/[id].
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListBankSettlements, mockHandleGetBankSettlement } = vi.hoisted(() => ({
  mockHandleListBankSettlements: vi.fn(), mockHandleGetBankSettlement: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListBankSettlements: mockHandleListBankSettlements, handleGetBankSettlement: mockHandleGetBankSettlement,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealBankSettlementsClient } = vi.hoisted(() => ({ mockCreateRealBankSettlementsClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealBankSettlementsClient: mockCreateRealBankSettlementsClient }));

import { GET as listGET } from "@/app/api/paysync/bank-settlements/route";
import { GET as detailGET } from "@/app/api/paysync/bank-settlements/[id]/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/bank-settlements", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListBankSettlements.mockReset(); mockCreateRealBankSettlementsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/bank-settlements"))).status).toBe(401);
    expect(mockHandleListBankSettlements).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealBankSettlementsClient.mockReturnValue({});
    mockHandleListBankSettlements.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/bank-settlements"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealBankSettlementsClient.mockReturnValue({});
    mockHandleListBankSettlements.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/bank-settlements"))).status).toBe(502);
  });
});

describe("GET /api/paysync/bank-settlements/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetBankSettlement.mockReset(); mockCreateRealBankSettlementsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/bank-settlements/bs1"), { params: Promise.resolve({ id: "bs1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetBankSettlement).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealBankSettlementsClient.mockReturnValue({});
    mockHandleGetBankSettlement.mockResolvedValue({ data: { id: "bs1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/bank-settlements/bs1"), { params: Promise.resolve({ id: "bs1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealBankSettlementsClient.mockReturnValue({});
    mockHandleGetBankSettlement.mockRejectedValue(new Error("down"));
    expect((await detailGET(new NextRequest("http://localhost/api/paysync/bank-settlements/bs1"), { params: Promise.resolve({ id: "bs1" }) })).status).toBe(502);
  });
});
