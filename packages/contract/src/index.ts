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

// PaySync clients — SP-1.
export {
  UploadSchema,
  UploadStatusSchema,
  UploadListRequestSchema,
  UploadListResponseSchema,
  InboxItemSchema,
  RbacRoleSchema,
  CycleSchema,
  CycleStatusSchema,
  CycleListResponseSchema,
  type Upload,
  type UploadStatus,
  type UploadListRequest,
  type UploadListResponse,
  type Cycle,
  type CycleStatus,
  type CycleListResponse,
  type InboxItem as PaysyncInboxItem,
  type RbacRole as PaysyncRbacRole,
} from "./impls/paysync/types.js";

export {
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_CYCLES_CACHE_POLICIES,
  type UploadsClient,
  type InboxClient,
  type CyclesClient,
} from "./impls/paysync/client.js";

export {
  createRealUploadsClient,
  createRealInboxClient,
  createRealCyclesClient,
} from "./impls/paysync/real.js";

export {
  createMockUploadsClient,
  createMockInboxClient,
  createMockCyclesClient,
} from "./impls/paysync/mock.js";
