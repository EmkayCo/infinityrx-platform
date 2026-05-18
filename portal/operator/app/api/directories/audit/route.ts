// portal/operator/app/api/directories/audit/route.ts
// GET /api/directories/audit — ingestion audit log viewer (SP-2 Plan D).
// Proxies to core-platform /api/v1/audit with JWT forwarding.
// Pre-applies module=prescriber_directory and 90-day date_from filter.
// Forwards 403 as-is — core-platform enforces audit:read permission.
import type { NextRequest } from "next/server";
import { getAuditLog } from "@infinityrx/module-directories/bff";

export function GET(request: NextRequest) {
  return getAuditLog(request);
}
