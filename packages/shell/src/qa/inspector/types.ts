/**
 * A single captured request/response entry for the inspector panel.
 */
export interface InspectorEntry {
  /** Unique ID for React key and dedup. */
  readonly id: string;
  /** HTTP method, upper-cased. */
  readonly method: string;
  /** Full URL. */
  readonly url: string;
  /** HTTP status code, or 0 on network error. */
  readonly status: number;
  /** Round-trip latency in milliseconds. */
  readonly latencyMs: number;
  /** Whether the client was in mock mode when this call was made. */
  readonly isMock: boolean;
  /** Whether the response was served from cache (populated by the BFF cache layer). */
  readonly cacheHit: boolean;
  /** Correlation ID extracted from the x-correlation-id response header. */
  readonly correlationId?: string;
  /** ISO 8601 timestamp of the request. */
  readonly timestamp: string;
  /** Request body, if any (non-null only for POST/PUT/PATCH). */
  readonly requestBody?: unknown;
  /** Response body (JSON-parsed), if successful. */
  readonly responseBody?: unknown;
}
