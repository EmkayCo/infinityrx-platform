// portal/operator/app/api/directories/quality/route.ts
// GET /api/directories/quality — data-quality dashboard aggregator (SP-2 Plan D).
// Fan-out to prescriber-directory + pharmacy-directory + drug-database backends.
// tid is derived from JWT claims — never from request headers.
import type { NextRequest } from "next/server";
import { getQuality } from "@infinityrx/module-directories/bff";

export function GET(request: NextRequest) {
  return getQuality(request);
}
