// packages/modules/paysync/src/surfaces/files/bff/files.ts
// Next.js BFF route handlers for the paysync files surface.
// Proxies to FilesClient from @infinityrx/contract.
// Cache-Control: no-store on download (PHI-adjacent binary content).

import type { FilesClient, FileGenerateRequest } from "@infinityrx/contract";

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
  readonly body?: FileGenerateRequest;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

/**
 * GET /api/paysync/files
 * Proxies to FilesClient.list with optional type filter + cursor pagination.
 */
export async function handleListFiles(
  req: BffRequest,
  client: FilesClient,
): Promise<BffResponse<Awaited<ReturnType<FilesClient["list"]>>>> {
  const params = req.searchParams ?? new URLSearchParams();
  const typeVal = params.get("type");
  const cursorVal = params.get("cursor");
  const listReq: { type?: string; limit?: number; cursor?: string } = {
    limit: params.has("limit") ? Number(params.get("limit")) : 50,
    ...(typeVal !== null ? { type: typeVal } : {}),
    ...(cursorVal !== null ? { cursor: cursorVal } : {}),
  };
  const data = await client.list(listReq);
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/files/[id]
 * Proxies to FilesClient.get; returns 404 when artifact is null.
 */
export async function handleGetFile(
  id: string,
  _req: BffRequest,
  client: FilesClient,
): Promise<BffResponse<Awaited<ReturnType<FilesClient["get"]>>>> {
  const data = await client.get(id);
  if (data === null) {
    return { data: null, status: 404, headers: {} };
  }
  return { data, status: 200, headers: {} };
}

/**
 * POST /api/paysync/files/generate
 * Approver-only -- enforced server-side; returns the new FileArtifact.
 * Write-path fail-fast: throws on backend error (never optimistic).
 */
export async function handleGenerateFile(
  req: BffRequest,
  client: FilesClient,
): Promise<BffResponse<Awaited<ReturnType<FilesClient["generate"]>>>> {
  if (!req.body) {
    return {
      data: null as unknown as Awaited<ReturnType<FilesClient["generate"]>>,
      status: 400,
      headers: {},
    };
  }
  const data = await client.generate(req.body);
  return { data, status: 201, headers: {} };
}

/**
 * GET /api/paysync/files/[id]/download
 * Proxies binary bytes from FilesClient.download.
 * Cache-Control: no-store -- content is PHI-adjacent (financial file bytes).
 * Sets Content-Disposition: attachment so browsers prompt a save dialog.
 */
export async function handleDownloadFile(
  id: string,
  _req: BffRequest,
  client: FilesClient,
): Promise<BffResponse<Blob>> {
  const data = await client.download(id);
  return {
    data,
    status: 200,
    headers: {
      "Cache-Control": "no-store",
      "Content-Disposition": `attachment`,
    },
  };
}
