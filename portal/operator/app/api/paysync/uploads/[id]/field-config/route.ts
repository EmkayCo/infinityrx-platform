/**
 * GET /api/paysync/uploads/[id]/field-config          -- load saved config
 * PUT /api/paysync/uploads/[id]/field-config          -- save config
 * GET /api/paysync/uploads/[id]/field-config?samples  -- get sample values
 *
 * Auth: resolveSession() + backendHeaders forwarding. Cache-Control: no-store.
 */
import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS, forwardJson } from "@/lib/bff";

const BILLING_BASE = BACKENDS.billing;

function billingUrl(uploadId: string, path: string): string {
  return `${BILLING_BASE}/api/v1/billing/uploads/${encodeURIComponent(uploadId)}/field-config${path}`;
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

  const wantSamples = request.nextUrl.searchParams.has("samples");
  const backendPath = wantSamples ? "/sample-values" : "";
  const url = billingUrl(id, backendPath);

  const result = await forwardJson<unknown>(url, session);
  if (!result.ok) {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to fetch field config" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
  return NextResponse.json(result.data, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}

export async function PUT(
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

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: { code: "INVALID_BODY", message: "Invalid JSON body" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const url = billingUrl(id, "");
  const result = await forwardJson<unknown>(url, session, {
    method: "PUT",
    body,
    timeoutMs: 8000,
  });
  if (!result.ok) {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to save field config" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
  return NextResponse.json(result.data, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}