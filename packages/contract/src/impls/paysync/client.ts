// packages/contract/src/impls/paysync/client.ts
// UploadsClient + InboxClient + CyclesClient interfaces + cache policies.
// Plan A R3 fix: singular client.ts holds all interfaces in one file (matches
// the prescriber-directory pattern). Future plans (B/C/D/E) may append more
// client interfaces here OR add domain-specific <name>-client.ts siblings.
//
// Gate-close fix (Codex): every cache key includes {tenant_id} as the first
// scoping segment, matching the tenant-isolation rule that all Redis keys
// MUST be prefixed `tenant:{tenant_id}:`. The cache layer interpolates
// {tenant_id} from the active tenant context.

import type { BaseClient } from "../../client-base.js";
import type { CachePolicy } from "../../cache-policy.js";
import type {
  Batch,
  BankSettlement,
  BankSettlementListResponse,
  BankSettlementStatus,
  BatchListResponse,
  BatchStatus,
  Carryover,
  CarryoverListResponse,
  Cycle,
  CycleListResponse,
  CycleStatus,
  InboxItem,
  Invoice,
  InvoiceListResponse,
  InvoiceStatus,
  PaymentRun,
  PaymentRunListResponse,
  PaymentRunStatus,
  RbacRole,
  Reconciliation,
  ReconciliationListResponse,
  ReconciliationStatus,
  Upload,
  UploadListRequest,
  UploadListResponse,
} from "./types.js";

// ── UploadsClient ───────────────────────────────────────────────────────
export interface UploadsClient extends BaseClient {
  readonly name: "paysync.uploads";

  /** List uploads for the active tenant. Filters via status; paginates via cursor. */
  list(req: UploadListRequest): Promise<UploadListResponse>;

  /** Fetch one upload by id. Returns null if not found / not visible to tenant. */
  get(id: string): Promise<Upload | null>;

  /** Create an upload by streaming bytes. Backend computes content_sha256.
   *  Plan A: signature only — real impl in Plan B. */
  create(args: {
    readonly filename: string;
    readonly content: Blob | ReadableStream<Uint8Array>;
  }): Promise<Upload>;

  /** Stream/list parsed claims for an upload. Plan A signature only. */
  getClaims(uploadId: string, opts?: {
    readonly limit?: number;
    readonly cursor?: string;
  }): Promise<{ results: Array<Record<string, unknown>>; next_cursor?: string; total: number }>;
}

export const PAYSYNC_UPLOADS_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "uploads", "list", "{tenant_id}", "{status}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:uploads"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "uploads", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:uploads"],
    backend_down: "stale-ok",
  },
  getClaims: {
    ttl_seconds: 60,
    key: ["paysync", "uploads", "claims", "{tenant_id}", "{uploadId}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:uploads", "paysync:claims"],
    backend_down: "stale-ok",
  },
};

// ── InboxClient ─────────────────────────────────────────────────────────
export interface InboxClient extends BaseClient {
  readonly name: "paysync.inbox";

  /** List inbox items for the given role within the active tenant. */
  list(role: RbacRole): Promise<InboxItem[]>;
}

export const PAYSYNC_INBOX_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    // 10s matches the spec §10.5 useInboxItems staleTime — same data, same TTL.
    ttl_seconds: 10,
    key: ["paysync", "inbox", "list", "{tenant_id}", "{role}"],
    invalidation_tags: ["paysync:inbox"],
    backend_down: "stale-ok",
  },
};

// ── CyclesClient ─────────────────────────────────────────────────────────
export interface CyclesClient extends BaseClient {
  readonly name: "paysync.cycles";

  /** List cycles for the active tenant. Filters via status; paginates via cursor. */
  list(req: { status?: CycleStatus; limit?: number; cursor?: string }): Promise<CycleListResponse>;

  /** Fetch one cycle by id. Returns null if not found / not visible to tenant. */
  get(id: string): Promise<Cycle | null>;

  /**
   * Close a cycle. Approver-only RBAC enforced server-side.
   * Transitions status from "closing" to "closed".
   */
  close(id: string): Promise<Cycle>;
}

export const PAYSYNC_CYCLES_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "cycles", "list", "{tenant_id}", "{status}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:cycles"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "cycles", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:cycles"],
    backend_down: "stale-ok",
  },
  close: {
    // Mutation — short TTL, fail-fast to prevent stale state.
    ttl_seconds: 0,
    key: ["paysync", "cycles", "close", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:cycles", "paysync:inbox"],
    backend_down: "fail-fast",
  },
};

// ── BatchesClient ─────────────────────────────────────────────────────────
export interface BatchesClient extends BaseClient {
  readonly name: "paysync.batches";

  /** List payment batches for the active tenant. */
  list(req: { status?: BatchStatus; limit?: number; cursor?: string }): Promise<BatchListResponse>;

  /** Fetch one batch by id. Returns null if not found. */
  get(id: string): Promise<Batch | null>;
}

export const PAYSYNC_BATCHES_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "batches", "list", "{tenant_id}", "{status}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:batches"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "batches", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:batches"],
    backend_down: "stale-ok",
  },
};

// ── InvoicesClient ────────────────────────────────────────────────────────
export interface InvoicesClient extends BaseClient {
  readonly name: "paysync.invoices";

  /** List invoices for the active tenant. */
  list(req: { status?: InvoiceStatus; client_id?: string; limit?: number; cursor?: string }): Promise<InvoiceListResponse>;

  /** Fetch one invoice by id. Returns null if not found. */
  get(id: string): Promise<Invoice | null>;
}

export const PAYSYNC_INVOICES_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "invoices", "list", "{tenant_id}", "{status}", "{client_id}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:invoices"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "invoices", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:invoices"],
    backend_down: "stale-ok",
  },
};

// ── PaymentRunsClient ─────────────────────────────────────────────────────
export interface PaymentRunsClient extends BaseClient {
  readonly name: "paysync.payment-runs";

  /** List payment runs for the active tenant. */
  list(req: { status?: PaymentRunStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<PaymentRunListResponse>;

  /** Fetch one payment run by id. Returns null if not found. */
  get(id: string): Promise<PaymentRun | null>;
}

export const PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "payment-runs", "list", "{tenant_id}", "{status}", "{batch_id}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:payment-runs"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "payment-runs", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:payment-runs"],
    backend_down: "stale-ok",
  },
};

// ── CarryoversClient ──────────────────────────────────────────────────────
export interface CarryoversClient extends BaseClient {
  readonly name: "paysync.carryovers";

  /** List carryovers for the active tenant. */
  list(req: { member_id?: string; from_period?: string; limit?: number; cursor?: string }): Promise<CarryoverListResponse>;

  /** Fetch one carryover by id. Returns null if not found. */
  get(id: string): Promise<Carryover | null>;
}

export const PAYSYNC_CARRYOVERS_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "carryovers", "list", "{tenant_id}", "{member_id}", "{from_period}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:carryovers"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "carryovers", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:carryovers"],
    backend_down: "stale-ok",
  },
};

// ── BankSettlementsClient ─────────────────────────────────────────────────
export interface BankSettlementsClient extends BaseClient {
  readonly name: "paysync.bank-settlements";

  /** List bank settlements for the active tenant. */
  list(req: { status?: BankSettlementStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<BankSettlementListResponse>;

  /** Fetch one bank settlement by id. Returns null if not found. */
  get(id: string): Promise<BankSettlement | null>;
}

export const PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "bank-settlements", "list", "{tenant_id}", "{status}", "{batch_id}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:bank-settlements"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "bank-settlements", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:bank-settlements"],
    backend_down: "stale-ok",
  },
};

// ── ReconciliationsClient ─────────────────────────────────────────────────
export interface ReconciliationsClient extends BaseClient {
  readonly name: "paysync.reconciliations";

  /** List reconciliations for the active tenant. */
  list(req: { status?: ReconciliationStatus; limit?: number; cursor?: string }): Promise<ReconciliationListResponse>;

  /** Fetch one reconciliation by id. Returns null if not found. */
  get(id: string): Promise<Reconciliation | null>;
}

export const PAYSYNC_RECONCILIATIONS_CACHE_POLICIES: Record<string, CachePolicy> = {
  list: {
    ttl_seconds: 30,
    key: ["paysync", "reconciliations", "list", "{tenant_id}", "{status}", "{cursor}", "{limit}"],
    invalidation_tags: ["paysync:reconciliations"],
    backend_down: "stale-ok",
  },
  get: {
    ttl_seconds: 60,
    key: ["paysync", "reconciliations", "by-id", "{tenant_id}", "{id}"],
    invalidation_tags: ["paysync:reconciliations"],
    backend_down: "stale-ok",
  },
};
