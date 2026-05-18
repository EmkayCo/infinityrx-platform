// portal/operator/app/api/directories/ingest/[source]/trigger/route.ts
// POST /api/directories/ingest/{source}/trigger — trigger an ingestion run.
// Source is validated against TRIGGERABLE_SOURCES inside the handler (SSRF guard).
import type { NextRequest } from "next/server";
import { triggerRun } from "@infinityrx/module-directories/bff";

export function POST(
  request: NextRequest,
  { params }: { params: Promise<{ source: string }> },
) {
  return params.then(({ source }) => triggerRun(request, source));
}
