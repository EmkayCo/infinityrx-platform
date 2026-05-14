/**
 * B11 w2 — BFF: GET /api/v1/dashboard/activity
 *
 * Recent-activity feed sourced from core-platform's audit query,
 * tenant-scoped via the session JWT's tid claim.
 */
import { resolveSession, phiJson, forwardJson, BACKENDS } from "@/lib/bff";

interface DashboardActivityEvent {
  id: string;
  actor: string;
  action: string;
  resource?: string;
  timestamp: string;
  detail?: string;
}

export async function GET() {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  // Real core-platform endpoint is GET /api/v1/audit (list, paginated).
  // Query params: date_from, date_to, action, module, entity_type,
  // user_id, correlation_id, limit, offset. Response is AuditPage shape.
  // See modules/core-platform/src/audit/api.py:38.
  const since = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  const audit = await forwardJson<{ items?: DashboardActivityEvent[] }>(
    `${BACKENDS.corePlatform}/api/v1/audit?date_from=${encodeURIComponent(since)}&limit=20`,
    session,
    { timeoutMs: 3000 }
  );
  const activity = audit.ok ? audit.data.items ?? [] : [];

  return phiJson({
    activity,
    source_status: audit.ok ? "ok" : "degraded",
  });
}
