// packages/modules/paysync/src/inbox/cards/CarryoverOpenCard.tsx
// Rich inbox card for carryover_open items.
// Renders carried_amount via MoneyDisplay, from_period, and a navigation link
// to the carryover detail page via payload.carryover_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function CarryoverOpenCard({ item }: { readonly item: InboxItem }): ReactElement {
  const carriedAmount = typeof item.payload["carried_amount"] === "string"
    ? item.payload["carried_amount"]
    : null;
  const fromPeriod = typeof item.payload["from_period"] === "string"
    ? item.payload["from_period"]
    : null;
  const carryoverId = typeof item.payload["carryover_id"] === "string"
    ? item.payload["carryover_id"]
    : null;
  const detailHref = carryoverId
    ? `/admin/paysync/carryovers/${carryoverId}`
    : "/admin/paysync/carryovers";

  return (
    <div data-testid="inbox-card-carryover_open">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>Carryover Open</strong>

      {fromPeriod !== null && (
        <span> — From period: {fromPeriod}</span>
      )}

      {carriedAmount !== null && (
        <span data-testid="card-carried-amount">
          {" Carried: "}
          <MoneyDisplay value={carriedAmount} />
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Review carryover
      </a>
    </div>
  );
}
