// portal/operator/app/api/directories/ingest/[source]/runs/[runId]/cancel/route.ts
// POST /api/directories/ingest/{source}/runs/{runId}/cancel — cancel a running ingestion.
import type { NextRequest } from "next/server";
import { cancelRun } from "@infinityrx/module-directories/bff";

export function POST(
  request: NextRequest,
  { params }: { params: Promise<{ source: string; runId: string }> },
) {
  return params.then(({ source, runId }) => cancelRun(request, source, runId));
}
