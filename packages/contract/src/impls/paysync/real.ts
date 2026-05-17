// packages/contract/src/impls/paysync/real.ts
// HTTP-backed implementations of UploadsClient + InboxClient.
// Plan A ships the FACTORY shape only — actual HTTP wiring lands in Plan B
// (when the backend Upload resource lands in modules/billing/). All methods
// here are typed-but-not-yet-implemented and throw a clear error so
// downstream callers get a deterministic failure mode if they wire real
// before Plan B is merged.

import type { ClientConfig } from "../../client-base.js";
import { PAYSYNC_INBOX_CACHE_POLICIES, PAYSYNC_UPLOADS_CACHE_POLICIES, type InboxClient, type UploadsClient } from "./client.js";
import type { InboxItem, RbacRole, Upload, UploadListRequest, UploadListResponse } from "./types.js";

const NOT_WIRED = "paysync real client method is not wired yet — lands in SP-1 Plan B";

export function createRealUploadsClient(_config: ClientConfig): UploadsClient {
  return {
    name: "paysync.uploads" as const,
    cachePolicies: PAYSYNC_UPLOADS_CACHE_POLICIES,

    async list(_req: UploadListRequest): Promise<UploadListResponse> {
      throw new Error(NOT_WIRED);
    },

    async get(_id: string): Promise<Upload | null> {
      throw new Error(NOT_WIRED);
    },

    async create(_args: { readonly filename: string; readonly content: Blob | ReadableStream<Uint8Array> }): Promise<Upload> {
      throw new Error(NOT_WIRED);
    },

    async getClaims(_uploadId: string, _opts?: { readonly limit?: number; readonly cursor?: string }): Promise<{ results: Array<Record<string, unknown>>; next_cursor?: string; total: number }> {
      throw new Error(NOT_WIRED);
    },

    async probeHealth() {
      throw new Error(NOT_WIRED);
    },
  };
}

export function createRealInboxClient(_config: ClientConfig): InboxClient {
  return {
    name: "paysync.inbox" as const,
    cachePolicies: PAYSYNC_INBOX_CACHE_POLICIES,

    async list(_role: RbacRole): Promise<InboxItem[]> {
      throw new Error(NOT_WIRED);
    },

    async probeHealth() {
      throw new Error(NOT_WIRED);
    },
  };
}
