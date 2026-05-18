// src/bff/search.ts
// GET /api/directories/search?q=...&limit=20
// Validates JWT (packages/auth), fans out to backends, returns ranked results.
//
// Auth note: uses verifyTokenRaw + AccessClaimsSchema.safeParse rather than
// verifyAccessToken, because verifyAccessToken requires a RevocationRepo
// (SD-1 §8 step 9 revocation check). The BFF route handler is a stateless
// Next.js route — revocation checking is performed by the shell middleware
// (packages/shell) before the request reaches module BFF routes. Using
// verifyTokenRaw here performs steps 1–8 (signature, claims, iss, aud, env,
// typ, exp) which is correct for a second-layer route-handler auth gate.
import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { verifyTokenRaw, AccessClaimsSchema } from "@infinityrx/auth";
import { resolveEnvClaim } from "@infinityrx/auth";
import { SearchResponseSchema } from "../search/schemas.js";
import { FederatedSearchClient } from "../search/FederatedSearchClient.js";

const client = new FederatedSearchClient({
  prescriberDirectoryUrl:
    process.env.PRESCRIBER_DIRECTORY_URL ?? "http://prescriber-directory:8010",
  pharmacyDirectoryUrl:
    process.env.PHARMACY_DIRECTORY_URL ?? "http://pharmacy-directory:8009",
  drugDatabaseUrl:
    process.env.DRUG_DATABASE_URL ?? "http://drug-database:8011",
  budgetMs: 300,
  limitPerDataset: 5,
});

export async function GET(req: NextRequest): Promise<NextResponse> {
  const correlationId =
    req.headers.get("x-correlation-id") ?? crypto.randomUUID();

  // ── Auth gate ────────────────────────────────────────────────────────────
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

  // ── Query handling ───────────────────────────────────────────────────────
  const q = req.nextUrl.searchParams.get("q")?.trim() ?? "";

  if (!q || q.length < 2) {
    const res = NextResponse.json(
      SearchResponseSchema.parse({
        results: [],
        is_partial: false,
        timed_out_datasets: [],
      }),
    );
    res.headers.set("x-correlation-id", correlationId);
    return res;
  }

  const { results, timedOutDatasets } = await client.search(q, correlationId);
  const limited = results.slice(0, 20);

  const body = SearchResponseSchema.parse({
    results: limited,
    is_partial: timedOutDatasets.length > 0,
    timed_out_datasets: timedOutDatasets,
  });

  // Cache: 30s public (reference data, not PHI — no Cache-Control: no-store needed)
  const res = NextResponse.json(body);
  res.headers.set("Cache-Control", "public, s-maxage=30");
  res.headers.set("x-correlation-id", correlationId);
  return res;
}
