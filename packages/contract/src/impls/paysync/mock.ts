// packages/contract/src/impls/paysync/mock.ts
// In-memory implementations of UploadsClient, InboxClient, and CyclesClient.
// Usable for dev, Storybook, and tests.
// Plan B populates real synthetic fixtures. Cycle data is inlined here
// (mirrors packages/modules/paysync/fixtures/seeds/cycles.json).

import {
  PAYSYNC_CYCLES_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  type CyclesClient,
  type InboxClient,
  type UploadsClient,
} from "./client.js";
import type {
  Cycle,
  CycleListResponse,
  CycleStatus,
  InboxItem,
  RbacRole,
  Upload,
  UploadListRequest,
  UploadListResponse,
} from "./types.js";

// ── Uploads mock ─────────────────────────────────────────────────────────

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
      // mirroring the input filename.
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

// ── Inbox mock ───────────────────────────────────────────────────────────

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

// ── Cycles mock ───────────────────────────────────────────────────────────
// Fixture data mirrors packages/modules/paysync/fixtures/seeds/cycles.json.
// 5 cycles: 2 open, 1 closing, 1 closed, 1 error.

const FIXTURE_CYCLES: Cycle[] = [
  {
    id: "c1000000-0000-0000-0000-000000000001",
    tenant_id: "t0000000-0000-0000-0000-000000000001",
    period_label: "2026-05",
    status: "open",
    window_closed_at: null,
    origin_upload_id: "u0000000-0000-0000-0000-000000000001",
    total_billed_amount: null,
    claim_count: 20,
    created_at: "2026-05-01T00:00:00.000+00:00",
    updated_at: "2026-05-16T00:00:00.000+00:00",
  },
  {
    id: "c1000000-0000-0000-0000-000000000002",
    tenant_id: "t0000000-0000-0000-0000-000000000001",
    period_label: "2026-04",
    status: "open",
    window_closed_at: null,
    origin_upload_id: "u0000000-0000-0000-0000-000000000002",
    total_billed_amount: null,
    claim_count: 30,
    created_at: "2026-04-01T00:00:00.000+00:00",
    updated_at: "2026-04-30T00:00:00.000+00:00",
  },
  {
    id: "c1000000-0000-0000-0000-000000000003",
    tenant_id: "t0000000-0000-0000-0000-000000000001",
    period_label: "2026-03",
    status: "closing",
    window_closed_at: "2026-03-31T23:59:59.000+00:00",
    origin_upload_id: "u0000000-0000-0000-0000-000000000003",
    total_billed_amount: "45678.9000",
    claim_count: 150,
    created_at: "2026-03-01T00:00:00.000+00:00",
    updated_at: "2026-03-31T23:59:59.000+00:00",
  },
  {
    id: "c1000000-0000-0000-0000-000000000004",
    tenant_id: "t0000000-0000-0000-0000-000000000001",
    period_label: "2026-02",
    status: "closed",
    window_closed_at: "2026-02-28T23:59:59.000+00:00",
    origin_upload_id: "u0000000-0000-0000-0000-000000000004",
    total_billed_amount: "98765.4321",
    claim_count: 500,
    created_at: "2026-02-01T00:00:00.000+00:00",
    updated_at: "2026-02-28T23:59:59.000+00:00",
  },
  {
    id: "c1000000-0000-0000-0000-000000000005",
    tenant_id: "t0000000-0000-0000-0000-000000000001",
    period_label: "2026-01",
    status: "error",
    window_closed_at: null,
    origin_upload_id: null,
    total_billed_amount: null,
    claim_count: 0,
    created_at: "2026-01-01T00:00:00.000+00:00",
    updated_at: "2026-01-15T00:00:00.000+00:00",
  },
];

export function createMockCyclesClient(): CyclesClient {
  // Mutable copy so .close() can mutate state within a test session.
  const cycles: Cycle[] = FIXTURE_CYCLES.map((c) => ({ ...c }));

  return {
    name: "paysync.cycles" as const,
    cachePolicies: PAYSYNC_CYCLES_CACHE_POLICIES,

    async list(req: { status?: CycleStatus; limit?: number; cursor?: string }): Promise<CycleListResponse> {
      const filtered = req.status === undefined
        ? cycles
        : cycles.filter((c) => c.status === req.status);
      const limit = req.limit ?? 50;
      return {
        results: filtered.slice(0, limit),
        total: filtered.length,
      };
    },

    async get(id: string): Promise<Cycle | null> {
      return cycles.find((c) => c.id === id) ?? null;
    },

    async close(id: string): Promise<Cycle> {
      const cycle = cycles.find((c) => c.id === id);
      if (!cycle) {
        throw new Error(`Cycle ${id} not found`);
      }
      cycle.status = "closed";
      cycle.updated_at = new Date().toISOString();
      return { ...cycle };
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
