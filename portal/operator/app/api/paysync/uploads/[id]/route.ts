/**
 * GET /api/paysync/uploads/[id]         -- single upload detail
 * GET /api/paysync/uploads/[id]?claims  -- (claims fetched via UploadClaimViewer
 *                                           which calls /api/paysync/uploads/[id]/claims)
 *
 * Auth-before-parse, Cache-Control: no-store, no PHI on error paths.
 */
import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealUploadsClient } from "@infinityrx/contract";
import { handleGetUpload } from "@infinityrx/module-paysync/bff";

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
  // AUTH FIRST.
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
    const result = await handleGetUpload(id, bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch upload" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
