// packages/modules/paysync/src/surfaces/reports/index.ts
// Reports surface: surface descriptor + public component exports.
// Plan E adds ReportsListPage, CycleReportsPage, JournalEntriesReportPage,
// PeriodSummaryPage and BFF route handlers.
// All reports are read-only. All roles can access.

import type { SurfaceConfig } from "../../types/surface.js";

export const ReportsSurface: SurfaceConfig = {
  id: "reports",
  path: "/admin/paysync/reports",
};

export { ReportsListPage } from "./ReportsListPage.js";

export { CycleReportsPage } from "./CycleReportsPage.js";
export type { CycleReportsPageProps } from "./CycleReportsPage.js";

export { JournalEntriesReportPage } from "./JournalEntriesReportPage.js";
export type { JournalEntriesReportPageProps } from "./JournalEntriesReportPage.js";

export { PeriodSummaryPage } from "./PeriodSummaryPage.js";
export type { PeriodSummaryPageProps } from "./PeriodSummaryPage.js";

export {
  handleListCycleReports,
  handleListJournalEntriesReport,
  handleGetPeriodSummary,
} from "./bff/reports.js";
export type { BffRequest, BffResponse, ReportsClient, PeriodSummaryData } from "./bff/reports.js";
