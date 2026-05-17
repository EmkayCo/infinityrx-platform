// packages/contract/src/__tests__/paysync.test.ts
// Plan A gate: paysync contract factories instantiable, schemas validate.
// Plan B additions: CyclesClient + Cycle schema tests.

import { describe, expect, it } from "vitest";
import {
  createMockCyclesClient,
  createMockInboxClient,
  createMockUploadsClient,
  createRealCyclesClient,
  createRealInboxClient,
  createRealUploadsClient,
  CycleSchema,
  CycleStatusSchema,
  InboxItemSchema,
  PAYSYNC_CYCLES_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  RbacRoleSchema,
  UploadListRequestSchema,
  UploadSchema,
} from "../index.js";

describe("paysync contract — mock factories", () => {
  it("createMockUploadsClient instantiates with the expected shape", async () => {
    const c = createMockUploadsClient();
    expect(c.name).toBe("paysync.uploads");
    expect(c.cachePolicies).toBe(PAYSYNC_UPLOADS_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockUploadsClient.list returns a typed empty page", async () => {
    const c = createMockUploadsClient();
    const page = await c.list({ limit: 50 });
    expect(page.results).toEqual([]);
    expect(page.total).toBe(0);
  });

  it("createMockUploadsClient.get returns null for unknown id", async () => {
    const c = createMockUploadsClient();
    const u = await c.get("not-a-real-id");
    expect(u).toBeNull();
  });

  it("createMockUploadsClient.create returns a typed synthetic Upload", async () => {
    const c = createMockUploadsClient();
    const u = await c.create({ filename: "sample.csv", content: new Blob(["a"]) });
    expect(u.filename).toBe("sample.csv");
    expect(u.status).toBe("received");
    // schema parse confirms the synthetic value matches the public shape
    expect(() => UploadSchema.parse(u)).not.toThrow();
  });

  it("createMockInboxClient instantiates with the expected shape", async () => {
    const c = createMockInboxClient();
    expect(c.name).toBe("paysync.inbox");
    expect(c.cachePolicies).toBe(PAYSYNC_INBOX_CACHE_POLICIES);
    const list = await c.list("operator");
    expect(list).toEqual([]);
  });
});

describe("paysync contract — real factories (HTTP wired in Plan B)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealUploadsClient attaches Bearer + correlation header on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as URL).href ?? (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealUploadsClient({ baseUrl: "http://x.test", getAuthToken: async () => "tok-u", fetch: fakeFetch });
    await c.list({ limit: 10 });
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-u");
    expect(captured[0]?.url).toContain("/api/v1/billing/uploads");
  });

  it("createRealUploadsClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealUploadsClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });

  it("createRealInboxClient attaches Bearer header on list", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse([]);
    };
    const c = createRealInboxClient({ baseUrl: "http://x.test", getAuthToken: async () => "tok-i", fetch: fakeFetch });
    await c.list("operator");
    expect(captured[0]?.get("authorization")).toBe("Bearer tok-i");
  });

  it("createRealCyclesClient attaches Bearer header on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as URL).href ?? (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealCyclesClient({ baseUrl: "http://x.test", getAuthToken: async () => "tok-c", fetch: fakeFetch });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-c");
    expect(captured[0]?.url).toContain("/api/v1/billing/cycles");
  });

  it("createRealUploadsClient.create throws with details.existing_upload_id on 409 DUPLICATE_UPLOAD", async () => {
    // B9: PaysyncClientError must carry error.details so the BFF can recover existing_upload_id
    const existingId = "ffffffff-ffff-ffff-ffff-ffffffffffff";
    const fakeFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "DUPLICATE_UPLOAD",
            message: "File already uploaded",
            correlation_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
            details: { existing_upload_id: existingId },
          },
        }),
        { status: 409, headers: { "content-type": "application/json" } },
      );
    const c = createRealUploadsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "t",
      getTenantId: async () => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      fetch: fakeFetch,
    });
    let caught: unknown;
    try {
      await c.create({ filename: "dup.csv", content: new Blob(["a"]) });
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeDefined();
    expect((caught as { code?: string }).code).toBe("DUPLICATE_UPLOAD");
    // details must be present so BFF can recover existing_upload_id
    expect((caught as { details?: { existing_upload_id?: string } }).details?.existing_upload_id).toBe(existingId);
  });

  it("createRealCyclesClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealCyclesClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });

  // B3: every paysync real client must send X-Tenant-Id on every request
  it("createRealUploadsClient sends X-Tenant-Id header on list when getTenantId provided", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealUploadsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      getTenantId: async () => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      fetch: fakeFetch,
    });
    await c.list({ limit: 10 });
    expect(captured[0]?.get("x-tenant-id")).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
  });

  it("createRealUploadsClient sends X-Tenant-Id header on get", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse({ id: "11111111-1111-1111-1111-111111111111", tenant_id: "22222222-2222-2222-2222-222222222222", filename: "f.csv", content_sha256: "a".repeat(64), status: "validated", total_billed_amount: null, claim_count: 0, row_error_count: 0, uploaded_by_user_id: "33333333-3333-3333-3333-333333333333", uploaded_at: new Date().toISOString() });
    };
    const c = createRealUploadsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      getTenantId: async () => "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      fetch: fakeFetch,
    });
    await c.get("some-id");
    expect(captured[0]?.get("x-tenant-id")).toBe("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
  });

  it("createRealInboxClient sends X-Tenant-Id header on list", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse([]);
    };
    const c = createRealInboxClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      getTenantId: async () => "cccccccc-cccc-cccc-cccc-cccccccccccc",
      fetch: fakeFetch,
    });
    await c.list("operator");
    expect(captured[0]?.get("x-tenant-id")).toBe("cccccccc-cccc-cccc-cccc-cccccccccccc");
  });

  it("createRealCyclesClient sends X-Tenant-Id header on list", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealCyclesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      getTenantId: async () => "dddddddd-dddd-dddd-dddd-dddddddddddd",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.get("x-tenant-id")).toBe("dddddddd-dddd-dddd-dddd-dddddddddddd");
  });

  it("createRealCyclesClient sends X-Tenant-Id header on close", async () => {
    const captured: Headers[] = [];
    const fakeFetch: typeof fetch = async (_input, init) => {
      captured.push(new Headers(init?.headers));
      return jsonResponse({ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", tenant_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", period_label: "2026-05", status: "closed", window_closed_at: null, origin_upload_id: null, total_billed_amount: null, claim_count: 0, created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
    };
    const c = createRealCyclesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      getTenantId: async () => "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      fetch: fakeFetch,
    });
    await c.close("id1");
    expect(captured[0]?.get("x-tenant-id")).toBe("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee");
  });
});

describe("paysync contract — cycles mock factory", () => {
  it("createMockCyclesClient instantiates with expected shape", async () => {
    const c = createMockCyclesClient();
    expect(c.name).toBe("paysync.cycles");
    expect(c.cachePolicies).toBe(PAYSYNC_CYCLES_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockCyclesClient.list returns 5 fixture cycles", async () => {
    const c = createMockCyclesClient();
    const page = await c.list({});
    expect(page.results).toHaveLength(5);
    expect(page.total).toBe(5);
  });

  it("createMockCyclesClient.list filters by status", async () => {
    const c = createMockCyclesClient();
    const page = await c.list({ status: "open" });
    expect(page.results.every((cy) => cy.status === "open")).toBe(true);
  });

  it("createMockCyclesClient.list respects limit", async () => {
    const c = createMockCyclesClient();
    const page = await c.list({ limit: 2 });
    expect(page.results.length).toBeLessThanOrEqual(2);
  });

  it("createMockCyclesClient.get returns cycle by id", async () => {
    const c = createMockCyclesClient();
    const all = await c.list({});
    const first = all.results[0]!;
    const found = await c.get(first.id);
    expect(found?.id).toBe(first.id);
  });

  it("createMockCyclesClient.get returns null for unknown id", async () => {
    const c = createMockCyclesClient();
    expect(await c.get("00000000-0000-0000-0000-000000000000")).toBeNull();
  });

  it("createMockCyclesClient.close transitions status to closed", async () => {
    const c = createMockCyclesClient();
    // pick a cycle that is in "closing" state to close
    const all = await c.list({ status: "closing" });
    const closing = all.results[0];
    if (closing) {
      const closed = await c.close(closing.id);
      expect(closed.status).toBe("closed");
    }
    // ensure the fixture has at least one closable cycle — guard
    expect(closing ?? "no-closing-cycle-in-fixture").not.toBe("no-closing-cycle-in-fixture");
  });

  it("PAYSYNC_CYCLES_CACHE_POLICIES has list, get, close operations", () => {
    expect(PAYSYNC_CYCLES_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_CYCLES_CACHE_POLICIES).toHaveProperty("get");
    expect(PAYSYNC_CYCLES_CACHE_POLICIES).toHaveProperty("close");
  });
});

describe("paysync contract — schemas", () => {
  it("RbacRoleSchema accepts the three valid roles", () => {
    for (const role of ["operator", "approver", "auditor"] as const) {
      expect(RbacRoleSchema.parse(role)).toBe(role);
    }
    expect(() => RbacRoleSchema.parse("admin")).toThrow();
  });

  it("UploadListRequestSchema applies default limit=50", () => {
    const parsed = UploadListRequestSchema.parse({});
    expect(parsed.limit).toBe(50);
  });

  it("UploadSchema validates a well-formed Upload", () => {
    const sample = {
      id: "11111111-1111-1111-1111-111111111111",
      tenant_id: "22222222-2222-2222-2222-222222222222",
      filename: "claims-batch.csv",
      content_sha256: "a".repeat(64),
      status: "validated",
      total_billed_amount: "12345.67",
      claim_count: 100,
      row_error_count: 0,
      uploaded_by_user_id: "33333333-3333-3333-3333-333333333333",
      uploaded_at: "2026-05-16T19:30:00.000+00:00",
    };
    expect(() => UploadSchema.parse(sample)).not.toThrow();
  });

  it("UploadSchema rejects a non-hex content_sha256", () => {
    const bad = {
      id: "11111111-1111-1111-1111-111111111111",
      tenant_id: "22222222-2222-2222-2222-222222222222",
      filename: "x.csv",
      content_sha256: "not-a-sha",
      status: "received" as const,
      total_billed_amount: null,
      claim_count: 0,
      row_error_count: 0,
      uploaded_by_user_id: "33333333-3333-3333-3333-333333333333",
      uploaded_at: "2026-05-16T19:30:00.000+00:00",
    };
    expect(() => UploadSchema.parse(bad)).toThrow();
  });

  it("InboxItemSchema validates a payload-bearing item", () => {
    expect(() => InboxItemSchema.parse({
      id: "i-1",
      kind: "upload_pending_review",
      tenant_id: "t-1",
      upload_id: null,
      rbac_required: "operator",
      created_at: "2026-05-16T19:30:00.000+00:00",
      priority: "normal",
      payload: { foo: 1 },
    })).not.toThrow();
  });

  it("CycleStatusSchema accepts all four valid statuses", () => {
    for (const s of ["open", "closing", "closed", "error"] as const) {
      expect(CycleStatusSchema.parse(s)).toBe(s);
    }
    expect(() => CycleStatusSchema.parse("unknown")).toThrow();
  });

  it("CycleSchema validates a well-formed open cycle", () => {
    expect(() => CycleSchema.parse({
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      tenant_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      period_label: "2026-05",
      status: "open",
      window_closed_at: null,
      origin_upload_id: null,
      total_billed_amount: null,
      claim_count: 0,
      created_at: "2026-05-01T00:00:00.000+00:00",
      updated_at: "2026-05-16T19:30:00.000+00:00",
    })).not.toThrow();
  });

  it("CycleSchema validates a well-formed closed cycle with amounts", () => {
    expect(() => CycleSchema.parse({
      id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
      tenant_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      period_label: "2026-04",
      status: "closed",
      window_closed_at: "2026-04-30T23:59:59.000+00:00",
      origin_upload_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
      total_billed_amount: "98765.4321",
      claim_count: 500,
      created_at: "2026-04-01T00:00:00.000+00:00",
      updated_at: "2026-04-30T23:59:59.000+00:00",
    })).not.toThrow();
  });

  it("CycleSchema rejects a period_label that is empty", () => {
    expect(() => CycleSchema.parse({
      id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
      tenant_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      period_label: "",
      status: "open",
      window_closed_at: null,
      origin_upload_id: null,
      total_billed_amount: null,
      claim_count: 0,
      created_at: "2026-05-01T00:00:00.000+00:00",
      updated_at: "2026-05-16T19:30:00.000+00:00",
    })).toThrow();
  });
});
