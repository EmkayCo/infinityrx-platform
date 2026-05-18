// portal/operator/app/api/directories/ingest/[source]/runs/[runId]/route.ts
// GET /api/directories/ingest/{source}/runs/{runId} — run detail.
import type { NextRequest } from "next/server";
import { getRunDetail } from "@infinityrx/module-directories/bff";

export function GET(
  request: NextRequest,
  { params }: { params: Promise<{ source: string; runId: string }> },
) {
  return params.then(({ source, runId }) => getRunDetail(request, source, runId));
}
