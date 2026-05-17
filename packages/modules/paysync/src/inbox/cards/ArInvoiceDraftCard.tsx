// packages/modules/paysync/src/inbox/cards/ArInvoiceDraftCard.tsx
// Rich inbox card for ar_invoice_draft items.
// Renders invoice_number, total via MoneyDisplay, action link. Approver role.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export default function ArInvoiceDraftCard({ item }: { readonly item: InboxItem }): ReactElement {
  const invoiceNumber = typeof item.payload["invoice_number"] === "string"
    ? item.payload["invoice_number"] : null;
  const total = typeof item.payload["total"] === "string"
    ? item.payload["total"] : null;
  const invoiceId = typeof item.payload["invoice_id"] === "string"
    ? item.payload["invoice_id"] : null;
  const detailHref = invoiceId
    ? `/admin/paysync/invoices/${invoiceId}`
    : "/admin/paysync/invoices";

  return (
    <div data-testid="inbox-card-ar_invoice_draft">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">High Priority</span>
      )}
      <strong>{invoiceNumber ?? "Invoice"}</strong>
      <span> -- Draft, awaiting send approval</span>
      {total !== null && (
        <span data-testid="card-total-amount">
          {" Total: "}<MoneyDisplay value={total} />
        </span>
      )}
      <a data-testid="card-action-link" href={detailHref}>Review invoice</a>
    </div>
  );
}
