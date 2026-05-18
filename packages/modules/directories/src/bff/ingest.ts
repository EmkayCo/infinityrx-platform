// src/bff/ingest.ts
// BFF proxy routes for the ingestion console (SP-2 Plan C).
//
// Auth pattern: verifyTokenRaw + AccessClaimsSchema.safeParse — same as Plan A
// (stateless route handler; shell middleware handles revocation checking).
//
// SSRF guard: all {source} path parameters are validated against TRIGGERABLE_SOURCES
// allowlist before proxying. Any source not in the set returns 404 without
// forwarding the request to the backend. This is a security control (100% coverage
// required per Plan C testing requirements).
//
// Ingestion backend is hosted by prescriber-directory (port 8010 per Plan A §10.3).
// The backend router has no auth dependency — BFF is the auth gate.
//
// Exported named handlers follow Next.js App Router conventions so portal route
// files can re-export them directly.

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyTokenRaw, AccessClaimsSchema, resolveEnvClaim } from "@infinityrx/auth";

const INGESTION_BASE =
  process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010";

// ---------------------------------------------------------------------------
// SSRF guard: only these source keys may be triggered/cancelled via BFF.
// bpg = live external API (no loader). fdb = B9-blocked. relay-health = not a loader.
// nppes_monthly + nppes_deactivation are sub-mode triggers for the NPPES source.
// ---------------------------------------------------------------------------

export const TRIGGERABLE_SOURCES: ReadonlySet<string> = new Set([
  "nppes",
  "nppes_monthly",
  "nppes_deactivation",
  "ncpdp",
  "fda_ndc",
  "fda_orange_book",
  "fda_purple_book",
  "fda_drug_shortages",
  "fda_rems",
  "rxnorm",
  "hcpcs",
  "icd10_cm",
  "cms_asp",
  "cms_nadac",
  "state_medicaid_bins",
  "cms_opt_out",
  "ofac_sdn",
  "sam_exclusions",
  "oig_leie",
  "dea_registrations",
]);

// ---------------------------------------------------------------------------
// Auth helper — shared across all handlers in this file.
// Returns null on success (claims parsed), or a 401 NextResponse on failure.
// ---------------------------------------------------------------------------

async function _verifyAuth(
  req: NextRequest,
  correlationId: string,
): Promise<{ ok: true } | NextResponse> {
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

  return { ok: true };
}

// ---------------------------------------------------------------------------
// Source guard helper — validates source against TRIGGERABLE_SOURCES.
// Returns null on valid source, or a 404 NextResponse on invalid source.
// ---------------------------------------------------------------------------

function _guardSource(
  source: string,
  correlationId: string,
): NextResponse | null {
  if (!TRIGGERABLE_SOURCES.has(source)) {
    return NextResponse.json(
      {
        error: {
          code: "SOURCE_NOT_FOUND",
          message: `Source '${source}' is not a recognized triggerable ingestion source`,
          correlation_id: correlationId,
        },
      },
      { status: 404 },
    );
  }
  return null;
}

// ---------------------------------------------------------------------------
// POST /api/directories/ingest/[source]/trigger
// Proxies to POST http://prescriber-directory:8010/api/v1/data-ingestion/{source}/trigger
// ---------------------------------------------------------------------------

export async function triggerRun(
  req: NextRequest,
  source: string,
): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;

  const sourceGuard = _guardSource(source, correlationId);
  if (sourceGuard) return sourceGuard;

  const body = await req.json().catch(() => ({ run_type: "manual_trigger" }));

  const backendResp = await fetch(
    `${INGESTION_BASE}/api/v1/data-ingestion/${source}/trigger`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-correlation-id": correlationId,
      },
      body: JSON.stringify(body),
    },
  );

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}

// ---------------------------------------------------------------------------
// GET /api/directories/ingest/[source]/history
// Proxies to GET http://prescriber-directory:8010/api/v1/data-ingestion/{source}/history
// ---------------------------------------------------------------------------

export async function getHistory(
  req: NextRequest,
  source: string,
): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;

  const sourceGuard = _guardSource(source, correlationId);
  if (sourceGuard) return sourceGuard;

  const limit = req.nextUrl.searchParams.get("limit") ?? "50";
  const backendResp = await fetch(
    `${INGESTION_BASE}/api/v1/data-ingestion/${source}/history?limit=${limit}`,
    {
      headers: { "x-correlation-id": correlationId },
    },
  );

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}

// ---------------------------------------------------------------------------
// GET /api/directories/ingest/runs/[run_id]
// Proxies to GET http://prescriber-directory:8010/api/v1/data-ingestion/runs/{run_id}
// run_id is a UUID — no source allowlist check needed (run IDs are server-generated).
// ---------------------------------------------------------------------------

export async function getRunDetail(
  req: NextRequest,
  runId: string,
): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;

  const backendResp = await fetch(
    `${INGESTION_BASE}/api/v1/data-ingestion/runs/${runId}`,
    {
      headers: { "x-correlation-id": correlationId },
    },
  );

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}

// ---------------------------------------------------------------------------
// POST /api/directories/ingest/[source]/cancel
// Proxies to POST http://prescriber-directory:8010/api/v1/data-ingestion/{source}/cancel
// ---------------------------------------------------------------------------

export async function cancelRun(
  req: NextRequest,
  source: string,
): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;

  const sourceGuard = _guardSource(source, correlationId);
  if (sourceGuard) return sourceGuard;

  const body = await req.json().catch(() => ({}));

  const backendResp = await fetch(
    `${INGESTION_BASE}/api/v1/data-ingestion/${source}/cancel`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-correlation-id": correlationId,
      },
      body: JSON.stringify(body),
    },
  );

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}

// ---------------------------------------------------------------------------
// GET /api/directories/ingest/status
// Proxies to GET http://prescriber-directory:8010/api/v1/data-ingestion/status
// Returns SourceStatus[] for the ingestion console table.
// ---------------------------------------------------------------------------

export async function getAllStatus(req: NextRequest): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const authResult = await _verifyAuth(req, correlationId);
  if (authResult instanceof NextResponse) return authResult;

  const backendResp = await fetch(
    `${INGESTION_BASE}/api/v1/data-ingestion/status`,
    {
      headers: { "x-correlation-id": correlationId },
    },
  );

  const data = await backendResp.json();
  const res = NextResponse.json(data, { status: backendResp.status });
  res.headers.set("x-correlation-id", correlationId);
  return res;
}
