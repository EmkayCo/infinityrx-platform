// Public surface of @infinityrx/contract.

export {
  ErrorEnvelopeSchema,
  isErrorEnvelope,
  type ErrorEnvelope,
} from "./error-envelope.js";

export {
  CachePolicySchema,
  type CachePolicy,
} from "./cache-policy.js";

export type {
  BaseClient,
  ClientConfig,
  ClientFactory,
} from "./client-base.js";

// Reference client: prescriber-directory. Other 12 backend clients live in their own SP-N verticals.
export {
  PrescriberSchema,
  PrescriberSearchRequestSchema,
  PrescriberSearchResponseSchema,
  NpiSchema,
  type Prescriber,
  type PrescriberSearchRequest,
  type PrescriberSearchResponse,
  type Npi,
} from "./impls/prescriber-directory/types.js";

export {
  PRESCRIBER_DIRECTORY_CACHE_POLICIES,
  type PrescriberDirectoryClient,
  type PrescriberDirectoryFactory,
} from "./impls/prescriber-directory/client.js";

export { createRealPrescriberDirectoryClient } from "./impls/prescriber-directory/real.js";
export { createMockPrescriberDirectoryClient } from "./impls/prescriber-directory/mock.js";

// ReclaimRx client — SP-3.
export {
  InvestigationStatusSchema,
  InvestigationSchema,
  InvestigationListResponseSchema,
  InvestigationTransitionRequestSchema,
  HoldReleaseRequestSchema,
  HoldReleaseResponseSchema,
  PaymentHoldSchema,
  GraphRunSchema,
  FraudRingSchema,
  ThresholdConfigSchema,
  DashboardSummarySchema,
  AccumulatorAnomalySchema,
  type Investigation,
  type InvestigationStatus,
  type PaymentHold,
  type GraphRun,
  type FraudRing,
  type ThresholdConfig,
  type DashboardSummary,
  type AccumulatorAnomaly,
  type HoldReleaseRequest,
  type HoldReleaseResponse,
} from "./impls/reclaimrx/types.js";

export {
  RECLAIMRX_CACHE_POLICIES,
  type ReclaimRxClient,
  type ReclaimRxFactory,
} from "./impls/reclaimrx/client.js";

export { createRealReclaimRxClient } from "./impls/reclaimrx/real.js";
export { createMockReclaimRxClient } from "./impls/reclaimrx/mock.js";

// PaySync clients — SP-1.
export {
  BankSettlementListResponseSchema,
  BankSettlementSchema,
  BankSettlementStatusSchema,
  BatchListResponseSchema,
  BatchSchema,
  BatchStatusSchema,
  CarryoverListResponseSchema,
  CarryoverSchema,
  CycleListResponseSchema,
  CycleSchema,
  CycleStatusSchema,
  FileArtifactKindSchema,
  FileArtifactListResponseSchema,
  FileArtifactSchema,
  FileGenerateRequestSchema,
  HashChainVerifyResponseSchema,
  InboxItemSchema,
  InvoiceListResponseSchema,
  InvoiceSchema,
  InvoiceStatusSchema,
  JournalEntryListResponseSchema,
  JournalEntrySchema,
  PaymentRunListResponseSchema,
  PaymentRunSchema,
  PaymentRunStatusSchema,
  RbacRoleSchema,
  ReconciliationListResponseSchema,
  ReconciliationSchema,
  ReconciliationStatusSchema,
  UploadListRequestSchema,
  UploadListResponseSchema,
  UploadSchema,
  UploadStatusSchema,
  type BankSettlement,
  type BankSettlementListResponse,
  type BankSettlementStatus,
  type Batch,
  type BatchListResponse,
  type BatchStatus,
  type Carryover,
  type CarryoverListResponse,
  type Cycle,
  type CycleListResponse,
  type CycleStatus,
  type FileArtifact,
  type FileArtifactKind,
  type FileArtifactListResponse,
  type FileGenerateRequest,
  type HashChainVerifyResponse,
  type InboxItem as PaysyncInboxItem,
  type Invoice,
  type InvoiceListResponse,
  type InvoiceStatus,
  type JournalEntry,
  type JournalEntryListResponse,
  type PaymentRun,
  type PaymentRunListResponse,
  type PaymentRunStatus,
  type RbacRole as PaysyncRbacRole,
  type Reconciliation,
  type ReconciliationListResponse,
  type ReconciliationStatus,
  type Upload,
  type UploadListRequest,
  type UploadListResponse,
  type UploadStatus,
} from "./impls/paysync/types.js";

export {
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
} from "./impls/paysync/client.js";

export {
  createRealBankSettlementsClient,
  createRealBatchesClient,
  createRealCarryoversClient,
  createRealCyclesClient,
  createRealFilesClient,
  createRealInboxClient,
  createRealInvoicesClient,
  createRealJournalClient,
  createRealPaymentRunsClient,
  createRealReconciliationsClient,
  createRealUploadsClient,
} from "./impls/paysync/real.js";

export {
  createMockBankSettlementsClient,
  createMockBatchesClient,
  createMockCarryoversClient,
  createMockCyclesClient,
  createMockFilesClient,
  createMockInboxClient,
  createMockInvoicesClient,
  createMockJournalClient,
  createMockPaymentRunsClient,
  createMockReconciliationsClient,
  createMockUploadsClient,
} from "./impls/paysync/mock.js";
