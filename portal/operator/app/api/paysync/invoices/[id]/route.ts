/**
 * GET /api/paysync/invoices/[id] -- single invoice detail
 *
 * Auth-before-handler, Cache-Control: no-store.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealInvoicesClient } from "@infinityrx/contract";
import { handleGetInvoice } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeInvoicesClient(jwt: string, tenantId: string) {
  return createRealInvoicesClient({
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
      { error: { code: "MISSING_ID", message: "Invoice id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const client = makeInvoicesClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleGetInvoice(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch invoice" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
