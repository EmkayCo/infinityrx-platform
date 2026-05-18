// portal/operator/app/api/directories/quality/dismiss/[source]/route.ts
// POST /api/directories/quality/dismiss/{source} — dismiss a data-quality alert.
// Source validated against DISMISSIBLE_SOURCES (21 keys, includes fdb) inside handler.
// Returns 204 on success, 404 for unknown source.
import type { NextRequest } from "next/server";
import { dismissAlert } from "@infinityrx/module-directories/bff";

export function POST(
  request: NextRequest,
  { params }: { params: Promise<{ source: string }> },
) {
  return params.then(({ source }) => dismissAlert(request, source));
}
