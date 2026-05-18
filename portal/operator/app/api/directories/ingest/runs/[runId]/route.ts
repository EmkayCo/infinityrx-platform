// portal/operator/app/api/directories/ingest/runs/[runId]/route.ts
// GET /api/directories/ingest/runs/{runId} — run detail.
// getRunDetail takes (req, runId) — no source segment needed; backend uses runId only.
import type { NextRequest } from "next/server";
import { getRunDetail } from "@infinityrx/module-directories/bff";

export function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> },
) {
  return params.then(({ runId }) => getRunDetail(request, runId));
}
