/**
 * B11 w2 — BFF: GET /api/v1/dashboard/program-health
 *
 * Per-program health cards (claim volume, spend, GTN%, alert count).
 * Forwards to reporting's FWA summary endpoint which has program-grain
 * data. Full multi-backend aggregation is a w2.x follow-up.
 */
import { resolveSession, phiJson, forwardJson, BACKENDS } from "@/lib/bff";

interface ProgramHealthCard {
  program_id: string;
  program_name: string;
  manufacturer: string;
  claims_period: number;
  spend_period: string;
  gtn_percent: string;
  active_alerts: number;
  href: string;
}

export async function GET() {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const summary = await forwardJson<{ programs?: ProgramHealthCard[] }>(
    `${BACKENDS.reporting}/api/v1/reporting/client-api/fwa-summary`,
    session,
    { timeoutMs: 3000 }
  );
  const programs = summary.ok ? summary.data.programs ?? [] : [];

  return phiJson({
    programs,
    source_status: summary.ok ? "ok" : "degraded",
  });
}
