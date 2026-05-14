/**
 * B11 w2 — BFF: GET /api/v1/dashboard/kpi
 *
 * Headline operator dashboard KPIs. Reads session JWT server-side and
 * forwards to the appropriate backend modules with tenant-id injection.
 * Replaces the pre-w2 client-side fallback (hardcoded zeros + "1.4% vs
 * last month" subtext that wasn't even true). Distinguishes "no data"
 * from "backend unreachable" via the unavailable_fields envelope.
 */
import { resolveSession, phiJson, forwardJson, BACKENDS } from "@/lib/bff";

interface DashboardKpi {
  active_programs: number;
  total_claims_ytd: number;
  total_copay_spend_ytd: string;
  gtn_ratio: string;
  active_investigations: number;
  pending_payments: number;
}

export async function GET() {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const unavailable: string[] = [];

  const inv = await forwardJson<{ items?: unknown[]; total?: number }>(
    `${BACKENDS.reclaimrx}/api/v1/reclaimrx/investigations?status=open&limit=1`,
    session,
    { timeoutMs: 3000 }
  );
  const activeInvestigations = inv.ok
    ? (inv.data.total ?? inv.data.items?.length ?? 0)
    : 0;
  if (!inv.ok) unavailable.push("active_investigations");

  const pay = await forwardJson<{ items?: unknown[]; total?: number }>(
    `${BACKENDS.paymentProcessing}/api/v1/payments/pending?limit=1`,
    session,
    { timeoutMs: 3000 }
  );
  const pendingPayments = pay.ok
    ? (pay.data.total ?? pay.data.items?.length ?? 0)
    : 0;
  if (!pay.ok) unavailable.push("pending_payments");

  // active_programs, total_claims_ytd, total_copay_spend_ytd, gtn_ratio —
  // tracked as B11 w2 follow-up aggregation work. Return zero-but-honest.
  unavailable.push("active_programs", "total_claims_ytd", "total_copay_spend_ytd", "gtn_ratio");

  const body: DashboardKpi & { unavailable_fields: string[] } = {
    active_programs: 0,
    total_claims_ytd: 0,
    total_copay_spend_ytd: "0.00",
    gtn_ratio: "0.0%",
    active_investigations: activeInvestigations,
    pending_payments: pendingPayments,
    unavailable_fields: unavailable,
  };
  return phiJson(body);
}
