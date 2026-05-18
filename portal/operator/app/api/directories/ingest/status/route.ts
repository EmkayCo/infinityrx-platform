// portal/operator/app/api/directories/ingest/status/route.ts
// GET /api/directories/ingest/status — all-source ingestion status.
// Mounts getAllStatus from the ingestion BFF handler.
import type { NextRequest } from "next/server";
import { getAllStatus } from "@infinityrx/module-directories/bff";

export function GET(request: NextRequest) {
  return getAllStatus(request);
}
