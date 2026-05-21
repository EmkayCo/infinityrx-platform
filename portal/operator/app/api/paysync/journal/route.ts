/**
 * GET /api/paysync/journal -- list journal entries (cursor pagination)
 *
 * Auth-before-handler, Cache-Control: no-store — financial audit hash-chain;
 * never serve stale journal data.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealJournalClient } from "@infinityrx/contract";
import { handleListJournal } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeJournalClient(jwt: string, tenantId: string) {
  return createRealJournalClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeJournalClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListJournal(bffReq, client);
    // Cache-Control: no-store is non-negotiable for financial audit hash-chain.
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list journal entries" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
