// packages/contract/src/impls/paysync/mock.ts
// In-memory implementations of UploadsClient, InboxClient, and CyclesClient.
// Usable for dev, Storybook, and tests.
// Plan B populates real synthetic fixtures. Cycle data is inlined here
// (mirrors packages/modules/paysync/fixtures/seeds/cycles.json).

import {
  PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES,
  PAYSYNC_BATCHES_CACHE_POLICIES,
  PAYSYNC_CARRYOVERS_CACHE_POLICIES,
  PAYSYNC_CYCLES_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_INVOICES_CACHE_POLICIES,
  PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES,
  PAYSYNC_RECONCILIATIONS_CACHE_POLICIES,
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  type BankSettlementsClient,
  type BatchesClient,
  type CarryoversClient,
  type CyclesClient,
  type InboxClient,
  type InvoicesClient,
  type PaymentRunsClient,
  type ReconciliationsClient,
  type UploadsClient,
} from "./client.js";
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

// ── Batches mock ──────────────────────────────────────────────────────────

const FIXTURE_BATCHES: Batch[] = [
  {
    id: "b1000000-0000-0000-0000-000000000001",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_number: "BATCH-2026-001",
    payment_route: "ach",
    total_amount: "12345.67",
    payment_count: 10,
    ap_count: 10,
    status: "settled",
    created_at: "2026-05-01T00:00:00.000+00:00",
    updated_at: "2026-05-02T00:00:00.000+00:00",
  },
  {
    id: "b1000000-0000-0000-0000-000000000002",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_number: "BATCH-2026-002",
    payment_route: "ach",
    total_amount: "67890.12",
    payment_count: 25,
    ap_count: 25,
    status: "approved",
    created_at: "2026-05-10T00:00:00.000+00:00",
    updated_at: "2026-05-10T00:00:00.000+00:00",
  },
  {
    id: "b1000000-0000-0000-0000-000000000003",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_number: "BATCH-2026-003",
    payment_route: "wire",
    total_amount: "5000.00",
    payment_count: 3,
    ap_count: 3,
    status: "generated",
    created_at: "2026-05-15T00:00:00.000+00:00",
    updated_at: "2026-05-15T00:00:00.000+00:00",
  },
];

export function createMockBatchesClient(): BatchesClient {
  const batches: Batch[] = FIXTURE_BATCHES.map((b) => ({ ...b }));

  return {
    name: "paysync.batches" as const,
    cachePolicies: PAYSYNC_BATCHES_CACHE_POLICIES,

    async list(req: { status?: BatchStatus; limit?: number; cursor?: string }): Promise<BatchListResponse> {
      const filtered = req.status === undefined
        ? batches
        : batches.filter((b) => b.status === req.status);
      const limit = req.limit ?? 50;
      return { results: filtered.slice(0, limit), total: filtered.length };
    },

    async get(id: string): Promise<Batch | null> {
      return batches.find((b) => b.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

// ── Invoices mock ─────────────────────────────────────────────────────────

const FIXTURE_INVOICES: Invoice[] = [
  {
    id: "11000000-0000-0000-0000-000000000001",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    invoice_number: "INV-2026-001",
    invoice_type: "client_billing",
    client_id: "c1000000-0000-0000-0000-000000000001",
    client_name: "Acme Health Plan",
    period_start: "2026-04-01",
    period_end: "2026-04-30",
    claims_subtotal: "50000.00",
    fees_subtotal: "2500.00",
    adjustments: "0.00",
    late_fees: "0.00",
    total: "52500.00",
    paid_amount: "52500.00",
    claim_count: 500,
    status: "paid",
    due_date: "2026-05-15",
    created_at: "2026-04-30T00:00:00.000+00:00",
  },
  {
    id: "11000000-0000-0000-0000-000000000002",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    invoice_number: "INV-2026-002",
    invoice_type: "client_billing",
    client_id: "c1000000-0000-0000-0000-000000000001",
    client_name: "Acme Health Plan",
    period_start: "2026-05-01",
    period_end: "2026-05-31",
    claims_subtotal: "48000.00",
    fees_subtotal: "2400.00",
    adjustments: "-500.00",
    late_fees: "0.00",
    total: "49900.00",
    paid_amount: "0.00",
    claim_count: 480,
    status: "draft",
    due_date: "2026-06-15",
    created_at: "2026-05-31T00:00:00.000+00:00",
  },
];

export function createMockInvoicesClient(): InvoicesClient {
  const invoices: Invoice[] = FIXTURE_INVOICES.map((i) => ({ ...i }));

  return {
    name: "paysync.invoices" as const,
    cachePolicies: PAYSYNC_INVOICES_CACHE_POLICIES,

    async list(req: { status?: InvoiceStatus; client_id?: string; limit?: number; cursor?: string }): Promise<InvoiceListResponse> {
      let filtered = invoices;
      if (req.status !== undefined) filtered = filtered.filter((i) => i.status === req.status);
      if (req.client_id !== undefined) filtered = filtered.filter((i) => i.client_id === req.client_id);
      const limit = req.limit ?? 50;
      return { results: filtered.slice(0, limit), total: filtered.length };
    },

    async get(id: string): Promise<Invoice | null> {
      return invoices.find((i) => i.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

// ── PaymentRuns mock ──────────────────────────────────────────────────────

const FIXTURE_PAYMENT_RUNS: PaymentRun[] = [
  {
    id: "20000000-0000-0000-0000-000000000001",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_id: "b1000000-0000-0000-0000-000000000001",
    status: "completed",
    total_amount: "12345.67",
    payment_count: 10,
    run_at: "2026-05-02T08:00:00.000+00:00",
    completed_at: "2026-05-02T08:01:30.000+00:00",
    created_at: "2026-05-02T08:00:00.000+00:00",
  },
  {
    id: "20000000-0000-0000-0000-000000000002",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_id: "b1000000-0000-0000-0000-000000000002",
    status: "pending",
    total_amount: "67890.12",
    payment_count: 25,
    run_at: "2026-05-11T08:00:00.000+00:00",
    completed_at: null,
    created_at: "2026-05-11T08:00:00.000+00:00",
  },
];

export function createMockPaymentRunsClient(): PaymentRunsClient {
  const runs: PaymentRun[] = FIXTURE_PAYMENT_RUNS.map((r) => ({ ...r }));

  return {
    name: "paysync.payment-runs" as const,
    cachePolicies: PAYSYNC_PAYMENT_RUNS_CACHE_POLICIES,

    async list(req: { status?: PaymentRunStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<PaymentRunListResponse> {
      let filtered = runs;
      if (req.status !== undefined) filtered = filtered.filter((r) => r.status === req.status);
      if (req.batch_id !== undefined) filtered = filtered.filter((r) => r.batch_id === req.batch_id);
      const limit = req.limit ?? 50;
      return { results: filtered.slice(0, limit), total: filtered.length };
    },

    async get(id: string): Promise<PaymentRun | null> {
      return runs.find((r) => r.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

// ── Carryovers mock ───────────────────────────────────────────────────────
// Fixtures mirror the AP-carryforward shape (billing.carryovers, commit 5eb024f1).

const FIXTURE_CARRYOVERS: Carryover[] = [
  {
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
  },
  {
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
  },
];

export function createMockCarryoversClient(): CarryoversClient {
  const carryovers: Carryover[] = FIXTURE_CARRYOVERS.map((c) => ({ ...c }));

  return {
    name: "paysync.carryovers" as const,
    cachePolicies: PAYSYNC_CARRYOVERS_CACHE_POLICIES,

    // NOTE: client.ts list signature still uses member_id/from_period from the
    // old member-accumulator design; those params are treated as no-ops until
    // client.ts is updated in the C4 follow-up (Task 7 / sp-1-c-C4-followup).
    async list(req: { member_id?: string; from_period?: string; limit?: number; cursor?: string }): Promise<CarryoverListResponse> {
      void req.member_id;
      void req.from_period;
      const limit = req.limit ?? 50;
      return { results: carryovers.slice(0, limit), total: carryovers.length };
    },

    async get(id: string): Promise<Carryover | null> {
      return carryovers.find((c) => c.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

// ── BankSettlements mock ──────────────────────────────────────────────────

const FIXTURE_BANK_SETTLEMENTS: BankSettlement[] = [
  {
    id: "f0000000-0000-0000-0000-000000000001",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_id: "b1000000-0000-0000-0000-000000000001",
    bank_reference: "ACH-20260502-001",
    expected_amount: "12345.67",
    actual_amount: "12345.67",
    status: "matched",
    settlement_date: "2026-05-02",
    resolved_at: null,
    created_at: "2026-05-02T12:00:00.000+00:00",
  },
  {
    id: "f0000000-0000-0000-0000-000000000002",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    batch_id: "b1000000-0000-0000-0000-000000000002",
    bank_reference: "ACH-20260511-002",
    expected_amount: "67890.12",
    actual_amount: "67889.00",
    status: "discrepancy",
    settlement_date: "2026-05-11",
    resolved_at: null,
    created_at: "2026-05-11T12:00:00.000+00:00",
  },
];

export function createMockBankSettlementsClient(): BankSettlementsClient {
  const settlements: BankSettlement[] = FIXTURE_BANK_SETTLEMENTS.map((s) => ({ ...s }));

  return {
    name: "paysync.bank-settlements" as const,
    cachePolicies: PAYSYNC_BANK_SETTLEMENTS_CACHE_POLICIES,

    async list(req: { status?: BankSettlementStatus; batch_id?: string; limit?: number; cursor?: string }): Promise<BankSettlementListResponse> {
      let filtered = settlements;
      if (req.status !== undefined) filtered = filtered.filter((s) => s.status === req.status);
      if (req.batch_id !== undefined) filtered = filtered.filter((s) => s.batch_id === req.batch_id);
      const limit = req.limit ?? 50;
      return { results: filtered.slice(0, limit), total: filtered.length };
    },

    async get(id: string): Promise<BankSettlement | null> {
      return settlements.find((s) => s.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}

// ── Reconciliations mock ──────────────────────────────────────────────────

const FIXTURE_RECONCILIATIONS: Reconciliation[] = [
  {
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
  },
  {
    id: "10000000-0000-0000-0000-000000000002",
    tenant_id: "a0000000-0000-0000-0000-000000000001",
    period_label: "2026-05",
    status: "in_progress",
    total_billed: null,
    total_paid: null,
    variance: null,
    finalized_at: null,
    created_at: "2026-05-31T00:00:00.000+00:00",
    updated_at: "2026-05-31T00:00:00.000+00:00",
  },
];

export function createMockReconciliationsClient(): ReconciliationsClient {
  const recs: Reconciliation[] = FIXTURE_RECONCILIATIONS.map((r) => ({ ...r }));

  return {
    name: "paysync.reconciliations" as const,
    cachePolicies: PAYSYNC_RECONCILIATIONS_CACHE_POLICIES,

    async list(req: { status?: ReconciliationStatus; limit?: number; cursor?: string }): Promise<ReconciliationListResponse> {
      const filtered = req.status === undefined
        ? recs
        : recs.filter((r) => r.status === req.status);
      const limit = req.limit ?? 50;
      return { results: filtered.slice(0, limit), total: filtered.length };
    },

    async get(id: string): Promise<Reconciliation | null> {
      return recs.find((r) => r.id === id) ?? null;
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
