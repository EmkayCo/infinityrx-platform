/**
 * GET /api/paysync/batches -- list payment batches (status filter + cursor pagination)
 *
 * Auth-before-handler, Cache-Control: no-store — financial data.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealBatchesClient } from "@infinityrx/contract";
import { handleListBatches } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeBatchesClient(jwt: string, tenantId: string) {
  return createRealBatchesClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeBatchesClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListBatches(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list batches" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
