/**
 * GET /api/paysync/bank-settlements -- list bank settlements (status/batch filter + cursor pagination)
 *
 * Auth-before-handler, Cache-Control: no-store — financial data.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealBankSettlementsClient } from "@infinityrx/contract";
import { handleListBankSettlements } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeBankSettlementsClient(jwt: string, tenantId: string) {
  return createRealBankSettlementsClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeBankSettlementsClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListBankSettlements(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list bank settlements" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
