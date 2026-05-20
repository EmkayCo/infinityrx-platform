// packages/modules/paysync/src/surfaces/bank-settlements/bff/bank-settlements.ts
// Next.js BFF route handlers for the paysync bank-settlements surface.
// All methods proxy to BankSettlementsClient from @infinityrx/contract.

import type { BankSettlementsClient, BankSettlementStatus } from "@infinityrx/contract";

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
 * GET /api/paysync/settlements
 * Proxies to BankSettlementsClient.list with optional status/batch_id + cursor pagination.
 */
export async function handleListBankSettlements(
  req: BffRequest,
  client: BankSettlementsClient,
): Promise<BffResponse<Awaited<ReturnType<BankSettlementsClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as BankSettlementStatus | null;
  const batchId = params.get("batch_id");
  const cursorVal = params.get("cursor");
  const listReq: { status?: BankSettlementStatus; batch_id?: string; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(batchId !== null ? { batch_id: batchId } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/settlements/[id]
 * Proxies to BankSettlementsClient.get; returns 404 when settlement is null.
 */
export async function handleGetBankSettlement(
  id: string,
  _req: BffRequest,
  client: BankSettlementsClient,
): Promise<BffResponse<Awaited<ReturnType<BankSettlementsClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
