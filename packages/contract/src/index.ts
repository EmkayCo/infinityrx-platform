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
