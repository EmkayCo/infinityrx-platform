// packages/modules/paysync/src/bff/index.ts
// Centralized BFF barrel for @infinityrx/module-paysync/bff subpath.
// portal/operator App Router handlers import from this barrel — never
// directly from surface bff modules. Mirrors the directories module pattern.
//
// NOTE: Each surface bff file re-exports its own BffRequest/BffResponse
// interface (identical shapes). We re-export the shared interface types
// only once (from uploads) to avoid duplicate-export TS errors. Handler
// functions are re-exported individually by name.

// ── Shared BFF types (re-exported once from uploads) ─────────────────────
export type { BffRequest, BffResponse } from "../surfaces/uploads/bff/uploads.js";

// ── Uploads surface (G1 C1 — operator upload path, highest priority) ─────
export {
  handleListUploads,
  handleGetUpload,
  handleGetUploadClaims,
  handleCreateUpload,
} from "../surfaces/uploads/bff/uploads.js";

// ── Cycles surface ────────────────────────────────────────────────────────
export {
  handleListCycles,
  handleGetCycle,
  handleCloseCycle,
} from "../surfaces/cycles/bff/cycles.js";

// ── Batches surface ───────────────────────────────────────────────────────
export {
  handleListBatches,
  handleGetBatch,
} from "../surfaces/batches/bff/batches.js";

// ── Carryovers surface ────────────────────────────────────────────────────
export {
  handleListCarryovers,
  handleGetCarryover,
} from "../surfaces/carryovers/bff/carryovers.js";

// ── Invoices surface ──────────────────────────────────────────────────────
export {
  handleListInvoices,
  handleGetInvoice,
} from "../surfaces/invoices/bff/invoices.js";

// ── Payment-runs surface ──────────────────────────────────────────────────
export {
  handleListPaymentRuns,
  handleGetPaymentRun,
} from "../surfaces/payment-runs/bff/payment-runs.js";

// ── Files surface ─────────────────────────────────────────────────────────
export {
  handleListFiles,
  handleGetFile,
  handleGenerateFile,
  handleDownloadFile,
} from "../surfaces/files/bff/files.js";

// ── Bank-settlements surface ──────────────────────────────────────────────
export {
  handleListBankSettlements,
  handleGetBankSettlement,
} from "../surfaces/bank-settlements/bff/bank-settlements.js";

// ── Reconciliations surface ───────────────────────────────────────────────
export {
  handleListReconciliations,
  handleGetReconciliation,
} from "../surfaces/reconciliations/bff/reconciliations.js";

// ── Journal surface ───────────────────────────────────────────────────────
export {
  handleListJournal,
  handleGetJournalEntry,
  handleVerifyChain,
} from "../surfaces/journal/bff/journal.js";

// ── Reports surface ───────────────────────────────────────────────────────
export {
  handleListCycleReports,
  handleListJournalEntriesReport,
  handleGetPeriodSummary,
} from "../surfaces/reports/bff/reports.js";

// ── Setup surface ─────────────────────────────────────────────────────────
export {
  handleListEmailRecipients,
  handleListEmailTemplates,
  handleListExportTemplates,
  handleListGlAccountMappings,
  handleListInvoiceSequences,
  handleListCycleSchedules,
} from "../surfaces/setup/bff/setup.js";
