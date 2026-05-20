// packages/modules/paysync/src/surfaces/journal/bff/journal.ts
// Next.js BFF route handlers for the paysync journal surface.
// Proxies to JournalClient from @infinityrx/contract.

import type { JournalClient } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

/**
 * GET /api/paysync/journal
 * Proxies to JournalClient.list with cursor pagination.
 */
export async function handleListJournal(
  req: BffRequest,
  client: JournalClient,
): Promise<BffResponse<Awaited<ReturnType<JournalClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const cursorVal = params.get("cursor");
  const listReq: { limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/journal/[id]
 * Proxies to JournalClient.get; returns 404 when entry is null.
 */
export async function handleGetJournalEntry(
  id: string,
  _req: BffRequest,
  client: JournalClient,
): Promise<BffResponse<Awaited<ReturnType<JournalClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}

/**
 * POST /api/paysync/journal/verify-chain
 * Proxies to JournalClient.verifyChain.
 * Auditor-only -- enforced server-side (backend returns 403 for other roles).
 * Never serves stale: no-cache on the response.
 */
export async function handleVerifyChain(
  _req: BffRequest,
  client: JournalClient,
): Promise<BffResponse<Awaited<ReturnType<JournalClient["verifyChain"]>>>> {
  const data = await client.verifyChain();
  return { data, status: 200, headers: { "Cache-Control": "no-store" } };
}
