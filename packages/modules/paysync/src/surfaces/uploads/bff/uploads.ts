// packages/modules/paysync/src/surfaces/uploads/bff/uploads.ts
// Next.js BFF route handlers for the paysync uploads surface.
// These proxy requests from the operator portal UI to the billing backend.
// Auth token is forwarded via the Authorization header from the incoming request.
// Cache-Control: no-store is set on responses containing row_errors (PHI-adjacent).

import type { UploadsClient } from "@infinityrx/contract";
import type { UploadListRequest } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
  readonly body?: ReadableStream<Uint8Array> | Blob | FormData;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

/**
 * GET /api/paysync/uploads
 * Proxies to UploadsClient.list with cursor + status filters from query string.
 */
export async function handleListUploads(
  req: BffRequest,
  client: UploadsClient,
): Promise<BffResponse<Awaited<ReturnType<UploadsClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const cursorVal = params.get("cursor");
  const statusVal = params.get("status") as UploadListRequest["status"] | null;
  const listReq: UploadListRequest = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
    ...(statusVal !== null ? { status: statusVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: { "Cache-Control": "no-store" } };
}

/**
 * GET /api/paysync/uploads/[id]
 * Proxies to UploadsClient.get; returns 404 when upload is null.
 * Cache-Control: no-store because response may include row_errors (PHI-adjacent).
 */
export async function handleGetUpload(
  id: string,
  _req: BffRequest,
  client: UploadsClient,
): Promise<BffResponse<Awaited<ReturnType<UploadsClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: { "Cache-Control": "no-store" } };
  }
  return { data, status: 200, headers: { "Cache-Control": "no-store" } };
}

/**
 * GET /api/paysync/uploads/[id]/claims
 * Proxies to UploadsClient.getClaims with pagination.
 * Cache-Control: no-store (claims contain PHI-adjacent member_id).
 */
export async function handleGetUploadClaims(
  id: string,
  req: BffRequest,
  client: UploadsClient,
): Promise<BffResponse<Awaited<ReturnType<UploadsClient["getClaims"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const cursorParam = params.get("cursor");
  const claimsOpts: { readonly limit?: number; readonly cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(cursorParam !== null ? { cursor: cursorParam } : {}),
  };
  const data = await client.getClaims(id, claimsOpts);
  return { data, status: 200, headers: { "Cache-Control": "no-store" } };
}

/**
 * POST /api/paysync/uploads
 * Proxies a multipart upload to UploadsClient.create.
 * Returns 409 when the backend signals a sha256 duplicate.
 */
export async function handleCreateUpload(
  filename: string,
  content: Blob,
  client: UploadsClient,
): Promise<BffResponse<Awaited<ReturnType<UploadsClient["create"]>> | { conflict: true; existing_upload_id: string }>> {
  try {
    const data = await client.create({ filename, content });
    return { data, status: 201, headers: { "Cache-Control": "no-store" } };
  } catch (err: unknown) {
    // 409 from backend signals sha256 dedup — surface the existing upload id.
    const message = err instanceof Error ? err.message : String(err);
    if (message.includes("DUPLICATE_UPLOAD") || (err as { code?: string }).code === "DUPLICATE_UPLOAD") {
      const existingId = (err as { detail?: string }).detail ?? "";
      return {
        data: { conflict: true, existing_upload_id: existingId },
        status: 409,
        headers: { "Cache-Control": "no-store" },
      };
    }
    throw err;
  }
}
