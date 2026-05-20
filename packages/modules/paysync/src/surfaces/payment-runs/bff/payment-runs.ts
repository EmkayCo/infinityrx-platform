// packages/modules/paysync/src/surfaces/payment-runs/bff/payment-runs.ts
// Next.js BFF route handlers for the paysync payment-runs surface.

import type { PaymentRunsClient, PaymentRunStatus } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

/** GET /api/paysync/payment-runs */
export async function handleListPaymentRuns(
  req: BffRequest,
  client: PaymentRunsClient,
): Promise<BffResponse<Awaited<ReturnType<PaymentRunsClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as PaymentRunStatus | null;
  const batchIdVal = params.get("batch_id");
  const cursorVal = params.get("cursor");
  const listReq: { status?: PaymentRunStatus; batch_id?: string; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(batchIdVal !== null ? { batch_id: batchIdVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/** GET /api/paysync/payment-runs/[id] */
export async function handleGetPaymentRun(
  id: string,
  _req: BffRequest,
  client: PaymentRunsClient,
): Promise<BffResponse<Awaited<ReturnType<PaymentRunsClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
