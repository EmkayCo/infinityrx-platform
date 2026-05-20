// portal/operator/app/reclaimrx/holds/page.tsx
// SP-3 Plan A5 — Empty state per R1 BLOCK 9.
// Plan D replaces this with real hold release dialog + hold history table.
import { ComingSoonPage } from "@/components/ui/coming-soon-page";

export default function ReclaimRxHoldsPage() {
  return (
    <ComingSoonPage
      title="Payment Holds"
      description="Active holds, hold release with audited reason, per-investigation hold history."
      phase="Plan D"
    />
  );
}
