/**
 * GET /api/claims
 *
 * Paginated claims API backed by in-memory cache of InfinityRx source files.
 * DO NOT import from client components — server-only.
 *
 * Query params:
 *   page      (default 1)
 *   size      (default 200, max 1000)
 *   status    P | R
 *   client    substring match on client_name
 *   nrid      exact match on network_reimbursement_id
 *   chain     exact match on primary_chain_code
 *   dos_from  YYYY-MM-DD
 *   dos_to    YYYY-MM-DD
 *   q         free-text: matches claim_id, ndc, service_provider_id
 */

import { NextRequest, NextResponse } from "next/server";
import { getClaims } from "@/lib/data/store";
import type { ParsedClaim } from "@/lib/data/types";

const MAX_SIZE = 1000;
const DEFAULT_SIZE = 200;

export async function GET(req: NextRequest): Promise<NextResponse> {
  const sp = req.nextUrl.searchParams;

  const page = Math.max(1, parseInt(sp.get("page") ?? "1", 10));
  const size = Math.min(MAX_SIZE, Math.max(1, parseInt(sp.get("size") ?? String(DEFAULT_SIZE), 10)));

  const statusFilter = sp.get("status") ?? "";
  const clientFilter = (sp.get("client") ?? "").toLowerCase();
  const nridFilter = sp.get("nrid") ?? "";
  const chainFilter = sp.get("chain") ?? "";
  const dosFrom = sp.get("dos_from") ?? "";
  const dosTo = sp.get("dos_to") ?? "";
  const q = (sp.get("q") ?? "").toLowerCase();
  const cycleFilter = sp.get("cycle") ?? "";

  const all = await getClaims();

  let filtered: ParsedClaim[] = all;

  if (statusFilter === "P" || statusFilter === "R") {
    filtered = filtered.filter((c) => c.status === statusFilter);
  }
  if (clientFilter) {
    filtered = filtered.filter((c) => c.client_name.toLowerCase().includes(clientFilter));
  }
  if (nridFilter) {
    filtered = filtered.filter((c) => c.network_reimbursement_id === nridFilter);
  }
  if (chainFilter) {
    filtered = filtered.filter((c) => c.primary_chain_code === chainFilter);
  }
  if (dosFrom) {
    filtered = filtered.filter((c) => c.date_of_service >= dosFrom);
  }
  if (dosTo) {
    filtered = filtered.filter((c) => c.date_of_service <= dosTo);
  }
  if (cycleFilter) {
    filtered = filtered.filter((c) => c.cycle_id === cycleFilter);
  }
  if (q) {
    filtered = filtered.filter(
      (c) =>
        c.claim_id.toLowerCase().includes(q) ||
        c.ndc.includes(q) ||
        c.service_provider_id.includes(q) ||
        c.prescriber_npi.includes(q)
    );
  }

  const total = filtered.length;
  const start = (page - 1) * size;
  const rows = filtered.slice(start, start + size);

  return NextResponse.json({ rows, total, page, size });
}
