/**
 * GET  /api/paysync/uploads  -- list uploads (cursor-paginated, status filter)
 * POST /api/paysync/uploads  -- create upload (multipart form-data, streaming)
 *
 * Auth-before-body: resolveSession() runs before ANY body access.
 * Unauthenticated requests are rejected immediately, before the body is read
 * (multipart DoS guard).
 *
 * POST streaming passthrough:
 *   request.formData() buffers the entire body in Node.js and triggers Next.js
 *   body-size limits (~4-10 MB) -- unusable for 20-100 MB CSV uploads.
 *   Instead, request.body (ReadableStream) is piped directly to the billing
 *   backend via fetch with duplex:"half". The original Content-Type header
 *   (multipart/form-data; boundary=...) is forwarded unchanged so the billing
 *   FastAPI endpoint receives a well-formed multipart body it can parse with
 *   python-multipart. No body bytes are buffered in this BFF process.
 *
 * Cache-Control: no-store on all responses -- upload metadata is PHI-adjacent.
 * No PHI logged on any error path -- filename and file size are never included
 * in log output or error response bodies.
 */

// Edge-deployment guard: Edge runtime hard-caps request bodies at 4MB.
// Large CSV uploads would silently fail at the Edge boundary before reaching
// this handler. nodejs runtime has no framework-level body cap.
export const runtime = "nodejs";

import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, backendHeaders, BACKENDS } from "@/lib/bff";
import { createRealUploadsClient } from "@infinityrx/contract";
import { handleListUploads } from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;
const BILLING_UPLOADS_URL = `${BILLING_BASE}/api/v1/billing/uploads`;

function makeUploadsClient(jwt: string, tenantId: string) {
  return createRealUploadsClient({
    baseUrl: BILLING_BASE,
    getAuthToken: () => Promise.resolve(jwt),
    getTenantId: () => Promise.resolve(tenantId),
  });
}

export async function GET(request: NextRequest) {
  // AUTH FIRST -- before reading any part of the request.
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const client = makeUploadsClient(session.jwt, session.tenantId);
  const bffReq = { headers: {}, searchParams: request.nextUrl.searchParams };

  try {
    const result = await handleListUploads(bffReq, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    // Never log filename, file size, or claim data on the error path.
    return NextResponse.json(
      { error: { code: "UPSTREAM_ERROR", message: "Failed to list uploads" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}

export async function POST(request: NextRequest) {
  // AUTH FIRST -- before touching the body (multipart DoS guard).
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  // Validate content-type before streaming -- reject non-multipart immediately.
  const contentType = request.headers.get("content-type");
  if (!contentType || !contentType.includes("multipart/form-data")) {
    return NextResponse.json(
      { error: { code: "INVALID_BODY", message: "Expected multipart/form-data" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  if (!request.body) {
    return NextResponse.json(
      { error: { code: "INVALID_BODY", message: "Request body is missing" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  // Streaming passthrough: forward request.body directly to billing.
  // duplex:"half" is required by undici/Node fetch when the request body is a
  // ReadableStream -- without it fetch throws "RequestInit: duplex option is
  // required when request body is a ReadableStream".
  // Content-Type is forwarded verbatim to preserve the multipart boundary that
  // python-multipart on the billing side requires to parse the file field.
  // No body bytes are buffered in this BFF process.
  //
  // Column mapping: portal sends X-Column-Mapping: JSON({canonical->userCol})
  // when the user has mapped non-standard column names. Forwarded as-is to
  // billing, which applies the rename before CSV/XLSX validation. Safe to
  // forward verbatim -- billing ignores malformed values gracefully.
  const columnMappingHeader = request.headers.get("x-column-mapping");
  const extraMappingHeaders: Record<string, string> = columnMappingHeader
    ? { "x-column-mapping": columnMappingHeader }
    : {};

  let billingResp: Response;
  try {
    billingResp = await fetch(BILLING_UPLOADS_URL, {
      method: "POST",
      headers: {
        ...backendHeaders(session),
        "content-type": contentType,
        ...extraMappingHeaders,
      },
      body: request.body,
      // @ts-expect-error -- duplex is required by Node/undici for streaming
      // request bodies but is absent from TypeScript's lib.dom.d.ts fetch types.
      duplex: "half",
    });
  } catch {
    // Never log body details (PHI-adjacent).
    return NextResponse.json(
      { error: { code: "UPLOAD_FAILED", message: "Upload could not be processed" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }

  // Forward billing's JSON response (success or structured error) verbatim,
  // preserving billing's status code. Always no-store.
  let billingBody: unknown;
  try {
    billingBody = await billingResp.json();
  } catch {
    return NextResponse.json(
      { error: { code: "UPLOAD_FAILED", message: "Invalid response from upload service" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }

  return NextResponse.json(billingBody, {
    status: billingResp.status,
    headers: { "Cache-Control": "no-store" },
  });
}
