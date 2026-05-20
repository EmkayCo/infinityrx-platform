// portal/operator/app/reclaimrx/thresholds/page.tsx
// SP-3 Plan A5 — Empty state per R1 BLOCK 9.
// Plan C replaces this with real threshold config editor (admin-only).
import { ComingSoonPage } from "@/components/ui/coming-soon-page";

export default function ReclaimRxThresholdsPage() {
  return (
    <ComingSoonPage
      title="Threshold Configuration"
      description="Per-tenant rule thresholds, ML score thresholds, anomaly sensitivity. Admin-only."
      phase="Plan C"
    />
  );
}
