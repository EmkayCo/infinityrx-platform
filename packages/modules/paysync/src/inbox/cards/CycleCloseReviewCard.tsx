// packages/modules/paysync/src/inbox/cards/CycleCloseReviewCard.tsx
// Rich inbox card for cycle_close_review items (Approver role).
// Renders period_label, total_billed_amount (via MoneyDisplay if present),
// and a navigation link to the cycle detail page via payload.cycle_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function CycleCloseReviewCard({ item }: { readonly item: InboxItem }): ReactElement {
  const periodLabel = typeof item.payload["period_label"] === "string" ? item.payload["period_label"] : null;
  const totalBilled = typeof item.payload["total_billed_amount"] === "string" ? item.payload["total_billed_amount"] : null;
  const cycleId = typeof item.payload["cycle_id"] === "string" ? item.payload["cycle_id"] : null;
  const detailHref = cycleId
    ? `/admin/paysync/cycles/${cycleId}`
    : "/admin/paysync/cycles";

  return (
    <div data-testid="inbox-card-cycle_close_review">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{periodLabel ?? "Cycle"}</strong>
      <span> — Close review</span>

      {totalBilled !== null && (
        <span data-testid="card-total-billed">
          {" "}
          <MoneyDisplay value={totalBilled} />
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Review and close
      </a>
    </div>
  );
}
