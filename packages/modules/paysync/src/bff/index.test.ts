// Smoke test: verify BFF barrel re-exports all surface handler functions.
// This ensures portal/operator route files can import from
// @infinityrx/module-paysync/bff without importing from surface paths directly.
// If a handler is accidentally dropped, this fails before portal build breaks.

import { describe, it, expect } from "vitest";
import * as bff from "./index.js";

const requiredHandlers = [
  // Uploads (G1 C1 — highest priority)
  "handleListUploads",
  "handleGetUpload",
  "handleGetUploadClaims",
  "handleCreateUpload",
  // Cycles
  "handleListCycles",
  "handleGetCycle",
  "handleCloseCycle",
  // Batches
  "handleListBatches",
  "handleGetBatch",
  // Carryovers
  "handleListCarryovers",
  "handleGetCarryover",
  // Invoices
  "handleListInvoices",
  "handleGetInvoice",
  // Payment-runs
  "handleListPaymentRuns",
  "handleGetPaymentRun",
  // Files
  "handleListFiles",
  "handleGetFile",
  "handleGenerateFile",
  "handleDownloadFile",
  // Bank-settlements
  "handleListBankSettlements",
  "handleGetBankSettlement",
  // Reconciliations
  "handleListReconciliations",
  "handleGetReconciliation",
  // Journal
  "handleListJournal",
  "handleGetJournalEntry",
  "handleVerifyChain",
  // Reports
  "handleListCycleReports",
  "handleListJournalEntriesReport",
  "handleGetPeriodSummary",
  // Setup
  "handleListEmailRecipients",
  "handleListEmailTemplates",
  "handleListExportTemplates",
  "handleListGlAccountMappings",
  "handleListInvoiceSequences",
  "handleListCycleSchedules",
] as const;

describe("@infinityrx/module-paysync/bff barrel", () => {
  for (const name of requiredHandlers) {
    it(`re-exports ${name}`, () => {
      expect(bff).toHaveProperty(name);
      expect(typeof (bff as Record<string, unknown>)[name]).toBe("function");
    });
  }
});
