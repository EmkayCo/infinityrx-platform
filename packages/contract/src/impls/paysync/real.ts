// packages/contract/src/impls/paysync/real.ts
// HTTP-backed implementations of UploadsClient, InboxClient, and CyclesClient.
// Plan B wires the real HTTP calls (Plan A shipped typed-but-not-wired stubs).
// Pattern mirrors prescriber-directory/real.ts: authedFetch helper + zod unwrap.

import type { ClientConfig } from "../../client-base.js";
import { isErrorEnvelope } from "../../error-envelope.js";
import {
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
  type BankSettlementsClient,
  type BatchesClient,
  type CarryoversClient,
  type CyclesClient,
  type FilesClient,
  type InboxClient,
  type InvoicesClient,
  type JournalClient,
  type PaymentRunsClient,
  type ReconciliationsClient,
  type UploadsClient,
} from "./client.js";
import {
  BankSettlementListResponseSchema,
  BankSettlementSchema,
  BatchListResponseSchema,
  BatchSchema,
  CarryoverListResponseSchema,
  CarryoverSchema,
  CycleListResponseSchema,
  CycleSchema,
  FileArtifactListResponseSchema,
  FileArtifactSchema,
  HashChainVerifyResponseSchema,
  InvoiceListResponseSchema,
  InvoiceSchema,
  JournalEntryListResponseSchema,
  JournalEntrySchema,
  PaymentRunListResponseSchema,
  PaymentRunSchema,
  ReconciliationListResponseSchema,
  ReconciliationSchema,
  UploadListResponseSchema,
  UploadSchema,
  type Batch,
  type BankSettlement,
  type BankSettlementListResponse,
  type BankSettlementStatus,
  type BatchListResponse,
  type BatchStatus,
  type Carryover,
  type CarryoverListResponse,
  type Cycle,
  type CycleListResponse,
  type CycleStatus,
  type FileArtifact,
  type FileArtifactListResponse,
  type FileGenerateRequest,
  type HashChainVerifyResponse,
  type InboxItem,
  type Invoice,
  type InvoiceListResponse,
  type InvoiceStatus,
  type JournalEntry,
  type JournalEntryListResponse,
  type PaymentRun,
  type PaymentRunListResponse,
  type PaymentRunStatus,
  type RbacRole,
  type Reconciliation,
  type ReconciliationListResponse,
  type ReconciliationStatus,
  type Upload,
  type UploadListRequest,
  type UploadListResponse,
} from "./types.js";

class PaysyncClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly correlationId?: string,
    public readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "PaysyncClientError";
  }
}

function makeAuthedFetch(config: ClientConfig) {
  const baseUrl = (config.baseUrl ?? "").replace(/\/$/, "");
  const correlationHeader = config.correlationHeader ?? "x-correlation-id";
  const fetchImpl = config.fetch ?? globalThis.fetch;

  async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
    const token = await config.getAuthToken();
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    headers.set(correlationHeader, crypto.randomUUID());
    // B3: send X-Tenant-Id on every request so billing backend authz passes.
    if (config.getTenantId) {
      const tenantId = await config.getTenantId();
      headers.set("x-tenant-id", tenantId);
    }
    return fetchImpl(`${baseUrl}${path}`, { ...init, headers });
  }

  async function unwrap<T>(res: Response, schema: { parse(raw: unknown): T }): Promise<T> {
    const body = await res.json() as unknown;
    if (!res.ok) {
      if (isErrorEnvelope(body)) {
        throw new PaysyncClientError(body.error.code, body.error.message, body.error.correlation_id, body.error.details as Record<string, unknown> | undefined);
      }
      throw new Error(`Unexpected error shape: HTTP ${res.status}`);
    }
    return schema.parse(body);
  }

  async function probeHealth(fetchBase: typeof fetchImpl): Promise<{ ok: boolean; latency_ms: number; error?: string }> {
    const start = performance.now();
    try {
      const res = await fetchBase(`${baseUrl}/health`, { method: "GET" });
      const latency_ms = Math.round(performance.now() - start);
      return res.ok
        ? { ok: true as const, latency_ms }
        : { ok: false as const, latency_ms, error: `HTTP ${res.status}` };
    } catch (e) {
      return {
        ok: false as const,
        latency_ms: Math.round(performance.now() - start),
        error: (e as Error).message,
      };
    }
  }

  return { authedFetch, unwrap, probeHealth: () => probeHealth(fetchImpl) };
}

export function createRealUploadsClient(config: ClientConfig): UploadsClient {
  if (!config.baseUrl) {
    throw new Error("createRealUploadsClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.uploads" as const,
    cachePolicies: PAYSYNC_UPLOADS_CACHE_POLICIES,

    async list(req: UploadListRequest): Promise<UploadListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/uploads?${qs.toString()}`);
      return unwrap(res, UploadListResponseSchema);
    },

    async get(id: string): Promise<Upload | null> {
      const res = await authedFetch(`/api/v1/billing/uploads/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, UploadSchema);
    },

    async create(args: { readonly filename: string; readonly content: Blob | ReadableStream<Uint8Array> }): Promise<Upload> {
      const body = new FormData();
      // P2-stream: ReadableStream must be consumed into a Blob before FormData.
      // Passing a stream directly to new Blob([]) produces an empty Blob.
      let blob: Blob;
      if (args.content instanceof Blob) {
        blob = args.content;
      } else {
        const reader = args.content.getReader();
        const chunks: Uint8Array[] = [];
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          if (value) chunks.push(value);
        }
        blob = new Blob(chunks);
      }
      body.append("file", blob, args.filename);
      // multipart — do NOT set Content-Type (browser/fetch sets it with boundary)
      const token = await config.getAuthToken();
      const fetchImpl = config.fetch ?? globalThis.fetch;
      const baseUrl = (config.baseUrl ?? "").replace(/\/$/, "");
      const correlationHeader = config.correlationHeader ?? "x-correlation-id";
      const headers = new Headers();
      headers.set("Authorization", `Bearer ${token}`);
      headers.set(correlationHeader, crypto.randomUUID());
      // B3: send X-Tenant-Id on multipart path too
      if (config.getTenantId) {
        const tenantId = await config.getTenantId();
        headers.set("x-tenant-id", tenantId);
      }
      const res = await fetchImpl(`${baseUrl}/api/v1/billing/uploads`, {
        method: "POST",
        headers,
        body,
      });
      if (!res.ok) {
        const errBody = await res.json() as unknown;
        if (isErrorEnvelope(errBody)) {
          throw new PaysyncClientError(errBody.error.code, errBody.error.message, errBody.error.correlation_id, errBody.error.details as Record<string, unknown> | undefined);
        }
        throw new Error(`Upload create failed: HTTP ${res.status}`);
      }
      return UploadSchema.parse(await res.json());
    },

    async getClaims(uploadId: string, opts?: { readonly limit?: number; readonly cursor?: string }): Promise<{ results: Array<Record<string, unknown>>; next_cursor?: string; total: number }> {
      const qs = new URLSearchParams();
      if (opts?.limit) qs.set("limit", String(opts.limit));
      if (opts?.cursor) qs.set("cursor", opts.cursor);
      const res = await authedFetch(`/api/v1/billing/uploads/${encodeURIComponent(uploadId)}/claims?${qs.toString()}`);
      const body = await res.json() as { results: Array<Record<string, unknown>>; next_cursor?: string; total: number };
      return body;
    },

    probeHealth,
  };
}

export function createRealInboxClient(config: ClientConfig): InboxClient {
  if (!config.baseUrl) {
    throw new Error("createRealInboxClient: baseUrl is required");
  }
  const { authedFetch, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.inbox" as const,
    cachePolicies: PAYSYNC_INBOX_CACHE_POLICIES,

    async list(role: RbacRole): Promise<InboxItem[]> {
      const qs = new URLSearchParams({ role });
      const res = await authedFetch(`/api/v1/billing/inbox?${qs.toString()}`);
      if (!res.ok) {
        throw new Error(`Inbox list failed: HTTP ${res.status}`);
      }
      return (await res.json()) as InboxItem[];
    },

    probeHealth,
  };
}

export function createRealCyclesClient(config: ClientConfig): CyclesClient {
  if (!config.baseUrl) {
    throw new Error("createRealCyclesClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.cycles" as const,
    cachePolicies: PAYSYNC_CYCLES_CACHE_POLICIES,

    async list(req: { status?: CycleStatus; limit?: number; cursor?: string }): Promise<CycleListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/cycles?${qs.toString()}`);
      return unwrap(res, CycleListResponseSchema);
    },

    async get(id: string): Promise<Cycle | null> {
      const res = await authedFetch(`/api/v1/billing/cycles/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, CycleSchema);
    },

    async close(id: string): Promise<Cycle> {
      const res = await authedFetch(`/api/v1/billing/cycles/${encodeURIComponent(id)}/close`, {
        method: "POST",
      });
      return unwrap(res, CycleSchema);
    },

    probeHealth,
  };
}

export function createRealBatchesClient(config: ClientConfig): BatchesClient {
  if (!config.baseUrl) {
    throw new Error("createRealBatchesClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.batches" as const,
    cachePolicies: PAYSYNC_BATCHES_CACHE_POLICIES,

    async list(req: { status?: BatchStatus; limit?: number; cursor?: string }): Promise<BatchListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/payment-batches?${qs.toString()}`);
      return unwrap(res, BatchListResponseSchema);
    },

    async get(id: string): Promise<Batch | null> {
      const res = await authedFetch(`/api/v1/billing/payment-batches/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, BatchSchema);
    },

    probeHealth,
  };
}

export function createRealInvoicesClient(config: ClientConfig): InvoicesClient {
  if (!config.baseUrl) {
    throw new Error("createRealInvoicesClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.invoices" as const,
    cachePolicies: PAYSYNC_INVOICES_CACHE_POLICIES,

    async list(req: { status?: InvoiceStatus; client_id?: string; limit?: number; cursor?: string }): Promise<InvoiceListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      if (req.client_id) qs.set("client_id", req.client_id);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/invoices?${qs.toString()}`);
      return unwrap(res, InvoiceListResponseSchema);
    },

    async get(id: string): Promise<Invoice | null> {
      const res = await authedFetch(`/api/v1/billing/invoices/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, InvoiceSchema);
    },

    probeHealth,
  };
}

export function createRealPaymentRunsClient(config: ClientConfig): PaymentRunsClient {
  if (!config.baseUrl) {
    throw new Error("createRealPaymentRunsClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.payment-runs" as const,
    cachePolicies: PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES,

    async list(req: { status?: PaymentRunStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<PaymentRunListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      if (req.batch_id) qs.set("batch_id", req.batch_id);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/payment-runs?${qs.toString()}`);
      return unwrap(res, PaymentRunListResponseSchema);
    },

    async get(id: string): Promise<PaymentRun | null> {
      const res = await authedFetch(`/api/v1/billing/payment-runs/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, PaymentRunSchema);
    },

    probeHealth,
  };
}

export function createRealCarryoversClient(config: ClientConfig): CarryoversClient {
  if (!config.baseUrl) {
    throw new Error("createRealCarryoversClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.carryovers" as const,
    cachePolicies: PAYSYNC_CARRYOVERS_CACHE_POLICIES,

    async list(req: { member_id?: string; from_period?: string; limit?: number; cursor?: string }): Promise<CarryoverListResponse> {
      const qs = new URLSearchParams();
      if (req.member_id) qs.set("member_id", req.member_id);
      if (req.from_period) qs.set("from_period", req.from_period);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/carryovers?${qs.toString()}`);
      return unwrap(res, CarryoverListResponseSchema);
    },

    async get(id: string): Promise<Carryover | null> {
      const res = await authedFetch(`/api/v1/billing/carryovers/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, CarryoverSchema);
    },

    probeHealth,
  };
}

export function createRealBankSettlementsClient(config: ClientConfig): BankSettlementsClient {
  if (!config.baseUrl) {
    throw new Error("createRealBankSettlementsClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.bank-settlements" as const,
    cachePolicies: PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES,

    async list(req: { status?: BankSettlementStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<BankSettlementListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      if (req.batch_id) qs.set("batch_id", req.batch_id);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/bank-settlements?${qs.toString()}`);
      return unwrap(res, BankSettlementListResponseSchema);
    },

    async get(id: string): Promise<BankSettlement | null> {
      const res = await authedFetch(`/api/v1/billing/bank-settlements/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, BankSettlementSchema);
    },

    probeHealth,
  };
}

export function createRealReconciliationsClient(config: ClientConfig): ReconciliationsClient {
  if (!config.baseUrl) {
    throw new Error("createRealReconciliationsClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.reconciliations" as const,
    cachePolicies: PAYSYNC_RECONCILIATIONS_CACHE_POLICIES,

    async list(req: { status?: ReconciliationStatus; limit?: number; cursor?: string }): Promise<ReconciliationListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/reconciliations?${qs.toString()}`);
      return unwrap(res, ReconciliationListResponseSchema);
    },

    async get(id: string): Promise<Reconciliation | null> {
      const res = await authedFetch(`/api/v1/billing/reconciliations/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, ReconciliationSchema);
    },

    probeHealth,
  };
}

export function createRealFilesClient(config: ClientConfig): FilesClient {
  if (!config.baseUrl) {
    throw new Error("createRealFilesClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);
  const baseUrl = (config.baseUrl).replace(/\/$/, "");

  return {
    name: "paysync.files" as const,
    cachePolicies: PAYSYNC_FILES_CACHE_POLICIES,

    async list(req: { type?: string; limit?: number; cursor?: string }): Promise<FileArtifactListResponse> {
      const qs = new URLSearchParams();
      if (req.type) qs.set("kind", req.type);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/files?${qs.toString()}`);
      return unwrap(res, FileArtifactListResponseSchema);
    },

    async get(id: string): Promise<FileArtifact | null> {
      const res = await authedFetch(`/api/v1/billing/files/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, FileArtifactSchema);
    },

    async generate(input: FileGenerateRequest): Promise<FileArtifact> {
      const res = await authedFetch(`/api/v1/billing/files/generate`, {
        method: "POST",
        body: JSON.stringify(input),
      });
      return unwrap(res, FileArtifactSchema);
    },

    async download(id: string): Promise<Blob> {
      const token = await config.getAuthToken();
      const fetchImpl = config.fetch ?? globalThis.fetch;
      const correlationHeader = config.correlationHeader ?? "x-correlation-id";
      const headers = new Headers();
      headers.set("Authorization", `Bearer ${token}`);
      headers.set(correlationHeader, crypto.randomUUID());
      if (config.getTenantId) {
        const tenantId = await config.getTenantId();
        headers.set("x-tenant-id", tenantId);
      }
      const res = await fetchImpl(
        `${baseUrl}/api/v1/billing/files/${encodeURIComponent(id)}/download`,
        { headers },
      );
      if (!res.ok) {
        const errBody = await res.json().catch(() => null) as unknown;
        if (isErrorEnvelope(errBody)) {
          throw new PaysyncClientError(errBody.error.code, errBody.error.message, errBody.error.correlation_id, errBody.error.details as Record<string, unknown> | undefined);
        }
        throw new Error(`File download failed: HTTP ${res.status}`);
      }
      return res.blob();
    },

    probeHealth,
  };
}

export function createRealJournalClient(config: ClientConfig): JournalClient {
  if (!config.baseUrl) {
    throw new Error("createRealJournalClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.journal" as const,
    cachePolicies: PAYSYNC_JOURNAL_CACHE_POLICIES,

    async list(req: { limit?: number; cursor?: string }): Promise<JournalEntryListResponse> {
      const qs = new URLSearchParams();
      qs.set("limit", String(req.limit ?? 100));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/journal?${qs.toString()}`);
      return unwrap(res, JournalEntryListResponseSchema);
    },

    async get(id: string): Promise<JournalEntry | null> {
      const res = await authedFetch(`/api/v1/billing/journal/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, JournalEntrySchema);
    },

    async verifyChain(): Promise<HashChainVerifyResponse> {
      const res = await authedFetch(`/api/v1/billing/journal/verify-chain`, {
        method: "POST",
      });
      return unwrap(res, HashChainVerifyResponseSchema);
    },

    probeHealth,
  };
}
