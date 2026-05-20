// packages/modules/paysync/src/inbox/cards/ApPaymentRunHeldCard.tsx
// Rich inbox card for ap_payment_run_held items.
// Renders hold_reason, total_amount via MoneyDisplay, action link. Approver role.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function ApPaymentRunHeldCard({ item }: { readonly item: InboxItem }): ReactElement {
  const holdReason = typeof item.payload["hold_reason"] === "string"
    ? item.payload["hold_reason"] : null;
  const totalAmount = typeof item.payload["total_amount"] === "string"
    ? item.payload["total_amount"] : null;
  const runId = typeof item.payload["run_id"] === "string"
    ? item.payload["run_id"] : null;
  const detailHref = runId
    ? `/admin/paysync/payment-runs/${runId}`
    : "/admin/paysync/payment-runs";

  return (
    <div data-testid="inbox-card-ap_payment_run_held">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">High Priority</span>
      )}
      <strong>Payment Run Held</strong>
      {holdReason !== null && (
        <span data-testid="card-hold-reason">{holdReason}</span>
      )}
      {totalAmount !== null && (
        <span data-testid="card-total-amount">
          {" Total: "}<MoneyDisplay value={totalAmount} />
        </span>
      )}
      <a data-testid="card-action-link" href={detailHref}>Review payment run</a>
    </div>
  );
}
