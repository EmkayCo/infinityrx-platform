// packages/modules/paysync/src/inbox/cards/BankingDiscrepancyCard.tsx
// Rich inbox card for banking_discrepancy items.
// Renders bank_reference, expected_amount and actual_amount via MoneyDisplay,
// and a navigation link to the bank settlement detail page via payload.settlement_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function BankingDiscrepancyCard({ item }: { readonly item: InboxItem }): ReactElement {
  const bankReference = typeof item.payload["bank_reference"] === "string"
    ? item.payload["bank_reference"]
    : null;
  const expectedAmount = typeof item.payload["expected_amount"] === "string"
    ? item.payload["expected_amount"]
    : null;
  const actualAmount = typeof item.payload["actual_amount"] === "string"
    ? item.payload["actual_amount"]
    : null;
  const settlementId = typeof item.payload["settlement_id"] === "string"
    ? item.payload["settlement_id"]
    : null;
  const detailHref = settlementId
    ? `/admin/paysync/settlements/${settlementId}`
    : "/admin/paysync/settlements";

  return (
    <div data-testid="inbox-card-banking_discrepancy">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{bankReference ?? "Settlement"}</strong>
      <span> — Amount mismatch</span>

      {expectedAmount !== null && (
        <span data-testid="card-expected-amount">
          {" Expected: "}
          <MoneyDisplay value={expectedAmount} />
        </span>
      )}

      {actualAmount !== null && (
        <span data-testid="card-actual-amount">
          {" Actual: "}
          <MoneyDisplay value={actualAmount} />
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Resolve discrepancy
      </a>
    </div>
  );
}
