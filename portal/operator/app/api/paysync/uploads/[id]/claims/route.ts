/**
 * GET /api/paysync/uploads/[id]/claims -- paginated claim list for one upload.
 * Auth-before-parse, Cache-Control: no-store (claims contain PHI-adjacent member_id).
 */
import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealUploadsClient } from "@infinityrx/contract";
import { handleGetUploadClaims } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

function makeUploadsClient(jwt: string, tenantId: string) {
  return createRealUploadsClient({
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
      { error: { code: "MISSING_ID", message: "Upload id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const client = makeUploadsClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleGetUploadClaims(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch claims" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
