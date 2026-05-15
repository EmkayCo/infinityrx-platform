import type { PrescriberDirectoryClient } from "./client.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "./client.js";
import type { ClientConfig } from "../../client-base.js";
import {
  PrescriberSchema,
  PrescriberSearchRequestSchema,
  PrescriberSearchResponseSchema,
  type Npi,
  type Prescriber,
  type PrescriberSearchRequest,
  type PrescriberSearchResponse,
} from "./types.js";
import { isErrorEnvelope } from "../../error-envelope.js";

class RealClientError extends Error {
  constructor(public readonly code: string, message: string, public readonly correlationId?: string) {
    super(message);
    this.name = "RealClientError";
  }
}

export function createRealPrescriberDirectoryClient(config: ClientConfig): PrescriberDirectoryClient {
  if (!config.baseUrl) {
    throw new Error("createRealPrescriberDirectoryClient: baseUrl is required");
  }
  const baseUrl = config.baseUrl.replace(/\/$/, "");
  const correlationHeader = config.correlationHeader ?? "x-correlation-id";
  const fetchImpl = config.fetch ?? globalThis.fetch;

  async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
    const token = await config.getAuthToken();
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    headers.set(correlationHeader, crypto.randomUUID());
    return fetchImpl(`${baseUrl}${path}`, { ...init, headers });
  }

  async function unwrap<T>(res: Response, schema: { parse(raw: unknown): T }): Promise<T> {
    const body = await res.json() as unknown;
    if (!res.ok) {
      if (isErrorEnvelope(body)) {
        throw new RealClientError(body.error.code, body.error.message, body.error.correlation_id);
      }
      throw new Error(`Unexpected error shape: HTTP ${res.status}`);
    }
    return schema.parse(body);
  }

  return {
    name: "prescriber-directory" as const,
    cachePolicies: PRESCRIBER_DIRECTORY_CACHE_POLICIES,

    async search(req: PrescriberSearchRequest): Promise<PrescriberSearchResponse> {
      const validated = PrescriberSearchRequestSchema.parse(req);
      const qs = new URLSearchParams();
      qs.set("q", validated.q);
      if (validated.state) qs.set("state", validated.state);
      if (validated.specialty) qs.set("specialty", validated.specialty);
      qs.set("limit", String(validated.limit));
      if (validated.cursor) qs.set("cursor", validated.cursor);
      const res = await authedFetch(`/prescribers/search?${qs.toString()}`);
      return unwrap(res, PrescriberSearchResponseSchema);
    },

    async getByNpi(npi: Npi): Promise<Prescriber | null> {
      const res = await authedFetch(`/prescribers/${encodeURIComponent(npi)}`);
      if (res.status === 404) return null;
      return unwrap(res, PrescriberSchema);
    },

    async probeHealth() {
      // NOTE: tsconfig.base.json has `exactOptionalPropertyTypes: true`, so we MUST NOT
      // return `{ error: undefined }` on the ok path — the optional property must be
      // OMITTED, not set to undefined. Branch the return type instead.
      const start = performance.now();
      try {
        const res = await fetchImpl(`${baseUrl}/health`, { method: "GET" });
        const latency_ms = Math.round(performance.now() - start);
        return res.ok
          ? { ok: true as const, latency_ms }
          : { ok: false as const, latency_ms, error: `HTTP ${res.status}` };
      } catch (e) {
        return {
          ok: false as const,
          latency_ms: Math.round(performance.now() - start),
          error: (e as Error).message,
        };
      }
    },
  };
}
