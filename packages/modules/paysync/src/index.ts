// packages/modules/paysync/src/index.ts
// Public surface of @infinityrx/module-paysync.
//
// Consumers (portal/operator, shell composition, qa-harness) import from
// '@infinityrx/module-paysync' which resolves to dist/src/index.js per the
// package.json `exports` field. The module's `module.config.ts` is read
// separately by build tooling via file-path glob and is NOT re-exported here.

// Inbox spine — types, registry, hook, queue component
export {
  INBOX_KIND_ROLE,
  type InboxItem,
  type InboxItemKind,
  type RbacRole,
} from "./inbox/types.js";
export {
  ItemRegistry,
  type InboxCardComponent,
  type InboxRegistration,
} from "./inbox/ItemRegistry.js";
export { useInboxItems, type UseInboxItemsResult } from "./inbox/useInboxItems.js";
export { InboxQueue, type InboxQueueProps } from "./inbox/InboxQueue.js";

// Module-local primitives (excludes dev-only/ — qa-harness reaches it via
// paysyncComposition.qa in module.config.ts under a NODE_ENV guard)
export {
  MoneyDisplay,
  type MoneyDisplayProps,
} from "./components/MoneyDisplay.js";
export {
  MoneyInput,
  type MoneyInputProps,
} from "./components/MoneyInput.js";
export {
  RbacGate,
  type RbacGateProps,
} from "./components/RbacGate.js";
export {
  ProvenanceBreadcrumb,
  type ProvenanceBreadcrumbProps,
  type ProvenanceLink,
} from "./components/ProvenanceBreadcrumb.js";
export {
  HashChainBadge,
  type HashChainBadgeProps,
} from "./components/HashChainBadge.js";

// Surface descriptor type + 13 surface configs
export type { SurfaceConfig } from "./types/surface.js";
export { UploadsSurface } from "./surfaces/uploads/index.js";
export { CyclesSurface } from "./surfaces/cycles/index.js";
export { BatchesSurface } from "./surfaces/batches/index.js";
export { CarryoversSurface } from "./surfaces/carryovers/index.js";
export { InvoicesSurface } from "./surfaces/invoices/index.js";
export { PaymentRunsSurface } from "./surfaces/payment-runs/index.js";
export { FilesSurface } from "./surfaces/files/index.js";
export { BankSettlementsSurface } from "./surfaces/bank-settlements/index.js";
export { ReconciliationsSurface } from "./surfaces/reconciliations/index.js";
export { JournalSurface } from "./surfaces/journal/index.js";
export { ReportsSurface } from "./surfaces/reports/index.js";
export { SetupSurface } from "./surfaces/setup/index.js";
export { EchoSurface } from "./surfaces/echo/index.js";

// Uploads surface page components (mounted by portal/operator App Router)
export {
  UploadsListPage,
  type UploadsListPageProps,
  type DedupBanner,
} from "./surfaces/uploads/UploadsListPage.js";
export {
  UploadDropzone,
  type UploadDropzoneProps,
} from "./surfaces/uploads/UploadDropzone.js";
export {
  UploadDetailPage,
  type UploadDetailPageProps,
  type RowError,
} from "./surfaces/uploads/UploadDetailPage.js";
export {
  UploadClaimViewer,
  type UploadClaimViewerProps,
} from "./surfaces/uploads/UploadClaimViewer.js";

// Reports surface page components (mounted by portal/operator App Router)
export { ReportsListPage } from "./surfaces/reports/ReportsListPage.js";
export { CycleReportsPage, type CycleReportsPageProps } from "./surfaces/reports/CycleReportsPage.js";
export {
  JournalEntriesReportPage,
  type JournalEntriesReportPageProps,
} from "./surfaces/reports/JournalEntriesReportPage.js";
export {
  PeriodSummaryPage,
  type PeriodSummaryPageProps,
} from "./surfaces/reports/PeriodSummaryPage.js";

// Setup surface page components (mounted by portal/operator App Router)
export { SetupHomePage } from "./surfaces/setup/SetupHomePage.js";
export {
  EmailRecipientsPage,
  type EmailRecipientsPageProps,
  type EmailRecipient,
} from "./surfaces/setup/EmailRecipientsPage.js";
export {
  EmailTemplatesPage,
  type EmailTemplatesPageProps,
  type EmailTemplate,
} from "./surfaces/setup/EmailTemplatesPage.js";
export {
  ExportTemplatesPage,
  type ExportTemplatesPageProps,
  type ExportTemplate,
  type ExportFormat,
} from "./surfaces/setup/ExportTemplatesPage.js";
export {
  GlAccountMappingsPage,
  type GlAccountMappingsPageProps,
  type GlAccountMapping,
} from "./surfaces/setup/GlAccountMappingsPage.js";
export {
  InvoiceSequencesPage,
  type InvoiceSequencesPageProps,
  type InvoiceSequence,
} from "./surfaces/setup/InvoiceSequencesPage.js";
export {
  CycleSchedulesPage,
  type CycleSchedulesPageProps,
  type CycleSchedule,
  type CycleFrequency,
} from "./surfaces/setup/CycleSchedulesPage.js";
