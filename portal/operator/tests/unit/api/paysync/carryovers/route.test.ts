/**
 * Auth-gate tests for GET /api/paysync/carryovers and GET /api/paysync/carryovers/[id].
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListCarryovers, mockHandleGetCarryover } = vi.hoisted(() => ({
  mockHandleListCarryovers: vi.fn(), mockHandleGetCarryover: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListCarryovers: mockHandleListCarryovers, handleGetCarryover: mockHandleGetCarryover,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealCarryoversClient } = vi.hoisted(() => ({ mockCreateRealCarryoversClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealCarryoversClient: mockCreateRealCarryoversClient }));

import { GET as listGET } from "@/app/api/paysync/carryovers/route";
import { GET as detailGET } from "@/app/api/paysync/carryovers/[id]/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/carryovers", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListCarryovers.mockReset(); mockCreateRealCarryoversClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/carryovers"))).status).toBe(401);
    expect(mockHandleListCarryovers).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealCarryoversClient.mockReturnValue({});
    mockHandleListCarryovers.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/carryovers"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealCarryoversClient.mockReturnValue({});
    mockHandleListCarryovers.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/carryovers"))).status).toBe(502);
  });
});

describe("GET /api/paysync/carryovers/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetCarryover.mockReset(); mockCreateRealCarryoversClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/carryovers/c1"), { params: Promise.resolve({ id: "c1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetCarryover).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealCarryoversClient.mockReturnValue({});
    mockHandleGetCarryover.mockResolvedValue({ data: { id: "c1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/carryovers/c1"), { params: Promise.resolve({ id: "c1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealCarryoversClient.mockReturnValue({});
    mockHandleGetCarryover.mockRejectedValue(new Error("down"));
    expect((await detailGET(new NextRequest("http://localhost/api/paysync/carryovers/c1"), { params: Promise.resolve({ id: "c1" }) })).status).toBe(502);
  });
});
