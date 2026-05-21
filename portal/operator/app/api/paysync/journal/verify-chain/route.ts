/**
 * POST /api/paysync/journal/verify-chain -- trigger hash-chain integrity verification
 *
 * Auditor-only operation. Backend enforces RBAC; BFF forwards the JWT and lets
 * the billing backend return 403 for non-auditor roles (backend is the RBAC source
 * of truth for this audit-critical operation).
 *
 * Cache-Control: no-store — never serve a cached verification result.
 * This is an audit-bearing write path; timeoutMs = 8000.
 */
export const runtime = "nodejs";

import { NextResponse } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealJournalClient } from "@infinityrx/contract";
import { handleVerifyChain } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeJournalClient(jwt: string, tenantId: string) {
  return createRealJournalClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function POST() {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeJournalClient(session.jwt, session.tenantId);
  const bffReq = { headers: {} };

  try {
    const result = await handleVerifyChain(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Hash-chain verification failed" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
