// portal/operator/app/api/directories/prescribers/[npi]/exclusion-check/route.ts
// GET /api/directories/prescribers/{npi}/exclusion-check
// NPI is validated inside the handler against the exclusion sources allowlist.
import type { NextRequest } from "next/server";
import { getExclusionCheck } from "@infinityrx/module-directories/bff";

export function GET(
  request: NextRequest,
  { params }: { params: Promise<{ npi: string }> },
) {
  return params.then(({ npi }) => getExclusionCheck(request, npi));
}
