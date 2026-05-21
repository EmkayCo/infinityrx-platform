/**
 * Auth-gate tests for GET /api/paysync/invoices and GET /api/paysync/invoices/[id].
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListInvoices, mockHandleGetInvoice } = vi.hoisted(() => ({
  mockHandleListInvoices: vi.fn(), mockHandleGetInvoice: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListInvoices: mockHandleListInvoices, handleGetInvoice: mockHandleGetInvoice,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealInvoicesClient } = vi.hoisted(() => ({ mockCreateRealInvoicesClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealInvoicesClient: mockCreateRealInvoicesClient }));

import { GET as listGET } from "@/app/api/paysync/invoices/route";
import { GET as detailGET } from "@/app/api/paysync/invoices/[id]/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/invoices", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListInvoices.mockReset(); mockCreateRealInvoicesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/invoices"))).status).toBe(401);
    expect(mockHandleListInvoices).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealInvoicesClient.mockReturnValue({});
    mockHandleListInvoices.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/invoices"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealInvoicesClient.mockReturnValue({});
    mockHandleListInvoices.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/invoices"))).status).toBe(502);
  });
});

describe("GET /api/paysync/invoices/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetInvoice.mockReset(); mockCreateRealInvoicesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/invoices/i1"), { params: Promise.resolve({ id: "i1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetInvoice).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealInvoicesClient.mockReturnValue({});
    mockHandleGetInvoice.mockResolvedValue({ data: { id: "i1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/invoices/i1"), { params: Promise.resolve({ id: "i1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealInvoicesClient.mockReturnValue({});
    mockHandleGetInvoice.mockRejectedValue(new Error("down"));
    expect((await detailGET(new NextRequest("http://localhost/api/paysync/invoices/i1"), { params: Promise.resolve({ id: "i1" }) })).status).toBe(502);
  });
});
