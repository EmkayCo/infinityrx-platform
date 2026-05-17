// packages/modules/paysync/src/surfaces/invoices/bff/invoices.ts
// Next.js BFF route handlers for the paysync invoices surface.

import type { InvoicesClient, InvoiceStatus } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

/** GET /api/paysync/invoices */
export async function handleListInvoices(
  req: BffRequest,
  client: InvoicesClient,
): Promise<BffResponse<Awaited<ReturnType<InvoicesClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const statusVal = params.get("status") as InvoiceStatus | null;
  const clientIdVal = params.get("client_id");
  const cursorVal = params.get("cursor");
  const listReq: { status?: InvoiceStatus; client_id?: string; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(statusVal !== null ? { status: statusVal } : {}),
    ...(clientIdVal !== null ? { client_id: clientIdVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/** GET /api/paysync/invoices/[id] */
export async function handleGetInvoice(
  id: string,
  _req: BffRequest,
  client: InvoicesClient,
): Promise<BffResponse<Awaited<ReturnType<InvoicesClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}
