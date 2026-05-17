// packages/contract/src/impls/paysync/mock.ts
// In-memory implementations of UploadsClient + InboxClient. Usable for dev,
// Storybook, and tests. Returns typed empty arrays for list endpoints in
// Plan A; Plan E populates real synthetic fixtures.

import { PAYSYNC_INBOX_CACHE_POLICIES, PAYSYNC_UPLOADS_CACHE_POLICIES, type InboxClient, type UploadsClient } from "./client.js";
import type { InboxItem, RbacRole, Upload, UploadListRequest, UploadListResponse } from "./types.js";

const MOCK_UPLOADS: ReadonlyArray<Upload> = [];

export function createMockUploadsClient(): UploadsClient {
  return {
    name: "paysync.uploads" as const,
    cachePolicies: PAYSYNC_UPLOADS_CACHE_POLICIES,

    async list(req: UploadListRequest): Promise<UploadListResponse> {
      const filtered = req.status === undefined
        ? MOCK_UPLOADS
        : MOCK_UPLOADS.filter((u) => u.status === req.status);
      const limit = req.limit ?? 50;
      return {
        results: filtered.slice(0, limit),
        total: filtered.length,
      };
    },

    async get(id: string): Promise<Upload | null> {
      return MOCK_UPLOADS.find((u) => u.id === id) ?? null;
    },

    async create(args: { readonly filename: string; readonly content: Blob | ReadableStream<Uint8Array> }): Promise<Upload> {
      // Deterministic mock — doesn't actually persist; returns a synthetic record
      // mirroring the input filename. Plan E replaces this with a fixture loader.
      void args.content; // ack the param so tsc doesn't complain
      const now = new Date().toISOString();
      return {
        id: "00000000-0000-0000-0000-000000000000",
        tenant_id: "00000000-0000-0000-0000-000000000000",
        filename: args.filename,
        content_sha256: "0".repeat(64),
        status: "received",
        total_billed_amount: null,
        claim_count: 0,
        row_error_count: 0,
        uploaded_by_user_id: "00000000-0000-0000-0000-000000000000",
        uploaded_at: now,
      };
    },

    async getClaims(_uploadId: string, _opts?: { readonly limit?: number; readonly cursor?: string }): Promise<{ results: Array<Record<string, unknown>>; next_cursor?: string; total: number }> {
      return { results: [], total: 0 };
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

const MOCK_INBOX: ReadonlyArray<InboxItem> = [];

export function createMockInboxClient(): InboxClient {
  return {
    name: "paysync.inbox" as const,
    cachePolicies: PAYSYNC_INBOX_CACHE_POLICIES,

    async list(role: RbacRole): Promise<InboxItem[]> {
      return MOCK_INBOX.filter((item) => item.rbac_required === role);
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
