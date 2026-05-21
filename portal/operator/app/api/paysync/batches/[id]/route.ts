/**
 * GET /api/paysync/batches/[id] -- single payment batch detail
 *
 * Auth-before-handler, Cache-Control: no-store.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealBatchesClient } from "@infinityrx/contract";
import { handleGetBatch } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeBatchesClient(jwt: string, tenantId: string) {
  return createRealBatchesClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const { id } = await params;
  if (!id) {
    return NextResponse.json(
      { error: { code: "MISSING_ID", message: "Batch id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const client = makeBatchesClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleGetBatch(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch batch" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
