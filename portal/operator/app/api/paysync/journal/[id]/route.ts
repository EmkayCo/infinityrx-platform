/**
 * GET /api/paysync/journal/[id] -- single journal entry detail
 *
 * Auth-before-handler, Cache-Control: no-store — financial audit hash-chain.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealJournalClient } from "@infinityrx/contract";
import { handleGetJournalEntry } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeJournalClient(jwt: string, tenantId: string) {
  return createRealJournalClient({
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
      { error: { code: "MISSING_ID", message: "Journal entry id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const client = makeJournalClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleGetJournalEntry(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch journal entry" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
