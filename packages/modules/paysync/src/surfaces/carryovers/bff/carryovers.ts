// packages/modules/paysync/src/surfaces/carryovers/bff/carryovers.ts
// Next.js BFF route handlers for the paysync carryovers surface.
// All methods proxy to CarryoversClient from @infinityrx/contract.

import type { CarryoversClient } from "@infinityrx/contract";

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
 * GET /api/paysync/carryovers
 * Proxies to CarryoversClient.list with optional member_id/from_period + cursor pagination.
 */
export async function handleListCarryovers(
  req: BffRequest,
  client: CarryoversClient,
): Promise<BffResponse<Awaited<ReturnType<CarryoversClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const memberId = params.get("member_id");
  const fromPeriod = params.get("from_period");
  const cursorVal = params.get("cursor");
  const listReq: { member_id?: string; from_period?: string; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(memberId !== null ? { member_id: memberId } : {}),
    ...(fromPeriod !== null ? { from_period: fromPeriod } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/carryovers/[id]
 * Proxies to CarryoversClient.get; returns 404 when carryover is null.
 */
export async function handleGetCarryover(
  id: string,
  _req: BffRequest,
  client: CarryoversClient,
): Promise<BffResponse<Awaited<ReturnType<CarryoversClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
