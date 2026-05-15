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
