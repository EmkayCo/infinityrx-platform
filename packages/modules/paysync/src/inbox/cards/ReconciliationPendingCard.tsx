// packages/modules/paysync/src/inbox/cards/ReconciliationPendingCard.tsx
// Rich inbox card for reconciliation_pending items.
// Renders period_label, total_billed via MoneyDisplay, and a navigation link
// to the reconciliation detail page via payload.reconciliation_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function ReconciliationPendingCard({ item }: { readonly item: InboxItem }): ReactElement {
  const periodLabel = typeof item.payload["period_label"] === "string"
    ? item.payload["period_label"]
    : null;
  const totalBilled = typeof item.payload["total_billed"] === "string"
    ? item.payload["total_billed"]
    : null;
  const reconciliationId = typeof item.payload["reconciliation_id"] === "string"
    ? item.payload["reconciliation_id"]
    : null;
  const detailHref = reconciliationId
    ? `/admin/paysync/reconcile/${reconciliationId}`
    : "/admin/paysync/reconcile";

  return (
    <div data-testid="inbox-card-reconciliation_pending">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{periodLabel ?? "Reconciliation"}</strong>
      <span> — Pending reconciliation</span>

      {totalBilled !== null && (
        <span data-testid="card-total-billed">
          {" Total billed: "}
          <MoneyDisplay value={totalBilled} />
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Review reconciliation
      </a>
    </div>
  );
}
