// src/bff/audit.ts
// BFF proxy for the audit log viewer (SP-2 Plan D Task D-4).
//
// Auth pattern: verifyTokenRaw + AccessClaimsSchema.safeParse — same as Plan C.
//
// This route proxies to core-platform's GET /api/v1/audit endpoint, which
// requires audit:read permission. The original JWT is forwarded to core-platform
// so it can enforce its own permission check server-side.
//
// IMPORTANT (codex BLOCK-2 addressed): Not all roles have audit:read.
// core-platform will return 403 if the JWT user lacks audit:read. The BFF
// forwards this 403 to the frontend — do NOT treat it as a BFF error.
// The AuditLogPage renders an appropriate "no access" state for 403.
//
// Pre-applied filters:
//   module=prescriber_directory  — ingestion requests routed through prescriber-directory
//   date_from=now-90d            — 90-day window
// These filters narrow the audit log to ingestion-relevant events.

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import {
  verifyTokenRaw,
  AccessClaimsSchema,
  resolveEnvClaim,
} from "@infinityrx/auth";

const CORE_PLATFORM_BASE =
  process.env.CORE_PLATFORM_URL ?? "http://core-platform:8000";

// 90-day window — provides a meaningful history window for ingestion audits.
const AUDIT_WINDOW_DAYS = 90;

// ---------------------------------------------------------------------------
// Auth helper — returns the raw token (for forwarding) or a 401 response.
// ---------------------------------------------------------------------------

type AuthResult = { ok: true; token: string } | NextResponse;

async function _verifyAuth(
  req: NextRequest,
  correlationId: string,
): Promise<AuthResult> {
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;

  if (!token) {
    return NextResponse.json(
      {
        error: {
          code: "UNAUTHORIZED",
          message: "Authentication required",
          correlation_id: correlationId,
        },
      },
      { status: 401 },
    );
  }

  try {
    const env = resolveEnvClaim(process.env.INFINITYRX_ENV ?? "development");
    const secret = process.env.JWT_SECRET ?? "";
    const raw = await verifyTokenRaw(token, secret, env);
    const parsed = AccessClaimsSchema.safeParse(raw);
    if (!parsed.success) {
      return NextResponse.json(
        {
          error: {
            code: "UNAUTHORIZED",
            message: "Invalid token claims",
            correlation_id: correlationId,
          },
        },
        { status: 401 },
      );
    }
    // Return the raw token for forwarding to core-platform.
    return { ok: true, token };
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "UNAUTHORIZED",
          message: "Invalid token",
          correlation_id: correlationId,
        },
      },
      { status: 401 },
    );
  }
}

// ---------------------------------------------------------------------------
// GET /api/directories/audit?limit=50&offset=0
// Proxies to GET http://core-platform:8000/api/v1/audit with pre-applied
// ingestion filters. Forwards the original JWT so core-platform enforces
// audit:read permission. Returns 403 as-is if user lacks audit:read.
// ---------------------------------------------------------------------------

export async function getAuditLog(req: NextRequest): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;
  const { token } = authResult;

  // Validated query params — limit and offset only.
  const rawLimit = req.nextUrl.searchParams.get("limit") ?? "50";
  const rawOffset = req.nextUrl.searchParams.get("offset") ?? "0";
  // Validate to prevent query injection — positive integers only.
  const limit = /^\d{1,5}$/.test(rawLimit) ? rawLimit : "50";
  const offset = /^\d{1,10}$/.test(rawOffset) ? rawOffset : "0";

  // Pre-apply 90-day window.
  const dateFrom = new Date(
    Date.now() - AUDIT_WINDOW_DAYS * 24 * 60 * 60 * 1000,
  ).toISOString();

  // Filter to ingestion-related module (prescriber-directory hosts the ingestion router
  // after Plan C mount). action filtering uses a prefix match on the backend.
  const backendUrl = new URL(`${CORE_PLATFORM_BASE}/api/v1/audit`);
  backendUrl.searchParams.set("module", "prescriber_directory");
  backendUrl.searchParams.set("date_from", dateFrom);
  backendUrl.searchParams.set("limit", limit);
  backendUrl.searchParams.set("offset", offset);

  const backendResp = await fetch(backendUrl.toString(), {
    headers: {
      // Forward original JWT — core-platform enforces audit:read permission.
      Authorization: `Bearer ${token}`,
      "x-correlation-id": correlationId,
    },
  });

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}
