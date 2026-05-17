// packages/contract/src/__tests__/paysync.test.ts
// Plan A gate: paysync contract factories instantiable, schemas validate.

import { describe, expect, it } from "vitest";
import {
  createMockInboxClient,
  createMockUploadsClient,
  createRealInboxClient,
  createRealUploadsClient,
  InboxItemSchema,
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

describe("paysync contract — real factories (signatures only, not yet wired)", () => {
  it("createRealUploadsClient returns a typed shape but throws on call", async () => {
    const c = createRealUploadsClient({ baseUrl: "http://localhost" });
    expect(c.name).toBe("paysync.uploads");
    await expect(c.get("x")).rejects.toThrow(/not wired/);
  });

  it("createRealInboxClient returns a typed shape but throws on call", async () => {
    const c = createRealInboxClient({ baseUrl: "http://localhost" });
    expect(c.name).toBe("paysync.inbox");
    await expect(c.list("operator")).rejects.toThrow(/not wired/);
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
});
