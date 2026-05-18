// src/bff/prescribers.ts
// GET /api/directories/prescribers/[npi]/exclusion-check
// Fan-out: checks cms_opt_out and sam_exclusions for a given NPI.
// Returns { sources: DatasetKey[] } — which exclusion sources match.
//
// Auth pattern: verifyTokenRaw + AccessClaimsSchema.safeParse (Plan A standard).
// Note: exclusion data tables (oig_leie, sam_exclusions, ofac_sdn) live in
// core-platform DB (migration 0008/0012) but have no REST API routes yet.
// This BFF route returns a stub response until backend exclusion API routes land
// (tracked as follow-up for Plan C/D). Returns empty sources array by default.
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyTokenRaw, AccessClaimsSchema, resolveEnvClaim } from "@infinityrx/auth";
import type { DatasetKey } from "../search/schemas.js";

const prescriberDirectoryUrl =
  process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010";

export interface ExclusionCheckResponse {
  npi: string;
  sources: DatasetKey[];
}

export async function getExclusionCheck(req: NextRequest, npi: string): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  // ── Auth gate ─────────────────────────────────────────────────────────────
  const authHeader = req.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null;

  if (!token) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Authentication required", correlation_id: correlationId } },
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
        { error: { code: "UNAUTHORIZED", message: "Invalid token claims", correlation_id: correlationId } },
        { status: 401 },
      );
    }
  } catch {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Invalid token", correlation_id: correlationId } },
      { status: 401 },
    );
  }

  // ── Exclusion fan-out ──────────────────────────────────────────────────────
  // Attempt to query the prescriber-directory alerts endpoint for opt-out status.
  // If the backend has no dedicated exclusion route, return empty sources.
  const matchedSources: DatasetKey[] = [];

  try {
    const alertsUrl = `${prescriberDirectoryUrl}/api/v1/prescribers/monitoring/alerts?npi=${encodeURIComponent(npi)}`;
    const alertsResp = await fetch(alertsUrl, {
      headers: { "x-correlation-id": correlationId },
    });
    if (alertsResp.ok) {
      const body = (await alertsResp.json()) as { alerts?: { alert_type?: string }[] };
      const alerts = body.alerts ?? [];
      // If any alert has type "cms_opt_out" or "sam_exclusion", surface the source
      if (alerts.some((a) => a.alert_type === "cms_opt_out")) matchedSources.push("cms_opt_out");
      if (alerts.some((a) => a.alert_type === "sam_exclusions")) matchedSources.push("sam_exclusions");
      if (alerts.some((a) => a.alert_type === "oig_leie")) matchedSources.push("oig_leie");
    }
    // Backend exclusion API routes not yet implemented — no-op returns empty sources
  } catch {
    // Exclusion check is best-effort; never fail the detail page over it
  }

  const response: ExclusionCheckResponse = { npi, sources: matchedSources };
  const res = NextResponse.json(response);
  res.headers.set("x-correlation-id", correlationId);
  res.headers.set("Cache-Control", "public, s-maxage=300");
  return res;
}
