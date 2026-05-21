/**
 * Auth-gate tests for GET /api/paysync/payment-runs, GET /api/paysync/payment-runs/[id],
 * and POST /api/paysync/payment-runs/[id]/manual-ap (RBAC gate: 403 without approver role).
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListPaymentRuns, mockHandleGetPaymentRun } = vi.hoisted(() => ({
  mockHandleListPaymentRuns: vi.fn(), mockHandleGetPaymentRun: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListPaymentRuns: mockHandleListPaymentRuns, handleGetPaymentRun: mockHandleGetPaymentRun,
  handleListUploads: vi.fn(), handleCreateUpload: vi.fn(), handleGetUpload: vi.fn(), handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealPaymentRunsClient, mockForwardJson } = vi.hoisted(() => ({
  mockCreateRealPaymentRunsClient: vi.fn(),
  mockForwardJson: vi.fn(),
}));
vi.mock("@infinityrx/contract", () => ({ createRealPaymentRunsClient: mockCreateRealPaymentRunsClient }));
vi.mock("@/lib/bff", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/bff")>();
  return { ...real, forwardJson: mockForwardJson };
});

import { GET as listGET } from "@/app/api/paysync/payment-runs/route";
import { GET as detailGET } from "@/app/api/paysync/payment-runs/[id]/route";
import { POST as manualApPOST } from "@/app/api/paysync/payment-runs/[id]/manual-ap/route";

function makeJwt(c: Record<string, unknown>) { return `${Buffer.from("{}").toString("base64url")}.${Buffer.from(JSON.stringify(c)).toString("base64url")}.s`; }
function authedWithRoles(roles: string[]) {
  authMock.mockResolvedValue({ user: { id: "u1", tenant_id: "t1", permissions: roles }, access_token: makeJwt({ tid: "t1", sub: "u1" }) });
}

describe("GET /api/paysync/payment-runs", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleListPaymentRuns.mockReset(); mockCreateRealPaymentRunsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    expect((await listGET(new NextRequest("http://localhost/api/paysync/payment-runs"))).status).toBe(401);
    expect(mockHandleListPaymentRuns).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authedWithRoles(["operator"]); mockCreateRealPaymentRunsClient.mockReturnValue({});
    mockHandleListPaymentRuns.mockResolvedValue({ data: { results: [] }, status: 200, headers: {} });
    const resp = await listGET(new NextRequest("http://localhost/api/paysync/payment-runs"));
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 when handler throws", async () => {
    authedWithRoles(["operator"]); mockCreateRealPaymentRunsClient.mockReturnValue({});
    mockHandleListPaymentRuns.mockRejectedValue(new Error("down"));
    expect((await listGET(new NextRequest("http://localhost/api/paysync/payment-runs"))).status).toBe(502);
  });
});

describe("GET /api/paysync/payment-runs/[id]", () => {
  beforeEach(() => { authMock.mockReset(); mockHandleGetPaymentRun.mockReset(); mockCreateRealPaymentRunsClient.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/payment-runs/pr1"), { params: Promise.resolve({ id: "pr1" }) });
    expect(resp.status).toBe(401);
    expect(mockHandleGetPaymentRun).not.toHaveBeenCalled();
  });

  it("delegates when authenticated", async () => {
    authedWithRoles(["operator"]); mockCreateRealPaymentRunsClient.mockReturnValue({});
    mockHandleGetPaymentRun.mockResolvedValue({ data: { id: "pr1" }, status: 200, headers: {} });
    const resp = await detailGET(new NextRequest("http://localhost/api/paysync/payment-runs/pr1"), { params: Promise.resolve({ id: "pr1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });
});

describe("POST /api/paysync/payment-runs/[id]/manual-ap (RBAC gate)", () => {
  beforeEach(() => { authMock.mockReset(); mockForwardJson.mockReset(); });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const req = new NextRequest("http://localhost/api/paysync/payment-runs/pr1/manual-ap", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
    expect((await manualApPOST(req, { params: Promise.resolve({ id: "pr1" }) })).status).toBe(401);
  });

  it("returns 403 when session lacks approver role", async () => {
    authedWithRoles(["read_only"]);
    const req = new NextRequest("http://localhost/api/paysync/payment-runs/pr1/manual-ap", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
    const resp = await manualApPOST(req, { params: Promise.resolve({ id: "pr1" }) });
    expect(resp.status).toBe(403);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("FORBIDDEN");
    expect(mockForwardJson).not.toHaveBeenCalled();
  });

  it("delegates to forwardJson when session has billing_approver role", async () => {
    authedWithRoles(["billing_approver"]);
    mockForwardJson.mockResolvedValue({ ok: true, data: { id: "ap1" } });
    const req = new NextRequest("http://localhost/api/paysync/payment-runs/pr1/manual-ap", { method: "POST", body: JSON.stringify({ amount: "10.00" }), headers: { "Content-Type": "application/json" } });
    const resp = await manualApPOST(req, { params: Promise.resolve({ id: "pr1" }) });
    expect(resp.status).toBe(200);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    expect(mockForwardJson).toHaveBeenCalledOnce();
  });
});
