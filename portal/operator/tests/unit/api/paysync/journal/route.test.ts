/**
 * Auth-gate tests for GET /api/paysync/journal, GET /api/paysync/journal/[id],
 * and POST /api/paysync/journal/verify-chain.
 * Journal routes must always set Cache-Control: no-store (financial audit hash-chain).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListJournal, mockHandleGetJournalEntry, mockHandleVerifyChain } = vi.hoisted(() => ({
  mockHandleListJournal: vi.fn(), mockHandleGetJournalEntry: vi.fn(), mockHandleVerifyChain: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListJournal: mockHandleListJournal, handleGetJournalEntry: mockHandleGetJournalEntry, handleVerifyChain: mockHandleVerifyChain,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealJournalClient } = vi.hoisted(() => ({ mockCreateRealJournalClient: vi.fn() }));
vi.mock("@infinityrx/contract", () => ({ createRealJournalClient: mockCreateRealJournalClient }));

import { GET as listGET } from "@/app/api/paysync/journal/route";
import { GET as detailGET } from "@/app/api/paysync/journal/[id]/route";
import { POST as verifyPOST } from "@/app/api/paysync/journal/verify-chain/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authed() { authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: [] }, access_token: makeJwt({ tid: "t1", sub: "u1" }) }); }

describe("GET /api/paysync/journal", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListJournal.mockReset(); mockCreateRealJournalClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/journal"))).status).toBe(401);
    expect(mockHandleListJournal).not.toHaveBeenCalled();
  });

  it("delegates when authenticated and sets Cache-Control: no-store", async () => {
    authed(); mockCreateRealJournalClient.mockReturnValue({});
    mockHandleListJournal.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/journal"));
    expect(resp.status).toBe(200);
    // Financial audit hash-chain: no-store is non-negotiable
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealJournalClient.mockReturnValue({});
    mockHandleListJournal.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/journal"))).status).toBe(502);
  });
});

describe("GET /api/paysync/journal/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetJournalEntry.mockReset(); mockCreateRealJournalClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/journal/j1"), { params: Promise.resolve({ id: "j1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetJournalEntry).not.toHaveBeenCalled();
  });

  it("delegates when authenticated, no-store header present", async () => {
    authed(); mockCreateRealJournalClient.mockReturnValue({});
    mockHandleGetJournalEntry.mockResolvedValue({ data: { id: "j1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/journal/j1"), { params: Promise.resolve({ id: "j1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });
});

describe("POST /api/paysync/journal/verify-chain", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleVerifyChain.mockReset(); mockCreateRealJournalClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await verifyPOST()).status).toBe(401);
    expect(mockHandleVerifyChain).not.toHaveBeenCalled();
  });

  it("delegates when authenticated, always sets no-store", async () => {
    authed(); mockCreateRealJournalClient.mockReturnValue({});
    mockHandleVerifyChain.mockResolvedValue({ data: { valid: true }, status: 200, headers: { "Cache-Control": "no-store" } });
    const resp = await verifyPOST();
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authed(); mockCreateRealJournalClient.mockReturnValue({});
    mockHandleVerifyChain.mockRejectedValue(new Error("chain broken"));
    expect((await verifyPOST()).status).toBe(502);
  });
});
