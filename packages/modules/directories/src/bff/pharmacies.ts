// src/bff/pharmacies.ts
// GET /api/directories/pharmacies/stats
// Proxies pharmacy stats from pharmacy-directory backend, passing mandatory
// ?x-tenant-id={tid} (required by pharmacy-directory router.py line 442).
//
// Auth pattern: verifyTokenRaw + AccessClaimsSchema.safeParse (Plan A standard).
// tid extracted from JWT claims.tid — UUID string.
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyTokenRaw, AccessClaimsSchema, resolveEnvClaim } from "@infinityrx/auth";

const pharmacyDirectoryUrl =
  process.env.PHARMACY_DIRECTORY_URL ?? "http://pharmacy-directory:8009";

export async function GET(req: NextRequest): Promise<NextResponse> {
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

  let tid: string;
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
    tid = parsed.data.tid;
  } catch {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Invalid token", correlation_id: correlationId } },
      { status: 401 },
    );
  }

  // ── Proxy to pharmacy-directory stats (mandatory x-tenant-id param) ───────
  // pharmacy-directory router.py:442: tenant_id: Annotated[uuid.UUID, Query(alias="x-tenant-id")]
  const backendUrl = `${pharmacyDirectoryUrl}/api/v1/pharmacies/stats?x-tenant-id=${encodeURIComponent(tid)}`;

  try {
    const backendResp = await fetch(backendUrl, {
      headers: {
        "x-correlation-id": correlationId,
        "content-type": "application/json",
      },
    });

    if (!backendResp.ok) {
      const body = (await backendResp.json().catch(() => ({}))) as Record<string, unknown>;
      const res = NextResponse.json(
        { error: { code: "UPSTREAM_ERROR", message: "Pharmacy stats unavailable", correlation_id: correlationId, upstream: body } },
        { status: backendResp.status },
      );
      res.headers.set("x-correlation-id", correlationId);
      return res;
    }

    const data = (await backendResp.json()) as Record<string, unknown>;
    const res = NextResponse.json(data);
    res.headers.set("x-correlation-id", correlationId);
    res.headers.set("Cache-Control", "public, s-maxage=60");
    return res;
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Pharmacy stats request failed", correlation_id: correlationId } },
      { status: 502 },
    );
  }
}
