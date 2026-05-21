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

// Cycles surface page components (mounted by portal/operator App Router)
export { CyclesListPage, type CyclesListPageProps } from "./surfaces/cycles/CyclesListPage.js";
export { CycleDetailPage, type CycleDetailPageProps } from "./surfaces/cycles/CycleDetailPage.js";

// Batches surface page components (mounted by portal/operator App Router)
export { BatchesListPage, type BatchesListPageProps } from "./surfaces/batches/BatchesListPage.js";
export { BatchDetailPage, type BatchDetailPageProps } from "./surfaces/batches/BatchDetailPage.js";

// Carryovers surface page components (mounted by portal/operator App Router)
export { CarryoversListPage, type CarryoversListPageProps } from "./surfaces/carryovers/CarryoversListPage.js";
export { CarryoverDetailPage, type CarryoverDetailPageProps } from "./surfaces/carryovers/CarryoverDetailPage.js";

// Invoices surface page components (mounted by portal/operator App Router)
export { InvoicesListPage, type InvoicesListPageProps } from "./surfaces/invoices/InvoicesListPage.js";
export { InvoiceDetailPage, type InvoiceDetailPageProps } from "./surfaces/invoices/InvoiceDetailPage.js";

// Payment-runs surface page components (mounted by portal/operator App Router)
export { PaymentRunsListPage, type PaymentRunsListPageProps } from "./surfaces/payment-runs/PaymentRunsListPage.js";
export { PaymentRunDetailPage, type PaymentRunDetailPageProps } from "./surfaces/payment-runs/PaymentRunDetailPage.js";
export { ManualApForm, type ManualApFormProps, type ManualApEntry } from "./surfaces/payment-runs/ManualApForm.js";

// Files surface page components (mounted by portal/operator App Router)
export { FilesListPage, type FilesListPageProps } from "./surfaces/files/FilesListPage.js";
export { FileDetailPage, type FileDetailPageProps } from "./surfaces/files/FileDetailPage.js";
export { FileGenerateForm, type FileGenerateFormProps } from "./surfaces/files/FileGenerateForm.js";

// Bank-settlements surface page components (mounted by portal/operator App Router)
export { BankSettlementsListPage, type BankSettlementsListPageProps } from "./surfaces/bank-settlements/BankSettlementsListPage.js";
export { BankSettlementDetailPage, type BankSettlementDetailPageProps } from "./surfaces/bank-settlements/BankSettlementDetailPage.js";

// Reconciliations surface page components (mounted by portal/operator App Router)
export { ReconciliationsListPage, type ReconciliationsListPageProps } from "./surfaces/reconciliations/ReconciliationsListPage.js";
export { ReconciliationDetailPage, type ReconciliationDetailPageProps } from "./surfaces/reconciliations/ReconciliationDetailPage.js";

// Journal surface page components (mounted by portal/operator App Router)
export { JournalListPage, type JournalListPageProps } from "./surfaces/journal/JournalListPage.js";
export { JournalDetailPage, type JournalDetailPageProps } from "./surfaces/journal/JournalDetailPage.js";
export { HashChainVerifyButton, type HashChainVerifyButtonProps } from "./surfaces/journal/HashChainVerifyButton.js";

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
