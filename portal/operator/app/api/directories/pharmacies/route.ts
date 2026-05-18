// portal/operator/app/api/directories/pharmacies/route.ts
// GET /api/directories/pharmacies?q=...&state=...&limit=20
// Mounts the pharmacy search BFF handler.
import type { NextRequest } from "next/server";
import { getPharmacies } from "@infinityrx/module-directories/bff";

export function GET(request: NextRequest) {
  return getPharmacies(request);
}
