// packages/modules/paysync/src/inbox/cards/BatchDraftedCard.tsx
// Rich inbox card for batch_drafted items.
// Renders batch_number, total_amount via MoneyDisplay, and a navigation link
// to the batch detail page. Required by Approver role.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function BatchDraftedCard({ item }: { readonly item: InboxItem }): ReactElement {
  const batchNumber = typeof item.payload["batch_number"] === "string"
    ? item.payload["batch_number"]
    : null;
  const totalAmount = typeof item.payload["total_amount"] === "string"
    ? item.payload["total_amount"]
    : null;
  const batchId = typeof item.payload["batch_id"] === "string"
    ? item.payload["batch_id"]
    : null;
  const detailHref = batchId
    ? `/admin/paysync/batches/${batchId}`
    : "/admin/paysync/batches";

  return (
    <div data-testid="inbox-card-batch_drafted">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{batchNumber ?? "Batch"}</strong>
      <span> — Drafted, awaiting approval</span>

      {totalAmount !== null && (
        <span data-testid="card-total-amount">
          {" Total: "}
          <MoneyDisplay value={totalAmount} />
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Review batch
      </a>
    </div>
  );
}
