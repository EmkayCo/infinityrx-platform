import type { CachePolicy } from "./cache-policy.js";

/**
 * Every typed backend client implements this contract.
 * Concrete clients (RealImpl + MockImpl) expose domain methods (e.g.,
 * `prescriberClient.search({ npi })`); the BaseClient describes only the
 * cross-cutting metadata the BFF + cache layer need.
 */
export interface BaseClient {
  /** Stable identifier for telemetry + cache key namespacing. e.g. "prescriber-directory" */
  readonly name: string;

  /** Per-resource cache policies keyed by operation name. */
  readonly cachePolicies: Record<string, CachePolicy>;

  /** Health probe for the services-health aggregator (Plan C). */
  probeHealth(): Promise<{ ok: boolean; latency_ms: number; error?: string }>;
}

export type ClientFactory<T extends BaseClient> = (config: ClientConfig) => T;

export interface ClientConfig {
  /** Base URL of the backend (real) or undefined (mock). */
  baseUrl?: string;
  /** Function that produces a fresh access token Bearer string. */
  getAuthToken: () => Promise<string>;
  /** Correlation-id propagation header (default `x-correlation-id`). */
  correlationHeader?: string;
  /** Fetch implementation override (Node uses undici; tests inject msw). */
  fetch?: typeof globalThis.fetch;
}
