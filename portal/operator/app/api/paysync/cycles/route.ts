/**
 * GET /api/paysync/cycles -- list billing cycles (status filter + cursor pagination)
 *
 * Auth-before-handler: resolveSession() runs before any backend call.
 * Cache-Control: no-store on all responses — financial data.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealCyclesClient } from "@infinityrx/contract";
import { handleListCycles } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeCyclesClient(jwt: string, tenantId: string) {
  return createRealCyclesClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeCyclesClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListCycles(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list cycles" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
