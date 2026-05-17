// packages/modules/paysync/src/surfaces/batches/bff/batches.ts
// Next.js BFF route handlers for the paysync batches surface.
// All methods proxy to BatchesClient from @infinityrx/contract.

import type { BatchesClient, BatchStatus } from "@infinityrx/contract";

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
 * GET /api/paysync/batches
 * Proxies to BatchesClient.list with optional status filter + cursor pagination.
 */
export async function handleListBatches(
  req: BffRequest,
  client: BatchesClient,
): Promise<BffResponse<Awaited<ReturnType<BatchesClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as BatchStatus | null;
  const cursorVal = params.get("cursor");
  const listReq: { status?: BatchStatus; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/batches/[id]
 * Proxies to BatchesClient.get; returns 404 when batch is null.
 */
export async function handleGetBatch(
  id: string,
  _req: BffRequest,
  client: BatchesClient,
): Promise<BffResponse<Awaited<ReturnType<BatchesClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
