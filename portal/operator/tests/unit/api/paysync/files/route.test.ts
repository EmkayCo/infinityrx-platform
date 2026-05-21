/**
 * Auth-gate tests for GET /api/paysync/files and GET /api/paysync/files/[id].
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListFiles, mockHandleGetFile } = vi.hoisted(() => ({
  mockHandleListFiles: vi.fn(), mockHandleGetFile: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListFiles: mockHandleListFiles, handleGetFile: mockHandleGetFile,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealFilesClient } = vi.hoisted(() => ({ mockCreateRealFilesClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealFilesClient: mockCreateRealFilesClient }));

import { GET as listGET } from "@/app/api/paysync/files/route";
import { GET as detailGET } from "@/app/api/paysync/files/[id]/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/files", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListFiles.mockReset(); mockCreateRealFilesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/files"))).status).toBe(401);
    expect(mockHandleListFiles).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealFilesClient.mockReturnValue({});
    mockHandleListFiles.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/files"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealFilesClient.mockReturnValue({});
    mockHandleListFiles.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/files"))).status).toBe(502);
  });
});

describe("GET /api/paysync/files/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetFile.mockReset(); mockCreateRealFilesClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/files/f1"), { params: Promise.resolve({ id: "f1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetFile).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authed(); mockCreateRealFilesClient.mockReturnValue({});
    mockHandleGetFile.mockResolvedValue({ data: { id: "f1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/files/f1"), { params: Promise.resolve({ id: "f1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealFilesClient.mockReturnValue({});
    mockHandleGetFile.mockRejectedValue(new Error("down"));
    expect((await detailGET(new NextRequest("http://localhost/api/paysync/files/f1"), { params: Promise.resolve({ id: "f1" }) })).status).toBe(502);
  });
});
