// portal/operator/app/api/directories/prescribers/search/route.ts
// GET /api/directories/prescribers/search?name=...&page_size=50
// Server-side proxy to prescriber-directory backend.
// Mints a short-lived service JWT from JWT_SECRET (dev) or uses the
// caller's own bearer token (if valid) to forward to the backend.
// The backend runs configure_auth_trust_jwt() so it trusts any validly-
// signed token without a users-table lookup.
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { SignJWT } from "jose";

const PRESCRIBER_URL =
  process.env.PRESCRIBER_DIRECTORY_URL ?? "http://localhost:8010";
const JWT_SECRET = process.env.JWT_SECRET ?? "";
const TENANT_ID = "a0000000-0000-0000-0000-000000000001";
const SERVICE_SUB = "00000000-0000-4000-8000-000000000001";

/** Mint a short-lived HS256 service token the backend will accept. */
async function mintServiceToken(): Promise<string> {
  const secret = new TextEncoder().encode(JWT_SECRET);
  return new SignJWT({
    tid: TENANT_ID,
    roles: ["platform_admin"],
    env: process.env.INFINITYRX_ENV ?? "development",
    typ: "access",
  })
    .setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setSubject(SERVICE_SUB)
    .setIssuedAt()
    .setExpirationTime("1h")
    .setJti(crypto.randomUUID())
    .sign(secret);
}

export async function GET(req: NextRequest): Promise<NextResponse> {
  const correlationId = req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  const name = req.nextUrl.searchParams.get("name") ?? "";
  const pageSize = req.nextUrl.searchParams.get("page_size") ?? "50";

  if (!name || name.length < 2) {
    return NextResponse.json({ results: [], total: 0, page: 1, page_size: Number(pageSize) });
  }

  let token: string;
  try {
    token = await mintServiceToken();
  } catch (err) {
    return NextResponse.json(
      { error: { code: "SERVICE_TOKEN_ERROR", message: "Failed to mint service token", correlation_id: correlationId } },
      { status: 500 },
    );
  }

  const backendUrl = `${PRESCRIBER_URL}/api/v1/prescribers/search?name=${encodeURIComponent(name)}&page_size=${encodeURIComponent(pageSize)}`;

  try {
    const resp = await fetch(backendUrl, {
      headers: {
        "Authorization": `Bearer ${token}`,
        "x-tenant-id": TENANT_ID,
        "x-correlation-id": correlationId,
      },
    });

    if (!resp.ok) {
      const body = (await resp.json().catch(() => ({}))) as Record<string, unknown>;
      return NextResponse.json(
        { error: { code: "UPSTREAM_ERROR", message: "Prescriber search unavailable", correlation_id: correlationId, upstream: body } },
        { status: resp.status },
      );
    }

    const data = (await resp.json()) as Record<string, unknown>;
    const res = NextResponse.json(data);
    res.headers.set("x-correlation-id", correlationId);
    res.headers.set("Cache-Control", "public, s-maxage=30");
    return res;
  } catch {
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Prescriber search request failed", correlation_id: correlationId } },
      { status: 502 },
    );
  }
}
