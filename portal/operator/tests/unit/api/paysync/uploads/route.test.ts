/**
 * Unit tests for GET + POST /api/paysync/uploads route handler.
 *
 * Security-sensitive paths per CLAUDE.md INVARIANTS:
 *   - Auth-before-body: unauthenticated -> 401 BEFORE body is touched
 *   - Cache-Control: no-store on all authenticated responses (PHI-adjacent)
 *   - No PHI in error responses: filename/file size never echoed back
 *
 * POST streaming passthrough design:
 *   The route forwards request.body (ReadableStream) directly to billing via
 *   fetch with duplex:"half". It does NOT call request.formData() -- no
 *   buffering, no Next.js body-size cap. globalThis.fetch is mocked to
 *   intercept the billing call and assert headers + body are forwarded.
 *
 * Test matrix:
 *   GET  -- unauthenticated -> 401, handler not called
 *   GET  -- authenticated   -> delegates to handleListUploads, no-store header
 *   GET  -- handler throws  -> 502 UPSTREAM_ERROR
 *   POST -- unauthenticated -> 401 BEFORE body is touched (multipart DoS guard)
 *   POST -- wrong content-type -> 400 INVALID_BODY, fetch not called
 *   POST -- valid stream -> 201 no-store, fetch called with duplex:"half"
 *   POST -- billing 409 dedup -> 409 no-store forwarded verbatim
 *   POST -- fetch throws (network) -> 502 UPLOAD_FAILED, no PHI in response
 *   POST -- billing returns non-JSON -> 502 UPLOAD_FAILED
 *   POST -- billing 422 validation failure -> 422 forwarded verbatim
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { NextRequest } from "next/server";

// hoist mocks before any imports
const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

const { mockHandleListUploads } = vi.hoisted(() => ({
  mockHandleListUploads: vi.fn(),
}));
vi.mock("@infinityrx/module-paysync/bff", () => ({
  handleListUploads: mockHandleListUploads,
  handleCreateUpload: vi.fn(),
  handleGetUpload: vi.fn(),
  handleGetUploadClaims: vi.fn(),
}));

const { mockCreateRealUploadsClient } = vi.hoisted(() => ({
  mockCreateRealUploadsClient: vi.fn(),
}));
vi.mock("@infinityrx/contract", () => ({
  createRealUploadsClient: mockCreateRealUploadsClient,
}));

import { GET, POST, runtime } from "@/app/api/paysync/uploads/route";

// ── helpers ──────────────────────────────────────────────────────────────────

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
 * Build a NextRequest for POST with a streaming body.
 * The route reads request.body (ReadableStream) directly -- it never calls
 * request.formData(). A ReadableStream body is set so request.body is non-null.
 */
function makeStreamingPostRequest(
  contentType = "multipart/form-data; boundary=----boundary123",
  bodyData: Uint8Array | null = new TextEncoder().encode("--boundary\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\nCSV data\r\n--boundary--"),
) {
  const bodyStream = bodyData
    ? new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(bodyData);
          controller.close();
        },
      })
    : undefined;

  return new NextRequest("http://localhost:3000/api/paysync/uploads", {
    method: "POST",
    headers: { "content-type": contentType },
    body: bodyStream,
    // @ts-expect-error -- duplex needed for Node fetch with streaming body
    duplex: "half",
  });
}

/** Mock globalThis.fetch to return a fake billing response. */
function mockBillingFetch(status: number, body: unknown) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

// Save and restore globalThis.fetch around each test
let savedFetch: typeof globalThis.fetch;
beforeEach(() => { savedFetch = globalThis.fetch; });
afterEach(() => { globalThis.fetch = savedFetch; });

// ── GET tests ─────────────────────────────────────────────────────────────────

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

// ── POST streaming passthrough tests ─────────────────────────────────────────

describe("POST /api/paysync/uploads (streaming passthrough)", () => {
  beforeEach(() => {
    authMock.mockReset();
    mockCreateRealUploadsClient.mockReset();
  });

  it("returns 401 before body is touched when no session (multipart DoS guard)", async () => {
    authMock.mockResolvedValue(null);
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;
    const req = makeStreamingPostRequest();
    const resp = await POST(req);
    expect(resp.status).toBe(401);
    // fetch must never be called -- body must be untouched before auth resolves
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns 400 INVALID_BODY when content-type is not multipart/form-data", async () => {
    authedSession();
    const fetchSpy = vi.fn();
    globalThis.fetch = fetchSpy;
    const req = makeStreamingPostRequest("application/json");
    const resp = await POST(req);
    expect(resp.status).toBe(400);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("INVALID_BODY");
    // fetch must not be called -- content-type guard fires before streaming
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("forwards request.body to billing with duplex:half and correct auth headers", async () => {
    authedSession();
    const fakeUpload = { id: "upl-stream-1", filename: "claims.csv", status: "received" };
    mockBillingFetch(201, fakeUpload);

    const req = makeStreamingPostRequest();
    const resp = await POST(req);

    expect(resp.status).toBe(201);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    const body = (await resp.json()) as typeof fakeUpload;
    expect(body.id).toBe("upl-stream-1");

    // Verify billing was called with streaming options
    type FetchCall = [string, RequestInit & { duplex?: string }];
    const [url, init] = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as FetchCall;
    expect(url).toContain("/api/v1/billing/uploads");
    expect(init.method).toBe("POST");
    const hdrs = init.headers as Record<string, string>;
    expect(hdrs["content-type"]).toContain("multipart/form-data");
    expect(hdrs["Authorization"]).toMatch(/^Bearer /);
    expect(hdrs["x-tenant-id"]).toBe("tenant-alpha");
    // duplex:"half" is the key that enables streaming without buffering
    expect(init.duplex).toBe("half");
    // body is the ReadableStream from request.body -- not a Blob or Buffer
    expect(init.body).toBeInstanceOf(ReadableStream);
  });

  it("forwards billing 409 dedup conflict verbatim with no-store", async () => {
    authedSession();
    mockBillingFetch(409, {
      error: {
        code: "DUPLICATE_UPLOAD",
        message: "File already uploaded",
        correlation_id: "corr-123",
        details: { existing_upload_id: "upl-existing" },
      },
    });

    const req = makeStreamingPostRequest();
    const resp = await POST(req);
    expect(resp.status).toBe(409);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    const body = (await resp.json()) as { error: { details: { existing_upload_id: string } } };
    expect(body.error.details.existing_upload_id).toBe("upl-existing");
  });

  it("returns 502 UPLOAD_FAILED when billing fetch throws (network/ECONNREFUSED)", async () => {
    authedSession();
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("ECONNREFUSED"));

    const req = makeStreamingPostRequest();
    const resp = await POST(req);
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string; message: string } };
    expect(body.error.code).toBe("UPLOAD_FAILED");
    // No filename or body content in error response (PHI-adjacent no-log rule)
    expect(JSON.stringify(body)).not.toContain("claims.csv");
    expect(JSON.stringify(body)).not.toContain("ECONNREFUSED");
  });

  it("returns 502 UPLOAD_FAILED when billing returns non-JSON body", async () => {
    authedSession();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new SyntaxError("Unexpected token")),
    } as unknown as Response);

    const req = makeStreamingPostRequest();
    const resp = await POST(req);
    expect(resp.status).toBe(502);
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("UPLOAD_FAILED");
  });

  it("forwards billing 422 validation failure verbatim with no-store", async () => {
    authedSession();
    mockBillingFetch(422, {
      error: {
        code: "VALIDATION_FAILED",
        message: "File failed validation -- all rows rejected.",
        correlation_id: "corr-422",
        details: { row_error_count: 5, row_errors: [] },
      },
    });

    const req = makeStreamingPostRequest();
    const resp = await POST(req);
    expect(resp.status).toBe(422);
    expect(resp.headers.get("Cache-Control")).toBe("no-store");
    const body = (await resp.json()) as { error: { code: string } };
    expect(body.error.code).toBe("VALIDATION_FAILED");
  });
});

// ── Route metadata ────────────────────────────────────────────────────────────

describe("route runtime export (Edge-deployment guard)", () => {
  it('exports runtime = "nodejs"', () => {
    expect(runtime).toBe("nodejs");
  });
});
