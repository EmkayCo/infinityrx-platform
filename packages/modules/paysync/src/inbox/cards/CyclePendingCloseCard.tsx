// packages/modules/paysync/src/inbox/cards/CyclePendingCloseCard.tsx
// Rich inbox card for cycle_pending_close items.
// Renders period_label, priority indicator, and a navigation link to the
// cycle detail page via payload.cycle_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";

export default function CyclePendingCloseCard({ item }: { readonly item: InboxItem }): ReactElement {
  const periodLabel = typeof item.payload["period_label"] === "string" ? item.payload["period_label"] : null;
  const cycleId = typeof item.payload["cycle_id"] === "string" ? item.payload["cycle_id"] : null;
  const detailHref = cycleId
    ? `/admin/paysync/cycles/${cycleId}`
    : "/admin/paysync/cycles";

  return (
    <div data-testid="inbox-card-cycle_pending_close">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{periodLabel ?? "Cycle"}</strong>
      <span> — Pending close</span>

      <a data-testid="card-action-link" href={detailHref}>
        Review cycle
      </a>
    </div>
  );
}
