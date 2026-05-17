// packages/contract/src/__tests__/paysync.test.ts
// Plan A gate: paysync contract factories instantiable, schemas validate.
// Plan B additions: CyclesClient + Cycle schema tests.

import { describe, expect, it } from "vitest";
import {
  createMockBankSettlementsClient,
  createMockBatchesClient,
  createMockCarryoversClient,
  createMockCyclesClient,
  createMockFilesClient,
  createMockInboxClient,
  createMockInvoicesClient,
  createMockJournalClient,
  createMockPaymentRunsClient,
  createMockReconciliationsClient,
  createMockUploadsClient,
  createRealBankSettlementsClient,
  createRealBatchesClient,
  createRealCarryoversClient,
  createRealCyclesClient,
  createRealFilesClient,
  createRealInboxClient,
  createRealInvoicesClient,
  createRealJournalClient,
  createRealPaymentRunsClient,
  createRealReconciliationsClient,
  createRealUploadsClient,
  BankSettlementSchema,
  BankSettlementStatusSchema,
  BatchListResponseSchema,
  BatchSchema,
  BatchStatusSchema,
  CarryoverListResponseSchema,
  CarryoverSchema,
  CycleSchema,
  CycleStatusSchema,
  FileArtifactKindSchema,
  FileArtifactListResponseSchema,
  FileArtifactSchema,
  FileGenerateRequestSchema,
  HashChainVerifyResponseSchema,
  InboxItemSchema,
  InvoiceListResponseSchema,
  InvoiceSchema,
  InvoiceStatusSchema,
  JournalEntryListResponseSchema,
  JournalEntrySchema,
  PaymentRunSchema,
  PaymentRunStatusSchema,
  ReconciliationSchema,
  ReconciliationStatusSchema,
  PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES,
  PAYSYNC_BATCHES_CACHE_POLICIES,
  PAYSYNC_CARRYOVERS_CACHE_POLICIES,
  PAYSYNC_CYCLES_CACHE_POLICIES,
  PAYSYNC_FILES_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_INVOICES_CACHE_POLICIES,
  PAYSYNC_JOURNAL_CACHE_POLICIES,
  PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES,
  PAYSYNC_RECONCILIATIONS_CACHE_POLICIES,
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

  it("createRealUploadsClient.create sends full stream content when ReadableStream passed", async () => {
    // P2: ReadableStream must be consumed into Blob — not replaced with new Blob([]).
    const captured: { body: FormData | null }[] = [];
    const csvContent = "ndc,npi,claim_id\n12345678901,1234567890,CLM-1";
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(csvContent));
        controller.close();
      },
    });
    const fakeFetch: typeof fetch = async (_input, init) => {
      const body = init?.body instanceof FormData ? init.body : null;
      captured.push({ body });
      return new Response(JSON.stringify({
        id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        tenant_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        filename: "test.csv",
        content_sha256: "a".repeat(64),
        status: "parsing",
        claim_count: 0,
        row_error_count: 0,
        total_billed_amount: null,
        uploaded_by_user_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
        uploaded_at: new Date().toISOString(),
      }), { status: 201, headers: { "Content-Type": "application/json" } });
    };
    const c = createRealUploadsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok",
      fetch: fakeFetch,
    });
    await c.create({ filename: "test.csv", content: stream });
    expect(captured.length).toBe(1);
    const sentBlob = captured[0]?.body?.get("file") as File | Blob | null;
    expect(sentBlob).not.toBeNull();
    // The blob must contain the actual content, not be empty
    const text = await (sentBlob as Blob).text();
    expect(text).toBe(csvContent);
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


// ── Plan C additions: Batches, Invoices, PaymentRuns, Carryovers, BankSettlements, Reconciliations ──

describe("paysync contract — batches mock factory", () => {
  it("createMockBatchesClient instantiates with expected shape", async () => {
    const c = createMockBatchesClient();
    expect(c.name).toBe("paysync.batches");
    expect(c.cachePolicies).toBe(PAYSYNC_BATCHES_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockBatchesClient.list returns fixture batches", async () => {
    const c = createMockBatchesClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("createMockBatchesClient.get returns batch by id", async () => {
    const c = createMockBatchesClient();
    const all = await c.list({});
    const first = all.results[0]!;
    const found = await c.get(first.id);
    expect(found?.id).toBe(first.id);
  });

  it("createMockBatchesClient.get returns null for unknown id", async () => {
    const c = createMockBatchesClient();
    expect(await c.get("00000000-0000-0000-0000-000000000000")).toBeNull();
  });

  it("BatchSchema validates a well-formed batch", () => {
    expect(() => BatchSchema.parse({
      id: "b1000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      batch_number: "BATCH-2026-001",
      payment_route: "ach",
      total_amount: "12345.67",
      payment_count: 10,
      ap_count: 10,
      status: "generated",
      created_at: "2026-05-01T00:00:00.000+00:00",
      updated_at: "2026-05-01T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("BatchStatusSchema accepts all valid statuses", () => {
    for (const s of ["generated", "validated", "approved", "submitted", "settled", "void"] as const) {
      expect(BatchStatusSchema.parse(s)).toBe(s);
    }
    expect(() => BatchStatusSchema.parse("unknown")).toThrow();
  });

  it("PAYSYNC_BATCHES_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_BATCHES_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_BATCHES_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — batches real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealBatchesClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealBatchesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-b",
      getTenantId: async () => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-b");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    // B1: backend route is /payment-batches (router.py:504), not /batches
    expect(captured[0]?.url).toContain("/api/v1/billing/payment-batches");
  });

  it("createRealBatchesClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealBatchesClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });
});

describe("paysync contract — invoices mock factory", () => {
  it("createMockInvoicesClient instantiates with expected shape", async () => {
    const c = createMockInvoicesClient();
    expect(c.name).toBe("paysync.invoices");
    expect(c.cachePolicies).toBe(PAYSYNC_INVOICES_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockInvoicesClient.list returns fixture invoices", async () => {
    const c = createMockInvoicesClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("createMockInvoicesClient.get returns invoice by id", async () => {
    const c = createMockInvoicesClient();
    const all = await c.list({});
    const first = all.results[0]!;
    const found = await c.get(first.id);
    expect(found?.id).toBe(first.id);
  });

  it("InvoiceSchema validates a well-formed invoice", () => {
    expect(() => InvoiceSchema.parse({
      id: "11000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      invoice_number: "INV-2026-001",
      invoice_type: "client_billing",
      client_id: "c1000000-0000-0000-0000-000000000001",
      client_name: "Acme Corp",
      period_start: "2026-05-01",
      period_end: "2026-05-31",
      claims_subtotal: "10000.00",
      fees_subtotal: "500.00",
      adjustments: "0.00",
      late_fees: "0.00",
      total: "10500.00",
      paid_amount: "0.00",
      claim_count: 100,
      status: "draft",
      due_date: "2026-06-15",
      created_at: "2026-05-31T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("InvoiceStatusSchema accepts all valid statuses", () => {
    for (const s of ["draft", "approved", "sent", "paid", "void", "overdue"] as const) {
      expect(InvoiceStatusSchema.parse(s)).toBe(s);
    }
    expect(() => InvoiceStatusSchema.parse("unknown")).toThrow();
  });

  it("PAYSYNC_INVOICES_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_INVOICES_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_INVOICES_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — invoices real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealInvoicesClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealInvoicesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-i",
      getTenantId: async () => "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-i");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    expect(captured[0]?.url).toContain("/api/v1/billing/invoices");
  });

  it("createRealInvoicesClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealInvoicesClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });
});

describe("paysync contract — payment-runs mock factory", () => {
  it("createMockPaymentRunsClient instantiates with expected shape", async () => {
    const c = createMockPaymentRunsClient();
    expect(c.name).toBe("paysync.payment-runs");
    expect(c.cachePolicies).toBe(PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockPaymentRunsClient.list returns fixture payment runs", async () => {
    const c = createMockPaymentRunsClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("PaymentRunSchema validates a well-formed payment run", () => {
    expect(() => PaymentRunSchema.parse({
      id: "20000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      batch_id: "b1000000-0000-0000-0000-000000000001",
      status: "completed",
      total_amount: "12345.67",
      payment_count: 10,
      run_at: "2026-05-01T00:00:00.000+00:00",
      completed_at: "2026-05-01T00:01:00.000+00:00",
      created_at: "2026-05-01T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("PaymentRunStatusSchema accepts all valid statuses", () => {
    for (const s of ["pending", "running", "completed", "failed", "held"] as const) {
      expect(PaymentRunStatusSchema.parse(s)).toBe(s);
    }
    expect(() => PaymentRunStatusSchema.parse("unknown")).toThrow();
  });

  it("PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — payment-runs real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealPaymentRunsClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealPaymentRunsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-pr",
      getTenantId: async () => "cccccccc-cccc-cccc-cccc-cccccccccccc",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-pr");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("cccccccc-cccc-cccc-cccc-cccccccccccc");
    expect(captured[0]?.url).toContain("/api/v1/billing/payment-runs");
  });
});

describe("paysync contract — carryovers mock factory", () => {
  it("createMockCarryoversClient instantiates with expected shape", async () => {
    const c = createMockCarryoversClient();
    expect(c.name).toBe("paysync.carryovers");
    expect(c.cachePolicies).toBe(PAYSYNC_CARRYOVERS_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockCarryoversClient.list returns fixture carryovers", async () => {
    const c = createMockCarryoversClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("CarryoverSchema validates a well-formed AP-carryforward carryover (C4)", () => {
    expect(() => CarryoverSchema.parse({
      id: "d0000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      ap_record_id: "e0000000-0000-0000-0000-000000000001",
      amount: "250.00",
      reason: "vendor_hold",
      upload_id: "f0000000-0000-0000-0000-000000000001",
      resolved: false,
      resolved_at: null,
      resolved_by: null,
      created_at: "2026-05-01T00:00:00.000+00:00",
      updated_at: "2026-05-01T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("CarryoverSchema validates a resolved carryover with resolved_at + resolved_by (C4)", () => {
    expect(() => CarryoverSchema.parse({
      id: "d0000000-0000-0000-0000-000000000002",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      ap_record_id: "e0000000-0000-0000-0000-000000000002",
      amount: "125.50",
      reason: "partial_funding",
      upload_id: null,
      resolved: true,
      resolved_at: "2026-05-10T12:00:00.000+00:00",
      resolved_by: "00000000-0000-0000-0000-000000000099",
      created_at: "2026-04-01T00:00:00.000+00:00",
      updated_at: "2026-05-10T12:00:00.000+00:00",
    })).not.toThrow();
  });

  it("CarryoverSchema rejects old member-accumulator shape (C4: member_id is gone)", () => {
    expect(() => CarryoverSchema.parse({
      id: "d0000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      member_id: "e0000000-0000-0000-0000-000000000001",
      carried_amount: "250.00",
      original_amount: "500.00",
      reason: "deductible_carryover",
      from_period: "2026-04",
      to_period: "2026-05",
      created_at: "2026-05-01T00:00:00.000+00:00",
    })).toThrow();
  });

  it("PAYSYNC_CARRYOVERS_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_CARRYOVERS_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_CARRYOVERS_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — carryovers real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealCarryoversClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealCarryoversClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-co",
      getTenantId: async () => "dddddddd-dddd-dddd-dddd-dddddddddddd",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-co");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("dddddddd-dddd-dddd-dddd-dddddddddddd");
    expect(captured[0]?.url).toContain("/api/v1/billing/carryovers");
  });
});

describe("paysync contract — bank-settlements mock factory", () => {
  it("createMockBankSettlementsClient instantiates with expected shape", async () => {
    const c = createMockBankSettlementsClient();
    expect(c.name).toBe("paysync.bank-settlements");
    expect(c.cachePolicies).toBe(PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockBankSettlementsClient.list returns fixture settlements", async () => {
    const c = createMockBankSettlementsClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("BankSettlementSchema validates a well-formed settlement", () => {
    expect(() => BankSettlementSchema.parse({
      id: "f0000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      batch_id: "b1000000-0000-0000-0000-000000000001",
      bank_reference: "ACH-20260501-001",
      expected_amount: "12345.67",
      actual_amount: "12345.67",
      status: "matched",
      settlement_date: "2026-05-01",
      resolved_at: null,
      created_at: "2026-05-01T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("BankSettlementStatusSchema accepts all valid statuses", () => {
    for (const s of ["matched", "unmatched", "discrepancy", "resolved"] as const) {
      expect(BankSettlementStatusSchema.parse(s)).toBe(s);
    }
    expect(() => BankSettlementStatusSchema.parse("unknown")).toThrow();
  });

  it("PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — bank-settlements real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealBankSettlementsClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealBankSettlementsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-bs",
      getTenantId: async () => "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-bs");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee");
    expect(captured[0]?.url).toContain("/api/v1/billing/bank-settlements");
  });
});

describe("paysync contract — reconciliations mock factory", () => {
  it("createMockReconciliationsClient instantiates with expected shape", async () => {
    const c = createMockReconciliationsClient();
    expect(c.name).toBe("paysync.reconciliations");
    expect(c.cachePolicies).toBe(PAYSYNC_RECONCILIATIONS_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockReconciliationsClient.list returns fixture reconciliations", async () => {
    const c = createMockReconciliationsClient();
    const page = await c.list({});
    expect(page.results.length).toBeGreaterThan(0);
    expect(typeof page.total).toBe("number");
  });

  it("ReconciliationSchema validates a well-formed reconciliation", () => {
    expect(() => ReconciliationSchema.parse({
      id: "10000000-0000-0000-0000-000000000001",
      tenant_id: "a0000000-0000-0000-0000-000000000001",
      period_label: "2026-04",
      status: "complete",
      total_billed: "98765.43",
      total_paid: "98765.43",
      variance: "0.00",
      finalized_at: "2026-05-05T00:00:00.000+00:00",
      created_at: "2026-05-01T00:00:00.000+00:00",
      updated_at: "2026-05-05T00:00:00.000+00:00",
    })).not.toThrow();
  });

  it("ReconciliationStatusSchema accepts all valid statuses", () => {
    for (const s of ["pending", "in_progress", "complete", "failed"] as const) {
      expect(ReconciliationStatusSchema.parse(s)).toBe(s);
    }
    expect(() => ReconciliationStatusSchema.parse("unknown")).toThrow();
  });

  it("PAYSYNC_RECONCILIATIONS_CACHE_POLICIES has list and get operations", () => {
    expect(PAYSYNC_RECONCILIATIONS_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_RECONCILIATIONS_CACHE_POLICIES).toHaveProperty("get");
  });
});

describe("paysync contract — reconciliations real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("createRealReconciliationsClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const c = createRealReconciliationsClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-r",
      getTenantId: async () => "ffffffff-ffff-ffff-ffff-ffffffffffff",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-r");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("ffffffff-ffff-ffff-ffff-ffffffffffff");
    expect(captured[0]?.url).toContain("/api/v1/billing/reconciliations");
  });
});

// ── B4: bare-array OR envelope acceptance tests ──────────────────────────────
// The legacy billing backend returns bare T[] from /payment-batches, /invoices,
// and /carryovers. The union schemas must accept both shapes and normalise to
// the envelope so consumers always read .results and .total.

const BARE_BATCH = {
  id: "b1000000-0000-0000-0000-000000000001",
  tenant_id: "a0000000-0000-0000-0000-000000000001",
  batch_number: "BATCH-2026-001",
  payment_route: "ach",
  total_amount: "12345.67",
  payment_count: 10,
  ap_count: 10,
  status: "generated" as const,
  created_at: "2026-05-01T00:00:00.000+00:00",
  updated_at: "2026-05-01T00:00:00.000+00:00",
};

const BARE_INVOICE = {
  id: "11000000-0000-0000-0000-000000000001",
  tenant_id: "a0000000-0000-0000-0000-000000000001",
  invoice_number: "INV-2026-001",
  invoice_type: "client_billing",
  client_id: "c1000000-0000-0000-0000-000000000001",
  client_name: "Acme Corp",
  period_start: "2026-05-01",
  period_end: "2026-05-31",
  claims_subtotal: "10000.00",
  fees_subtotal: "500.00",
  adjustments: "0.00",
  late_fees: "0.00",
  total: "10500.00",
  paid_amount: "0.00",
  claim_count: 100,
  status: "draft" as const,
  due_date: "2026-06-15",
  created_at: "2026-05-31T00:00:00.000+00:00",
};

const BARE_CARRYOVER = {
  id: "d0000000-0000-0000-0000-000000000001",
  tenant_id: "a0000000-0000-0000-0000-000000000001",
  ap_record_id: "e0000000-0000-0000-0000-000000000001",
  amount: "250.00",
  reason: "vendor_hold",
  upload_id: null,
  resolved: false,
  resolved_at: null,
  resolved_by: null,
  created_at: "2026-05-01T00:00:00.000+00:00",
  updated_at: "2026-05-01T00:00:00.000+00:00",
};

describe("paysync contract — B4: BatchListResponseSchema bare-array + envelope", () => {
  it("parses a bare array and normalises to envelope", () => {
    const result = BatchListResponseSchema.parse([BARE_BATCH]);
    expect(result.results).toHaveLength(1);
    expect(result.results[0]?.id).toBe(BARE_BATCH.id);
    expect(result.total).toBe(1);
    expect(result.next_cursor).toBeNull();
  });

  it("parses an envelope response unchanged", () => {
    const result = BatchListResponseSchema.parse({ results: [BARE_BATCH], next_cursor: null, total: 1 });
    expect(result.results).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it(".results is accessible in both cases", () => {
    const fromArray = BatchListResponseSchema.parse([BARE_BATCH]);
    const fromEnvelope = BatchListResponseSchema.parse({ results: [BARE_BATCH], total: 1, next_cursor: null });
    expect(fromArray.results[0]?.batch_number).toBe("BATCH-2026-001");
    expect(fromEnvelope.results[0]?.batch_number).toBe("BATCH-2026-001");
  });
});

describe("paysync contract — B4: InvoiceListResponseSchema bare-array + envelope", () => {
  it("parses a bare array and normalises to envelope", () => {
    const result = InvoiceListResponseSchema.parse([BARE_INVOICE]);
    expect(result.results).toHaveLength(1);
    expect(result.results[0]?.id).toBe(BARE_INVOICE.id);
    expect(result.total).toBe(1);
    expect(result.next_cursor).toBeNull();
  });

  it("parses an envelope response unchanged", () => {
    const result = InvoiceListResponseSchema.parse({ results: [BARE_INVOICE], next_cursor: null, total: 1 });
    expect(result.results).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it(".results is accessible in both cases", () => {
    const fromArray = InvoiceListResponseSchema.parse([BARE_INVOICE]);
    const fromEnvelope = InvoiceListResponseSchema.parse({ results: [BARE_INVOICE], total: 1, next_cursor: null });
    expect(fromArray.results[0]?.invoice_number).toBe("INV-2026-001");
    expect(fromEnvelope.results[0]?.invoice_number).toBe("INV-2026-001");
  });
});

describe("paysync contract — B4+C4: CarryoverListResponseSchema bare-array + envelope", () => {
  it("parses a bare array and normalises to envelope", () => {
    const result = CarryoverListResponseSchema.parse([BARE_CARRYOVER]);
    expect(result.results).toHaveLength(1);
    expect(result.results[0]?.id).toBe(BARE_CARRYOVER.id);
    expect(result.total).toBe(1);
    expect(result.next_cursor).toBeNull();
  });

  it("parses an envelope response unchanged", () => {
    const result = CarryoverListResponseSchema.parse({ results: [BARE_CARRYOVER], next_cursor: null, total: 1 });
    expect(result.results).toHaveLength(1);
    expect(result.total).toBe(1);
  });

  it(".results is accessible in both cases", () => {
    const fromArray = CarryoverListResponseSchema.parse([BARE_CARRYOVER]);
    const fromEnvelope = CarryoverListResponseSchema.parse({ results: [BARE_CARRYOVER], total: 1, next_cursor: null });
    expect(fromArray.results[0]?.ap_record_id).toBe("e0000000-0000-0000-0000-000000000001");
    expect(fromEnvelope.results[0]?.ap_record_id).toBe("e0000000-0000-0000-0000-000000000001");
  });
});

// ── Plan D additions: FilesClient + JournalClient ────────────────────────────

describe("paysync contract — files mock factory", () => {
  it("createMockFilesClient instantiates with expected shape", async () => {
    const c = createMockFilesClient();
    expect(c.name).toBe("paysync.files");
    expect(c.cachePolicies).toBe(PAYSYNC_FILES_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockFilesClient.list returns empty page", async () => {
    const c = createMockFilesClient();
    const page = await c.list({});
    expect(page.results).toEqual([]);
    expect(page.total).toBe(0);
  });

  it("createMockFilesClient.get returns null for any id", async () => {
    const c = createMockFilesClient();
    expect(await c.get("00000000-0000-0000-0000-000000000000")).toBeNull();
  });

  it("createMockFilesClient.generate returns a synthetic FileArtifact", async () => {
    const c = createMockFilesClient();
    const artifact = await c.generate({ kind: "nacha", source_id: "11111111-1111-1111-1111-111111111111" });
    expect(artifact.kind).toBe("nacha");
    expect(artifact.source_batch_id).toBe("11111111-1111-1111-1111-111111111111");
    expect(() => FileArtifactSchema.parse(artifact)).not.toThrow();
  });

  it("createMockFilesClient.generate returns 835 for kind='835'", async () => {
    const c = createMockFilesClient();
    const artifact = await c.generate({ kind: "835", source_id: "22222222-2222-2222-2222-222222222222" });
    expect(artifact.kind).toBe("835");
  });

  it("createMockFilesClient.download returns an empty Blob", async () => {
    const c = createMockFilesClient();
    const blob = await c.download("any-id");
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBe(0);
  });

  it("PAYSYNC_FILES_CACHE_POLICIES has list, get, generate, download operations", () => {
    expect(PAYSYNC_FILES_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_FILES_CACHE_POLICIES).toHaveProperty("get");
    expect(PAYSYNC_FILES_CACHE_POLICIES).toHaveProperty("generate");
    expect(PAYSYNC_FILES_CACHE_POLICIES).toHaveProperty("download");
  });

  it("PAYSYNC_FILES_CACHE_POLICIES.generate has ttl_seconds=0 (no-cache mutation)", () => {
    expect(PAYSYNC_FILES_CACHE_POLICIES.generate?.ttl_seconds).toBe(0);
  });

  it("PAYSYNC_FILES_CACHE_POLICIES.download has ttl_seconds=0 (never cache binary)", () => {
    expect(PAYSYNC_FILES_CACHE_POLICIES.download?.ttl_seconds).toBe(0);
  });
});

describe("paysync contract — files real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  function makeArtifact(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      id: "a0000000-0000-0000-0000-000000000001",
      tenant_id: "b0000000-0000-0000-0000-000000000001",
      kind: "nacha",
      source_batch_id: "c0000000-0000-0000-0000-000000000001",
      source_payment_run_id: null,
      sha256: "a".repeat(64),
      file_size: 1024,
      generated_at: "2026-05-17T10:00:00.000+00:00",
      generated_by: "d0000000-0000-0000-0000-000000000001",
      upload_id: null,
      filename: "payment.nacha",
      status: "ready",
      ...overrides,
    };
  }

  it("createRealFilesClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse([]);
    };
    const c = createRealFilesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-f",
      getTenantId: async () => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-f");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(captured[0]?.url).toContain("/api/v1/billing/files");
  });

  it("createRealFilesClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealFilesClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });

  it("createRealFilesClient.generate POSTs to /files/generate with Bearer + X-Tenant-Id", async () => {
    const captured: { headers: Headers; url: string; method: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url, method: init?.method ?? "GET" });
      return jsonResponse(makeArtifact());
    };
    const c = createRealFilesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-gen",
      getTenantId: async () => "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      fetch: fakeFetch,
    });
    await c.generate({ kind: "nacha", source_id: "c0000000-0000-0000-0000-000000000001" });
    expect(captured[0]?.method).toBe("POST");
    expect(captured[0]?.url).toContain("/api/v1/billing/files/generate");
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-gen");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
  });

  it("createRealFilesClient.download GETs /files/{id}/download with Bearer + X-Tenant-Id", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return new Response(new Uint8Array([1, 2, 3]), { status: 200 });
    };
    const c = createRealFilesClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-dl",
      getTenantId: async () => "cccccccc-cccc-cccc-cccc-cccccccccccc",
      fetch: fakeFetch,
    });
    const blob = await c.download("file-id-123");
    expect(blob).toBeInstanceOf(Blob);
    expect(captured[0]?.url).toContain("/api/v1/billing/files/file-id-123/download");
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-dl");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("cccccccc-cccc-cccc-cccc-cccccccccccc");
  });

  it("createRealFilesClient 403 response surfaces PaysyncClientError with .details", async () => {
    const fakeFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "FORBIDDEN",
            message: "Only approvers can generate payment files",
            correlation_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
            details: { required_role: "approver" },
          },
        }),
        { status: 403, headers: { "content-type": "application/json" } },
      );
    const c = createRealFilesClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    let caught: unknown;
    try {
      await c.generate({ kind: "nacha", source_id: "c0000000-0000-0000-0000-000000000001" });
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeDefined();
    expect((caught as { code?: string }).code).toBe("FORBIDDEN");
    expect((caught as { details?: { required_role?: string } }).details?.required_role).toBe("approver");
  });
});

describe("paysync contract — journal mock factory", () => {
  it("createMockJournalClient instantiates with expected shape", async () => {
    const c = createMockJournalClient();
    expect(c.name).toBe("paysync.journal");
    expect(c.cachePolicies).toBe(PAYSYNC_JOURNAL_CACHE_POLICIES);
    const health = await c.probeHealth();
    expect(health.ok).toBe(true);
  });

  it("createMockJournalClient.list returns empty page", async () => {
    const c = createMockJournalClient();
    const page = await c.list({});
    expect(page.results).toEqual([]);
    expect(page.total).toBe(0);
  });

  it("createMockJournalClient.get returns null for any id", async () => {
    const c = createMockJournalClient();
    expect(await c.get("00000000-0000-0000-0000-000000000000")).toBeNull();
  });

  it("createMockJournalClient.verifyChain returns the schema-shaped response", async () => {
    const c = createMockJournalClient();
    const result = await c.verifyChain();
    expect(result.verified).toBe(true);
    expect(result.too_large).toBe(false);
    expect(result.job_id).toBeNull();
    expect(result.total_entries).toBe(0);
    expect(result.broken_at).toBeNull();
    expect(() => HashChainVerifyResponseSchema.parse(result)).not.toThrow();
  });

  it("PAYSYNC_JOURNAL_CACHE_POLICIES has list, get, verifyChain operations", () => {
    expect(PAYSYNC_JOURNAL_CACHE_POLICIES).toHaveProperty("list");
    expect(PAYSYNC_JOURNAL_CACHE_POLICIES).toHaveProperty("get");
    expect(PAYSYNC_JOURNAL_CACHE_POLICIES).toHaveProperty("verifyChain");
  });

  it("PAYSYNC_JOURNAL_CACHE_POLICIES.verifyChain has ttl_seconds=0 (never serve stale)", () => {
    expect(PAYSYNC_JOURNAL_CACHE_POLICIES.verifyChain?.ttl_seconds).toBe(0);
  });
});

describe("paysync contract — journal real client (HTTP)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  function makeEntry(overrides: Record<string, unknown> = {}): Record<string, unknown> {
    return {
      id: "e0000000-0000-0000-0000-000000000001",
      tenant_id: "f0000000-0000-0000-0000-000000000001",
      entry_date: "2026-05-17",
      entry_timestamp: "2026-05-17T10:00:00",
      entry_type: "payment",
      client_id: null,
      client_name: null,
      program_id: null,
      program_name: null,
      pay_to_entity_id: null,
      pay_to_entity_name: null,
      amount: "1234.56",
      category: "ap",
      gl_account_code: "2000",
      gl_class: null,
      reference_type: "payment_batch",
      reference_id: "b0000000-0000-0000-0000-000000000001",
      description: null,
      exported_to_accounting: false,
      exported_at: null,
      export_reference: null,
      created_at: "2026-05-17T10:00:00",
      entry_hash: "a".repeat(64),
      prev_hash: null,
      ...overrides,
    };
  }

  it("createRealJournalClient sends Bearer + X-Tenant-Id on list", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse([]);
    };
    const c = createRealJournalClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-j",
      getTenantId: async () => "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      fetch: fakeFetch,
    });
    await c.list({});
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-j");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    expect(captured[0]?.url).toContain("/api/v1/billing/journal");
  });

  it("createRealJournalClient.get returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const c = createRealJournalClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    expect(await c.get("missing-id")).toBeNull();
  });

  it("createRealJournalClient.verifyChain POSTs to /journal/verify-chain with Bearer + X-Tenant-Id", async () => {
    const captured: { headers: Headers; url: string; method: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url, method: init?.method ?? "GET" });
      return jsonResponse({ verified: true, too_large: false, job_id: null, total_entries: 5, broken_at: null });
    };
    const c = createRealJournalClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-vc",
      getTenantId: async () => "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      fetch: fakeFetch,
    });
    const result = await c.verifyChain();
    expect(captured[0]?.method).toBe("POST");
    expect(captured[0]?.url).toContain("/api/v1/billing/journal/verify-chain");
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-vc");
    expect(captured[0]?.headers.get("x-tenant-id")).toBe("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    expect(result.verified).toBe(true);
    expect(result.total_entries).toBe(5);
  });

  it("createRealJournalClient.verifyChain returns too_large=true when chain is oversized", async () => {
    const fakeFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({ verified: null, too_large: true, job_id: null, total_entries: 50000, broken_at: null }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    const c = createRealJournalClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    const result = await c.verifyChain();
    expect(result.verified).toBeNull();
    expect(result.too_large).toBe(true);
    expect(result.total_entries).toBe(50000);
    expect(() => HashChainVerifyResponseSchema.parse(result)).not.toThrow();
  });

  it("createRealJournalClient 409 response surfaces PaysyncClientError with .details", async () => {
    const fakeFetch: typeof fetch = async () =>
      new Response(
        JSON.stringify({
          error: {
            code: "CONFLICT",
            message: "Concurrent verification already running",
            correlation_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
            details: { running_job_id: "jjjjjjjj-jjjj-jjjj-jjjj-jjjjjjjjjjjj" },
          },
        }),
        { status: 409, headers: { "content-type": "application/json" } },
      );
    const c = createRealJournalClient({ baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch });
    let caught: unknown;
    try {
      await c.verifyChain();
    } catch (e) {
      caught = e;
    }
    expect(caught).toBeDefined();
    expect((caught as { code?: string }).code).toBe("CONFLICT");
    expect((caught as { details?: { running_job_id?: string } }).details?.running_job_id).toBeDefined();
  });
});

describe("paysync contract — schemas: FileArtifact + JournalEntry + HashChainVerifyResponse", () => {
  it("FileArtifactSchema validates a well-formed artifact", () => {
    expect(() => FileArtifactSchema.parse({
      id: "a0000000-0000-0000-0000-000000000001",
      tenant_id: "b0000000-0000-0000-0000-000000000001",
      kind: "nacha",
      source_batch_id: "c0000000-0000-0000-0000-000000000001",
      source_payment_run_id: null,
      sha256: "a".repeat(64),
      file_size: 2048,
      generated_at: "2026-05-17T10:00:00.000+00:00",
      generated_by: "d0000000-0000-0000-0000-000000000001",
      upload_id: null,
      filename: "payment.nacha",
      status: "ready",
    })).not.toThrow();
  });

  it("FileArtifactSchema rejects invalid sha256 (not hex)", () => {
    expect(() => FileArtifactSchema.parse({
      id: "a0000000-0000-0000-0000-000000000001",
      tenant_id: "b0000000-0000-0000-0000-000000000001",
      kind: "nacha",
      source_batch_id: null,
      source_payment_run_id: null,
      sha256: "not-a-sha256",
      file_size: 0,
      generated_at: null,
      generated_by: "d0000000-0000-0000-0000-000000000001",
      upload_id: null,
      filename: "x.nacha",
      status: "ready",
    })).toThrow();
  });

  it("FileArtifactKindSchema accepts all valid kinds", () => {
    for (const k of ["nacha", "835"] as const) {
      expect(FileArtifactKindSchema.parse(k)).toBe(k);
    }
    expect(() => FileArtifactKindSchema.parse("unknown")).toThrow();
    expect(() => FileArtifactKindSchema.parse("x12_835")).toThrow();
  });

  it("FileGenerateRequestSchema validates a well-formed generate request", () => {
    expect(() => FileGenerateRequestSchema.parse({ kind: "nacha", source_id: "a0000000-0000-0000-0000-000000000001" })).not.toThrow();
    expect(() => FileGenerateRequestSchema.parse({ kind: "835", source_id: "b0000000-0000-0000-0000-000000000001" })).not.toThrow();
  });

  it("FileArtifactListResponseSchema parses a bare array and normalises to envelope", () => {
    const artifact = {
      id: "a0000000-0000-0000-0000-000000000001",
      tenant_id: "b0000000-0000-0000-0000-000000000001",
      kind: "nacha",
      source_batch_id: null,
      source_payment_run_id: null,
      sha256: "b".repeat(64),
      file_size: 512,
      generated_at: "2026-05-17T10:00:00.000+00:00",
      generated_by: "d0000000-0000-0000-0000-000000000001",
      upload_id: null,
      filename: "out.nacha",
      status: "ready",
    };
    const result = FileArtifactListResponseSchema.parse([artifact]);
    expect(result.results).toHaveLength(1);
    expect(result.total).toBe(1);
    expect(result.next_cursor).toBeNull();
  });

  it("JournalEntrySchema validates a well-formed journal entry", () => {
    expect(() => JournalEntrySchema.parse({
      id: "e0000000-0000-0000-0000-000000000001",
      tenant_id: "f0000000-0000-0000-0000-000000000001",
      entry_date: "2026-05-17",
      entry_timestamp: "2026-05-17T10:00:00",
      entry_type: "payment",
      client_id: null,
      client_name: null,
      program_id: null,
      program_name: null,
      pay_to_entity_id: null,
      pay_to_entity_name: null,
      amount: "1234.56",
      category: "ap",
      gl_account_code: "2000",
      gl_class: null,
      reference_type: "payment_batch",
      reference_id: "b0000000-0000-0000-0000-000000000001",
      description: null,
      exported_to_accounting: false,
      exported_at: null,
      export_reference: null,
      created_at: "2026-05-17T10:00:00",
      entry_hash: "a".repeat(64),
      prev_hash: null,
    })).not.toThrow();
  });

  it("JournalEntryListResponseSchema parses a bare array and normalises to envelope", () => {
    const entry = {
      id: "e0000000-0000-0000-0000-000000000001",
      tenant_id: "f0000000-0000-0000-0000-000000000001",
      entry_date: null,
      entry_timestamp: null,
      entry_type: "fee",
      client_id: null,
      client_name: null,
      program_id: null,
      program_name: null,
      pay_to_entity_id: null,
      pay_to_entity_name: null,
      amount: "50.00",
      category: null,
      gl_account_code: null,
      gl_class: null,
      reference_type: null,
      reference_id: null,
      description: null,
      exported_to_accounting: null,
      exported_at: null,
      export_reference: null,
      created_at: null,
      entry_hash: null,
      prev_hash: null,
    };
    const result = JournalEntryListResponseSchema.parse([entry]);
    expect(result.results).toHaveLength(1);
    expect(result.total).toBe(1);
    expect(result.next_cursor).toBeNull();
  });

  it("HashChainVerifyResponseSchema validates verified=true response", () => {
    expect(() => HashChainVerifyResponseSchema.parse({
      verified: true,
      too_large: false,
      job_id: null,
      total_entries: 42,
      broken_at: null,
    })).not.toThrow();
  });

  it("HashChainVerifyResponseSchema validates too_large=true response with verified=null", () => {
    expect(() => HashChainVerifyResponseSchema.parse({
      verified: null,
      too_large: true,
      job_id: null,
      total_entries: 99999,
      broken_at: null,
    })).not.toThrow();
  });

  it("HashChainVerifyResponseSchema validates broken chain response", () => {
    const result = HashChainVerifyResponseSchema.parse({
      verified: false,
      too_large: false,
      job_id: null,
      total_entries: 100,
      broken_at: "e0000000-0000-0000-0000-000000000042",
    });
    expect(result.verified).toBe(false);
    expect(result.broken_at).toBe("e0000000-0000-0000-0000-000000000042");
  });
});
