/**
 * GET  /api/paysync/uploads  -- list uploads (cursor-paginated, status filter)
 * POST /api/paysync/uploads  -- create upload (multipart form-data)
 *
 * Auth-before-parse: resolveSession() runs before ANY body access.
 * Unauthenticated requests are rejected immediately, before Next.js buffers
 * the multipart body (multipart DoS guard).
 *
 * Cache-Control: no-store on all responses -- upload metadata is PHI-adjacent.
 * No PHI logged on any error path -- filename and file size are never included
 * in log output or error response bodies.
 */
import { NextResponse, type NextRequest } from "next/server";
import { resolveSession, BACKENDS } from "@/lib/bff";
import { createRealUploadsClient } from "@infinityrx/contract";
import {
  handleListUploads,
  handleCreateUpload,
} from "@infinityrx/module-paysync/bff";

const BILLING_BASE = BACKENDS.billing;

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
  // AUTH FIRST -- before parsing multipart body (DoS guard).
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json(
      { error: { code: "INVALID_BODY", message: "Expected multipart/form-data" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  const fileEntry = formData.get("file");
  // Accept File (production Next.js) and Blob (jsdom test env / fallback).
  // File extends Blob, so instanceof Blob covers both.
  if (!(fileEntry instanceof Blob)) {
    return NextResponse.json(
      { error: { code: "MISSING_FILE", message: "Form field file is required" } },
      { status: 400, headers: { "Cache-Control": "no-store" } }
    );
  }

  // Derive filename: File has .name; plain Blob does not.
  const filename =
    typeof (fileEntry as File).name === "string" && (fileEntry as File).name !== ""
      ? (fileEntry as File).name
      : "upload";

  const client = makeUploadsClient(session.jwt, session.tenantId);
  const blob = new Blob([await fileEntry.arrayBuffer()], { type: fileEntry.type });

  try {
    const result = await handleCreateUpload(filename, blob, client);
    return NextResponse.json(result.data, {
      status: result.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    // Never log filename or file size on the error path (PHI-adjacent).
    return NextResponse.json(
      { error: { code: "UPLOAD_FAILED", message: "Upload could not be processed" } },
      { status: 502, headers: { "Cache-Control": "no-store" } }
    );
  }
}
