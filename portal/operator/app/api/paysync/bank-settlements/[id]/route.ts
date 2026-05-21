/**
 * GET /api/paysync/bank-settlements/[id] -- single bank settlement detail
 *
 * Auth-before-handler, Cache-Control: no-store.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealBankSettlementsClient } from "@infinityrx/contract";
import { handleGetBankSettlement } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeBankSettlementsClient(jwt: string, tenantId: string) {
  return createRealBankSettlementsClient({
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
      { error: { code: "MISSING_ID", message: "Bank settlement id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const client = makeBankSettlementsClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleGetBankSettlement(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch bank settlement" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
