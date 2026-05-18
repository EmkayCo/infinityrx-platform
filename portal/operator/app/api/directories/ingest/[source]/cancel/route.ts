// portal/operator/app/api/directories/ingest/[source]/cancel/route.ts
// POST /api/directories/ingest/{source}/cancel — cancel an active ingestion run.
// cancelRun takes (req, source) — backend: POST /data-ingestion/{source}/cancel.
// Source validated against TRIGGERABLE_SOURCES inside the handler (SSRF guard).
import type { NextRequest } from "next/server";
import { cancelRun } from "@infinityrx/module-directories/bff";

export function POST(
  request: NextRequest,
  { params }: { params: Promise<{ source: string }> },
) {
  return params.then(({ source }) => cancelRun(request, source));
}
