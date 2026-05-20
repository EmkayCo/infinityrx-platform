// packages/contract/src/impls/paysync/types.ts
// Zod schemas + types for the paysync contract surface (UploadsClient,
// InboxClient). Mirrors the prescriber-directory pattern: schemas are the
// runtime validators, types are the inferred TS shapes.

import { z } from "zod";

// ── RBAC role (mirrors the module-side type but lives in the contract so
// backend clients can speak in the same vocabulary as the UI) ────────────
export const RbacRoleSchema = z.enum(["operator", "approver", "auditor"]);
export type RbacRole = z.infer<typeof RbacRoleSchema>;

// ── Upload (paysync.upload backend resource — Plan B creates it) ────────
export const UploadStatusSchema = z.enum([
  "received",
  "parsing",
  "validated",
  "rejected",
  "applied",
]);
export type UploadStatus = z.infer<typeof UploadStatusSchema>;

export const UploadSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  filename: z.string().min(1).max(255),
  // SHA-256 hex of the canonical bytes — content-addressed dedupe key.
  content_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  status: UploadStatusSchema,
  // Decimal as string per .claude/rules/financial-precision.md. Aggregate
  // amount across all claims in this upload; null until parsing completes.
  total_billed_amount: z.string().nullable(),
  claim_count: z.number().int().nonnegative(),
  row_error_count: z.number().int().nonnegative(),
  uploaded_by_user_id: z.string().uuid(),
  uploaded_at: z.string().datetime({ offset: true }),
});
export type Upload = z.infer<typeof UploadSchema>;

// Inbox item from the contract perspective — alias renamed in the contract
// barrel export to avoid clashing with the module's own InboxItem type.
export const InboxItemSchema = z.object({
  id: z.string(),
  kind: z.string(),
  tenant_id: z.string(),
  upload_id: z.string().nullable(),
  rbac_required: RbacRoleSchema,
  created_at: z.string().datetime({ offset: true }),
  priority: z.enum(["normal", "high"]),
  payload: z.record(z.string(), z.unknown()),
});
export type InboxItem = z.infer<typeof InboxItemSchema>;

// Paginated upload list response.
export const UploadListResponseSchema = z.object({
  results: z.array(UploadSchema),
  next_cursor: z.string().optional(),
  total: z.number().int().nonnegative(),
});
export type UploadListResponse = z.infer<typeof UploadListResponseSchema>;

// List query.
export const UploadListRequestSchema = z.object({
  status: UploadStatusSchema.optional(),
  limit: z.number().int().positive().max(200).default(50),
  cursor: z.string().optional(),
});
export type UploadListRequest = z.infer<typeof UploadListRequestSchema>;

// ── Cycle (paysync billing cycle — Plan B adds CyclesClient) ────────────
export const CycleStatusSchema = z.enum([
  "open",
  "closing",
  "closed",
  "error",
]);
export type CycleStatus = z.infer<typeof CycleStatusSchema>;

export const CycleSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  // Human-readable period label e.g. "2026-05" or "Q2-2026".
  period_label: z.string().min(1).max(64),
  status: CycleStatusSchema,
  // ISO 8601 datetime when the billing window closed.
  // null when the cycle is still open.
  window_closed_at: z.string().datetime({ offset: true }).nullable(),
  // Provenance: which upload opened this cycle. null for system-initiated.
  origin_upload_id: z.string().uuid().nullable(),
  // Decimal-string total billed across all claims in this cycle.
  // null until the cycle transitions out of "open".
  total_billed_amount: z.string().nullable(),
  claim_count: z.number().int().nonnegative(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type Cycle = z.infer<typeof CycleSchema>;

// Paginated cycle list response.
export const CycleListResponseSchema = z.object({
  results: z.array(CycleSchema),
  next_cursor: z.string().optional(),
  total: z.number().int().nonnegative(),
});
export type CycleListResponse = z.infer<typeof CycleListResponseSchema>;

// ── Batch (paysync payment batch — Plan C adds BatchesClient) ────────────
export const BatchStatusSchema = z.enum([
  "generated",
  "validated",
  "approved",
  "submitted",
  "settled",
  "void",
]);
export type BatchStatus = z.infer<typeof BatchStatusSchema>;

export const BatchSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  // Human-readable batch identifier e.g. "BATCH-2026-001".
  batch_number: z.string().min(1).max(64),
  // ACH, wire, check, etc.
  payment_route: z.string().min(1).max(64),
  // Decimal-string total across all payments in this batch.
  total_amount: z.string(),
  payment_count: z.number().int().nonnegative(),
  ap_count: z.number().int().nonnegative(),
  status: BatchStatusSchema,
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type Batch = z.infer<typeof BatchSchema>;

// B4: backend /payment-batches returns a bare array; accept either shape and
// normalise to the envelope so consumers always use .results/.total.
export const BatchListResponseSchema = z.union([
  z.array(BatchSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(BatchSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type BatchListResponse = z.infer<typeof BatchListResponseSchema>;

// ── Invoice (paysync client invoice — Plan C adds InvoicesClient) ─────────
export const InvoiceStatusSchema = z.enum([
  "draft",
  "approved",
  "sent",
  "paid",
  "void",
  "overdue",
]);
export type InvoiceStatus = z.infer<typeof InvoiceStatusSchema>;

export const InvoiceSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  invoice_number: z.string().min(1).max(64),
  invoice_type: z.string().min(1).max(64),
  client_id: z.string().uuid(),
  client_name: z.string().min(1).max(255),
  // ISO date string (YYYY-MM-DD) for period boundaries.
  period_start: z.string().min(1),
  period_end: z.string().min(1),
  // All monetary fields are Decimal-as-string per financial-precision rules.
  claims_subtotal: z.string(),
  fees_subtotal: z.string(),
  adjustments: z.string(),
  late_fees: z.string(),
  total: z.string(),
  paid_amount: z.string(),
  claim_count: z.number().int().nonnegative(),
  status: InvoiceStatusSchema,
  // ISO date string (YYYY-MM-DD) payment due.
  due_date: z.string().min(1),
  created_at: z.string().datetime({ offset: true }),
});
export type Invoice = z.infer<typeof InvoiceSchema>;

// B4: backend /invoices returns a bare array; accept either shape and
// normalise to the envelope so consumers always use .results/.total.
export const InvoiceListResponseSchema = z.union([
  z.array(InvoiceSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(InvoiceSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type InvoiceListResponse = z.infer<typeof InvoiceListResponseSchema>;

// ── PaymentRun (paysync payment execution — Plan C adds PaymentRunsClient) ──
export const PaymentRunStatusSchema = z.enum([
  "pending",
  "running",
  "completed",
  "failed",
  "held",
]);
export type PaymentRunStatus = z.infer<typeof PaymentRunStatusSchema>;

export const PaymentRunSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  batch_id: z.string().uuid(),
  status: PaymentRunStatusSchema,
  // Decimal-string total across all payments dispatched in this run.
  total_amount: z.string(),
  payment_count: z.number().int().nonnegative(),
  run_at: z.string().datetime({ offset: true }),
  // null until the run completes or fails.
  completed_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
});
export type PaymentRun = z.infer<typeof PaymentRunSchema>;

// B4 R2: backend /payment-runs returns a bare array; accept either shape.
export const PaymentRunListResponseSchema = z.union([
  z.array(PaymentRunSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(PaymentRunSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type PaymentRunListResponse = z.infer<typeof PaymentRunListResponseSchema>;

// ── FileArtifact (paysync generated files — Plan D adds FilesClient) ──────────
export const FileArtifactKindSchema = z.enum(["nacha", "835"]);
export type FileArtifactKind = z.infer<typeof FileArtifactKindSchema>;

export const FileArtifactSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  // "kind" matches the backend column name (files.py uses "kind" in _artifact_to_dict).
  kind: FileArtifactKindSchema,
  source_batch_id: z.string().uuid().nullable(),
  source_payment_run_id: z.string().uuid().nullable(),
  // SHA-256 hex content hash.
  sha256: z.string().regex(/^[a-f0-9]{64}$/),
  file_size: z.number().int().nonnegative(),
  generated_at: z.string().datetime({ offset: true }).nullable(),
  // user_id of the approver who triggered generation.
  generated_by: z.string().uuid(),
  upload_id: z.string().uuid().nullable(),
  filename: z.string().min(1).max(255),
  status: z.string(),
});
export type FileArtifact = z.infer<typeof FileArtifactSchema>;

// Backend /files returns a JSON array; accept either shape and normalise.
export const FileArtifactListResponseSchema = z.union([
  z.array(FileArtifactSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(FileArtifactSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type FileArtifactListResponse = z.infer<typeof FileArtifactListResponseSchema>;

export const FileGenerateRequestSchema = z.object({
  // Plan D R1 B3: narrowed to match FileArtifactKindSchema; backend
  // GenerateFileRequest.kind accepts the same values.
  kind: FileArtifactKindSchema,
  source_id: z.string().uuid(),
});
export type FileGenerateRequest = z.infer<typeof FileGenerateRequestSchema>;

// ── JournalEntry (billing hash-chained ledger — Plan D adds JournalClient) ──
export const JournalEntrySchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  entry_date: z.string().nullable(),
  entry_timestamp: z.string().nullable(),
  entry_type: z.string(),
  client_id: z.string().uuid().nullable(),
  client_name: z.string().nullable(),
  program_id: z.string().uuid().nullable(),
  program_name: z.string().nullable(),
  pay_to_entity_id: z.string().uuid().nullable(),
  pay_to_entity_name: z.string().nullable(),
  // Decimal-as-string per financial-precision rules.
  amount: z.string(),
  category: z.string().nullable(),
  gl_account_code: z.string().nullable(),
  gl_class: z.string().nullable(),
  reference_type: z.string().nullable(),
  reference_id: z.string().uuid().nullable(),
  description: z.string().nullable(),
  exported_to_accounting: z.boolean().nullable(),
  exported_at: z.string().nullable(),
  export_reference: z.string().nullable(),
  created_at: z.string().nullable(),
  // Hash-chain fields.
  entry_hash: z.string().nullable(),
  prev_hash: z.string().nullable(),
});
export type JournalEntry = z.infer<typeof JournalEntrySchema>;

// Backend /journal returns a bare array; accept either shape.
export const JournalEntryListResponseSchema = z.union([
  z.array(JournalEntrySchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(JournalEntrySchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type JournalEntryListResponse = z.infer<typeof JournalEntryListResponseSchema>;

// Hash chain verify response -- mirrors journal.py verify_chain endpoint exactly.
export const HashChainVerifyResponseSchema = z.object({
  // null when too_large is true (chain not evaluated).
  verified: z.boolean().nullable(),
  too_large: z.boolean(),
  // Reserved for future async job path.
  job_id: z.string().nullable(),
  total_entries: z.number().int().nonnegative(),
  // entry id of the first broken link; null when verified or not checked.
  broken_at: z.string().nullable(),
});
export type HashChainVerifyResponse = z.infer<typeof HashChainVerifyResponseSchema>;

// ── Carryover (AP carryforward — billing.carryovers table, committed 5eb024f1) ─
// An APRecord that could not be fully paid in the current batch is represented
// as a Carryover. The Carryover carries the outstanding balance into the next
// PaymentBatch generation run. This is NOT a member accumulator carryover.
export const CarryoverSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  // FK to billing.ap_records — the AP record being carried forward.
  ap_record_id: z.string().uuid(),
  // Decimal-string outstanding AP amount (Numeric 12,2 in the DB).
  amount: z.string(),
  reason: z.string().min(1).max(255),
  // Upload provenance; null for legacy carryovers pre-dating SP-1.
  upload_id: z.string().uuid().nullable(),
  resolved: z.boolean(),
  resolved_at: z.string().datetime({ offset: true }).nullable(),
  resolved_by: z.string().uuid().nullable(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type Carryover = z.infer<typeof CarryoverSchema>;

// B4 + C4: backend /carryovers returns a bare array; accept either shape.
export const CarryoverListResponseSchema = z.union([
  z.array(CarryoverSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(CarryoverSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type CarryoverListResponse = z.infer<typeof CarryoverListResponseSchema>;

// ── BankSettlement (bank reconciliation settlement — Plan C) ──────────────
export const BankSettlementStatusSchema = z.enum([
  "matched",
  "unmatched",
  "discrepancy",
  "resolved",
]);
export type BankSettlementStatus = z.infer<typeof BankSettlementStatusSchema>;

export const BankSettlementSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  batch_id: z.string().uuid(),
  // Bank-provided reference number.
  bank_reference: z.string().min(1).max(128),
  // Decimal-string amount expected per the payment batch.
  expected_amount: z.string(),
  // Decimal-string amount actually settled by the bank.
  actual_amount: z.string(),
  status: BankSettlementStatusSchema,
  // ISO date string (YYYY-MM-DD) of settlement.
  settlement_date: z.string().min(1),
  // null until a discrepancy is resolved.
  resolved_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
});
export type BankSettlement = z.infer<typeof BankSettlementSchema>;

// B4 R2: backend /bank-settlements returns a bare array; accept either shape.
export const BankSettlementListResponseSchema = z.union([
  z.array(BankSettlementSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(BankSettlementSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type BankSettlementListResponse = z.infer<typeof BankSettlementListResponseSchema>;

// ── Reconciliation (period-level reconciliation — Plan C) ──────────────────
export const ReconciliationStatusSchema = z.enum([
  "pending",
  "in_progress",
  "complete",
  "failed",
]);
export type ReconciliationStatus = z.infer<typeof ReconciliationStatusSchema>;

export const ReconciliationSchema = z.object({
  id: z.string().uuid(),
  tenant_id: z.string().uuid(),
  // Period label e.g. "2026-04".
  period_label: z.string().min(1).max(64),
  status: ReconciliationStatusSchema,
  // Decimal-string totals — null until reconciliation runs.
  total_billed: z.string().nullable(),
  total_paid: z.string().nullable(),
  // Decimal-string variance (total_billed - total_paid). null until complete.
  variance: z.string().nullable(),
  // null until reconciliation is finalized.
  finalized_at: z.string().datetime({ offset: true }).nullable(),
  created_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
});
export type Reconciliation = z.infer<typeof ReconciliationSchema>;

// B4 R2: backend /reconciliations returns a bare array; accept either shape.
export const ReconciliationListResponseSchema = z.union([
  z.array(ReconciliationSchema).transform((items) => ({
    results: items,
    next_cursor: null as string | null,
    total: items.length,
  })),
  z.object({
    results: z.array(ReconciliationSchema),
    next_cursor: z.string().nullable().optional(),
    total: z.number().int().nonnegative(),
  }),
]);
export type ReconciliationListResponse = z.infer<typeof ReconciliationListResponseSchema>;
