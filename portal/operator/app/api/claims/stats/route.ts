/**
 * GET /api/claims/stats
 *
 * Returns all pre-computed aggregations from public/data/aggregated/*.json
 * merged into a single response object.
 */

import { NextResponse } from "next/server";
import { getAggregations } from "@/lib/data/store";

export async function GET(): Promise<NextResponse> {
  const agg = await getAggregations();
  return NextResponse.json(agg);
}
