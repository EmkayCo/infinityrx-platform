// packages/contract/src/impls/paysync/real.ts
// HTTP-backed implementations of UploadsClient, InboxClient, and CyclesClient.
// Plan B wires the real HTTP calls (Plan A shipped typed-but-not-wired stubs).
// Pattern mirrors prescriber-directory/real.ts: authedFetch helper + zod unwrap.

import type { ClientConfig } from "../../client-base.js";
import { isErrorEnvelope } from "../../error-envelope.js";
import {
  PAYSYNC_CYCLES_CACHE_POLICIES,
  PAYSYNC_INBOX_CACHE_POLICIES,
  PAYSYNC_UPLOADS_CACHE_POLICIES,
  type CyclesClient,
  type InboxClient,
  type UploadsClient,
} from "./client.js";
import {
  CycleListResponseSchema,
  CycleSchema,
  UploadListResponseSchema,
  UploadSchema,
  type Cycle,
  type CycleListResponse,
  type CycleStatus,
  type InboxItem,
  type RbacRole,
  type Upload,
  type UploadListRequest,
  type UploadListResponse,
} from "./types.js";

class PaysyncClientError extends Error {
  constructor(public readonly code: string, message: string, public readonly correlationId?: string) {
    super(message);
    this.name = "PaysyncClientError";
  }
}

function makeAuthedFetch(config: ClientConfig) {
  const baseUrl = (config.baseUrl ?? "").replace(/\/$/, "");
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
        throw new PaysyncClientError(body.error.code, body.error.message, body.error.correlation_id);
      }
      throw new Error(`Unexpected error shape: HTTP ${res.status}`);
    }
    return schema.parse(body);
  }

  async function probeHealth(fetchBase: typeof fetchImpl): Promise<{ ok: boolean; latency_ms: number; error?: string }> {
    const start = performance.now();
    try {
      const res = await fetchBase(`${baseUrl}/health`, { method: "GET" });
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
  }

  return { authedFetch, unwrap, probeHealth: () => probeHealth(fetchImpl) };
}

export function createRealUploadsClient(config: ClientConfig): UploadsClient {
  if (!config.baseUrl) {
    throw new Error("createRealUploadsClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.uploads" as const,
    cachePolicies: PAYSYNC_UPLOADS_CACHE_POLICIES,

    async list(req: UploadListRequest): Promise<UploadListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/uploads?${qs.toString()}`);
      return unwrap(res, UploadListResponseSchema);
    },

    async get(id: string): Promise<Upload | null> {
      const res = await authedFetch(`/api/v1/billing/uploads/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, UploadSchema);
    },

    async create(args: { readonly filename: string; readonly content: Blob | ReadableStream<Uint8Array> }): Promise<Upload> {
      const body = new FormData();
      const blob = args.content instanceof Blob ? args.content : new Blob([]);
      body.append("file", blob, args.filename);
      // multipart — do NOT set Content-Type (browser/fetch sets it with boundary)
      const token = await config.getAuthToken();
      const fetchImpl = config.fetch ?? globalThis.fetch;
      const baseUrl = (config.baseUrl ?? "").replace(/\/$/, "");
      const correlationHeader = config.correlationHeader ?? "x-correlation-id";
      const headers = new Headers();
      headers.set("Authorization", `Bearer ${token}`);
      headers.set(correlationHeader, crypto.randomUUID());
      const res = await fetchImpl(`${baseUrl}/api/v1/billing/uploads`, {
        method: "POST",
        headers,
        body,
      });
      if (!res.ok) {
        const errBody = await res.json() as unknown;
        if (isErrorEnvelope(errBody)) {
          throw new PaysyncClientError(errBody.error.code, errBody.error.message, errBody.error.correlation_id);
        }
        throw new Error(`Upload create failed: HTTP ${res.status}`);
      }
      return UploadSchema.parse(await res.json());
    },

    async getClaims(uploadId: string, opts?: { readonly limit?: number; readonly cursor?: string }): Promise<{ results: Array<Record<string, unknown>>; next_cursor?: string; total: number }> {
      const qs = new URLSearchParams();
      if (opts?.limit) qs.set("limit", String(opts.limit));
      if (opts?.cursor) qs.set("cursor", opts.cursor);
      const res = await authedFetch(`/api/v1/billing/uploads/${encodeURIComponent(uploadId)}/claims?${qs.toString()}`);
      const body = await res.json() as { results: Array<Record<string, unknown>>; next_cursor?: string; total: number };
      return body;
    },

    probeHealth,
  };
}

export function createRealInboxClient(config: ClientConfig): InboxClient {
  if (!config.baseUrl) {
    throw new Error("createRealInboxClient: baseUrl is required");
  }
  const { authedFetch, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.inbox" as const,
    cachePolicies: PAYSYNC_INBOX_CACHE_POLICIES,

    async list(role: RbacRole): Promise<InboxItem[]> {
      const qs = new URLSearchParams({ role });
      const res = await authedFetch(`/api/v1/billing/inbox?${qs.toString()}`);
      if (!res.ok) {
        throw new Error(`Inbox list failed: HTTP ${res.status}`);
      }
      return (await res.json()) as InboxItem[];
    },

    probeHealth,
  };
}

export function createRealCyclesClient(config: ClientConfig): CyclesClient {
  if (!config.baseUrl) {
    throw new Error("createRealCyclesClient: baseUrl is required");
  }
  const { authedFetch, unwrap, probeHealth } = makeAuthedFetch(config);

  return {
    name: "paysync.cycles" as const,
    cachePolicies: PAYSYNC_CYCLES_CACHE_POLICIES,

    async list(req: { status?: CycleStatus; limit?: number; cursor?: string }): Promise<CycleListResponse> {
      const qs = new URLSearchParams();
      if (req.status) qs.set("status", req.status);
      qs.set("limit", String(req.limit ?? 50));
      if (req.cursor) qs.set("cursor", req.cursor);
      const res = await authedFetch(`/api/v1/billing/cycles?${qs.toString()}`);
      return unwrap(res, CycleListResponseSchema);
    },

    async get(id: string): Promise<Cycle | null> {
      const res = await authedFetch(`/api/v1/billing/cycles/${encodeURIComponent(id)}`);
      if (res.status === 404) return null;
      return unwrap(res, CycleSchema);
    },

    async close(id: string): Promise<Cycle> {
      const res = await authedFetch(`/api/v1/billing/cycles/${encodeURIComponent(id)}/close`, {
        method: "POST",
      });
      return unwrap(res, CycleSchema);
    },

    probeHealth,
  };
}
