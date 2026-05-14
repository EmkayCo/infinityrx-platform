/**
 * B11 w2 — BFF: GET /api/v1/dashboard/alerts
 *
 * Returns operator-facing alerts aggregated from core-platform
 * notifications. Maintains the {alerts: [...]} envelope expected by
 * app/page.tsx AlertsSection.
 */
import { resolveSession, phiJson, forwardJson, BACKENDS } from "@/lib/bff";

type Severity = "info" | "warning" | "error";

interface DashboardAlert {
  id: string;
  severity: Severity;
  title: string;
  detail?: string;
  href?: string;
  created_at?: string;
}

export async function GET() {
  const r = await resolveSession();
  if (!r.ok) return r.response;
  const { session } = r;

  const notif = await forwardJson<{ notifications?: DashboardAlert[] }>(
    `${BACKENDS.corePlatform}/api/v1/notifications?unread=true&limit=10`,
    session,
    { timeoutMs: 3000 }
  );
  const alerts = notif.ok ? notif.data.notifications ?? [] : [];

  return phiJson({
    alerts,
    source_status: notif.ok ? "ok" : "degraded",
  });
}
