// portal/operator/app/api/directories/ingest/[source]/history/route.ts
// GET /api/directories/ingest/{source}/history — run history for a source.
import type { NextRequest } from "next/server";
import { getHistory } from "@infinityrx/module-directories/bff";

export function GET(
  request: NextRequest,
  { params }: { params: Promise<{ source: string }> },
) {
  return params.then(({ source }) => getHistory(request, source));
}
