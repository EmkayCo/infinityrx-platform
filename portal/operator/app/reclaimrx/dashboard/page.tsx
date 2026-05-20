// portal/operator/app/reclaimrx/dashboard/page.tsx
// SP-3 Plan A5 — Empty state per R1 BLOCK 9.
// Plan D replaces this with real DashboardTiles + 6 KPI tiles.
import { ComingSoonPage } from "@/components/ui/coming-soon-page";

export default function ReclaimRxDashboardPage() {
  return (
    <ComingSoonPage
      title="FWA Detection Dashboard"
      description="Investigations, hold volume, recovered dollars, and false-positive rate across all programs."
      phase="Plan D"
    />
  );
}
