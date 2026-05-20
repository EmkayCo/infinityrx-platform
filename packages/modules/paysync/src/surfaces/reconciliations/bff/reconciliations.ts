// packages/modules/paysync/src/surfaces/reconciliations/bff/reconciliations.ts
// Next.js BFF route handlers for the paysync reconciliations surface.
// All methods proxy to ReconciliationsClient from @infinityrx/contract.

import type { ReconciliationsClient, ReconciliationStatus } from "@infinityrx/contract";

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
 * GET /api/paysync/reconcile
 * Proxies to ReconciliationsClient.list with optional status + cursor pagination.
 */
export async function handleListReconciliations(
  req: BffRequest,
  client: ReconciliationsClient,
): Promise<BffResponse<Awaited<ReturnType<ReconciliationsClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as ReconciliationStatus | null;
  const cursorVal = params.get("cursor");
  const listReq: { status?: ReconciliationStatus; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/reconcile/[id]
 * Proxies to ReconciliationsClient.get; returns 404 when reconciliation is null.
 */
export async function handleGetReconciliation(
  id: string,
  _req: BffRequest,
  client: ReconciliationsClient,
): Promise<BffResponse<Awaited<ReturnType<ReconciliationsClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
