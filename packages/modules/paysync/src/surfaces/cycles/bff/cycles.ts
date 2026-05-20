// packages/modules/paysync/src/surfaces/cycles/bff/cycles.ts
// Next.js BFF route handlers for the paysync cycles surface.
// All methods proxy to CyclesClient from @infinityrx/contract.

import type { CyclesClient, CycleStatus } from "@infinityrx/contract";

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
 * GET /api/paysync/cycles
 * Proxies to CyclesClient.list with optional status filter + cursor pagination.
 */
export async function handleListCycles(
  req: BffRequest,
  client: CyclesClient,
): Promise<BffResponse<Awaited<ReturnType<CyclesClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as CycleStatus | null;
  const cursorVal = params.get("cursor");
  const listReq: { status?: CycleStatus; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/cycles/[id]
 * Proxies to CyclesClient.get; returns 404 when cycle is null.
 */
export async function handleGetCycle(
  id: string,
  _req: BffRequest,
  client: CyclesClient,
): Promise<BffResponse<Awaited<ReturnType<CyclesClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}

/**
 * POST /api/paysync/cycles/[id]/close
 * Approver-only action; RBAC enforced server-side.
 * Proxies to CyclesClient.close.
 */
export async function handleCloseCycle(
  id: string,
  _req: BffRequest,
  client: CyclesClient,
): Promise<BffResponse<Awaited<ReturnType<CyclesClient["close"]>>>> {
  const data = await client.close(id);
  return { data, status: 200, headers: {} };
}
