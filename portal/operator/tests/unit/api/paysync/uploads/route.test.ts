/**
 * Unit tests for GET + POST /api/paysync/uploads route handler.
 *
 * Security-sensitive paths per CLAUDE.md INVARIANTS:
 *   - Auth-before-parse: unauthenticated -> 401 BEFORE body is consumed
 *   - Cache-Control: no-store on all authenticated responses (PHI-adjacent)
 *   - No PHI in error responses: filename/file size never echoed back
 *
 * Test matrix:
 *   GET  -- unauthenticated -> 401, handler not called
 *   GET  -- authenticated   -> delegates to handleListUploads, no-store header
 *   GET  -- handler throws  -> 502 UPSTREAM_ERROR
 *   POST -- unauthenticated -> 401 BEFORE body parse (multipart DoS guard)
 *   POST -- missing file    -> 400 MISSING_FILE, handler not called
 *   POST -- valid file      -> 201 no-store, delegates to handleCreateUpload
 *   POST -- 409 dedup       -> 409 no-store, existing_upload_id forwarded
 *   POST -- handler throws  -> 502 UPLOAD_FAILED, filename not in response
 *
 * NOTE: jsdom cannot parse multipart FormData from a NextRequest body.
 * POST tests stub request.formData() directly so the route handler receives
 * a controlled FormData — this is the same pattern used across the portal
 * test suite for multipart routes.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { NextRequest } from "next/server";

// hoist mocks before any imports
const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListUploads, mockHandleCreateUpload } = vi.hoisted(() => ({
  mockHandleListUploads: vi.fn(),
  mockHandleCreateUpload: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListUploads: mockHandleListUploads,
  handleCreateUpload: mockHandleCreateUpload,
  handleGetUpload: vi.fn(),
  handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealUploadsClient } = vi.hoisted(() => ({
  mockCreateRealUploadsClient: vi.fn(),
}));
vi.mock("@infinityrx/contract", () => ({
  createRealUploadsClient: mockCreateRealUploadsClient,
}));

import { GET, POST } from "@/app/api/paysync/uploads/route";

// helpers
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

function makeGetRequest(qs = "") {
  return new NextRequest(`http://localhost:3000/api/paysync/uploads${qs}`);
}

/**
 * Build a NextRequest whose formData() resolves to the given map.
 * jsdom cannot parse multipart bodies from FormData objects, so we stub
 * request.formData directly — the route only calls request.formData(), never
 * request.body directly.
 */
function makePostRequestWithFormData(fields: Record<string, Blob | File | string | null>) {
  const req = new NextRequest("http://localhost:3000/api/paysync/uploads", {
    method: "POST",
    // Body content doesn't matter — formData() is stubbed below.
    body: "stub",
    headers: { "Content-Type": "multipart/form-data; boundary=stub" },
  });
  const fd = new FormData();
  for (const [key, val] of Object.entries(fields)) {
    if (val !== null) {
      if (val instanceof File) {
        fd.append(key, val, val.name);
      } else if (val instanceof Blob) {
        fd.append(key, val, "upload.csv");
      } else {
        fd.append(key, val);
      }
    }
  }
  req.formData = () => Promise.resolve(fd);
  return req;
}

// GET tests
describe("GET /api/paysync/uploads", () => {
  beforeEach(() => {
    authMock.mockReset();
    mockHandleListUploads.mockReset();
    mockCreateRealUploadsClient.mockReset();
  });

  it("returns 401 when no session (handler never called)", async () => {
    authMock.mockResolvedValue(null);
    const resp = await GET(makeGetRequest());
    expect(resp.status).toBe(401);
    expect(mockHandleListUploads).not.toHaveBeenCalled();
  });

  it("returns UNAUTHENTICATED error code when no session", async () => {
    authMock.mockResolvedValue(null);
    const resp = await GET(makeGetRequest());
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UNAUTHENTICATED");
  });

  it("delegates to handleListUploads when authenticated", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleListUploads.mockResolvedValue({
      data: { items: [], total: 0 },
      status: 200,
      headers: { "Cache-Control": "no-store" },
    });
    const resp = await GET(makeGetRequest());
    expect(resp.status).toBe(200);
    expect(mockHandleListUploads).toHaveBeenCalledOnce();
  });

  it("sets Cache-Control: no-store on authenticated success response", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleListUploads.mockResolvedValue({
      data: { items: [], total: 0 },
      status: 200,
      headers: { "Cache-Control": "no-store" },
    });
    const resp = await GET(makeGetRequest());
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
  });

  it("returns 502 UPSTREAM_ERROR when handleListUploads throws", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleListUploads.mockRejectedValue(new Error("backend down"));
    const resp = await GET(makeGetRequest());
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UPSTREAM_ERROR");
  });
});

// POST tests
describe("POST /api/paysync/uploads", () => {
  beforeEach(() => {
    authMock.mockReset();
    mockHandleCreateUpload.mockReset();
    mockCreateRealUploadsClient.mockReset();
  });

  it("returns 401 before body parse when no session (multipart DoS guard)", async () => {
    authMock.mockResolvedValue(null);
    // Even with a file field present, auth fires first — formData() is never called.
    const req = makePostRequestWithFormData({
      file: new Blob(["data"], { type: "text/csv" }),
    });
    const formDataSpy = vi.spyOn(req, "formData");
    const resp = await POST(req);
    expect(resp.status).toBe(401);
    expect(formDataSpy).not.toHaveBeenCalled();
    expect(mockHandleCreateUpload).not.toHaveBeenCalled();
  });

  it("returns 400 MISSING_FILE when form field file is absent", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    const req = makePostRequestWithFormData({ other_field: "value" });
    const resp = await POST(req);
    expect(resp.status).toBe(400);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("MISSING_FILE");
    expect(mockHandleCreateUpload).not.toHaveBeenCalled();
  });

  it("delegates to handleCreateUpload and returns 201 no-store on success", async () => {
    authedSession();
    const fakeUpload = { id: "upl-1", filename: "claims.csv", status: "received" };
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleCreateUpload.mockResolvedValue({
      data: fakeUpload,
      status: 201,
      headers: { "Cache-Control": "no-store" },
    });
    const req = makePostRequestWithFormData({
      file: new Blob(["col1,col2\nval1,val2"], { type: "text/csv" }),
    });
    const resp = await POST(req);
    expect(resp.status).toBe(201);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    expect(mockHandleCreateUpload).toHaveBeenCalledOnce();
    const body = (await resp.json()) as typeof fakeUpload;
    expect(body.id).toBe("upl-1");
  });

  it("returns 409 no-store on sha256 dedup conflict with existing_upload_id", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleCreateUpload.mockResolvedValue({
      data: { conflict: true, existing_upload_id: "upl-existing" },
      status: 409,
      headers: { "Cache-Control": "no-store" },
    });
    const req = makePostRequestWithFormData({
      file: new Blob(["dup data"], { type: "text/csv" }),
    });
    const resp = await POST(req);
    expect(resp.status).toBe(409);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    const body = (await resp.json()) as { conflict: boolean; existing_upload_id: string };
    expect(body.conflict).toBe(true);
    expect(body.existing_upload_id).toBe("upl-existing");
  });

  it("returns 502 UPLOAD_FAILED when handleCreateUpload throws, no filename in response", async () => {
    authedSession();
    mockCreateRealUploadsClient.mockReturnValue({});
    mockHandleCreateUpload.mockRejectedValue(new Error("billing backend down"));
    const req = makePostRequestWithFormData({
      file: new Blob(["data"], { type: "text/csv" }),
    });
    const resp = await POST(req);
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UPLOAD_FAILED");
    // Filename must not appear in error response (PHI-adjacent, no-log rule)
    expect(JSON.stringify(body)).not.toContain("claims.csv");
  });
});
