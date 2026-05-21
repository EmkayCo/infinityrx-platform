/**
 * GET /api/paysync/payment-runs -- list payment runs (status/batch filter + cursor pagination)
 *
 * Auth-before-handler, Cache-Control: no-store — financial data.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealPaymentRunsClient } from "@infinityrx/contract";
import { handleListPaymentRuns } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makePaymentRunsClient(jwt: string, tenantId: string) {
  return createRealPaymentRunsClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makePaymentRunsClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListPaymentRuns(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list payment runs" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
