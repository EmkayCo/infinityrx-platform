// Smoke test: verify root-level re-exports remain present.
// Plan E R2 added page-component re-exports so portal/operator App Router
// wrappers can `import { ReportsListPage } from "@infinityrx/module-paysync"`.
// G1 C1 adds uploads surface page-component re-exports (UploadsListPage,
// UploadDropzone, UploadDetailPage, UploadClaimViewer).
// If a future refactor drops one of these exports, this test fails fast
// before downstream portal builds break.

import { describe, it, expect } from "vitest";
import * as paysync from "../src/index.js";

const requiredExports = [
  // Uploads surface page components (G1 C1)
  "UploadsListPage",
  "UploadDropzone",
  "UploadDetailPage",
  "UploadClaimViewer",
  // Reports surface page components
  "ReportsListPage",
  "CycleReportsPage",
  "JournalEntriesReportPage",
  "PeriodSummaryPage",
  // Setup surface page components
  "SetupHomePage",
  "EmailRecipientsPage",
  "EmailTemplatesPage",
  "ExportTemplatesPage",
  "GlAccountMappingsPage",
  "InvoiceSequencesPage",
  "CycleSchedulesPage",
] as const;

describe("@infinityrx/module-paysync root index", () => {
  for (const name of requiredExports) {
    it(`re-exports ${name}`, () => {
      expect(paysync).toHaveProperty(name);
      expect(typeof (paysync as Record<string, unknown>)[name]).toBe("function");
    });
  }
});
