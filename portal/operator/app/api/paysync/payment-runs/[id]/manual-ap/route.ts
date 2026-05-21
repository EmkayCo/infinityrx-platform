/**
 * POST /api/paysync/payment-runs/[id]/manual-ap -- submit a manual AP entry
 *
 * RBAC gate: session.roles must include "billing_approver" (or "admin").
 * Enforced here in the BFF before the backend call — defense-in-depth; the
 * backend also enforces RBAC, but we gate early to avoid unnecessary upstream
 * calls and to return a clear 403 with an actionable error code.
 *
 * Auth-before-body: resolveSession() runs before JSON is parsed.
 * Cache-Control: no-store — money mutation, audit-bearing.
 */
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS, forwardJson } from "@/lib/bff";

const BILLING_BASE = BACKENDS.billing;

// Roles that may submit manual AP entries.
const MANUAL_AP_ROLES = new Set(["billing_approver", "admin", "operator_admin"]);

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  // AUTH FIRST — before reading body.
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  // RBAC gate — manual AP is approver-only.
  const hasPermission = session.roles.some((role) => MANUAL_AP_ROLES.has(role));
  if (!hasPermission) {
    return NextResponse.json(
      {
        error: {
          code: "FORBIDDEN",
          message: "Manual AP entry requires billing_approver or admin role",
        },
      },
      { status: 403, headers: { "Cache-Control": "no-store" } }
    );
  }

  const { id } = await params;
  if (!id) {
    return NextResponse.json(
      { error: { code: "MISSING_ID", message: "Payment run id is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { error: { code: "INVALID_BODY", message: "Expected JSON body" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const url = `${BILLING_BASE}/api/v1/billing/payment-runs/${encodeURIComponent(id)}/manual-ap`;
  const result = await forwardJson<unknown>(url, session, {
    method: "POST",
    body,
    timeoutMs: 8000, // write-path, audit-bearing
  });

  if (!result.ok) {
    const status = result.failure.reason === "UPSTREAM_ERROR" ? result.failure.status : 502;
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to submit manual AP entry" } },
      { status: status >= 400 ? status : 502, headers: { "Cache-Control": "no-store" } }
    );
  }

  return NextResponse.json(result.data, {
    status: 200,
    headers: { "Cache-Control": "no-store" },
  });
}
