// packages/modules/paysync/src/surfaces/invoices/InvoicesListPage.tsx
// List view for paysync AR invoices. Renders status badge and MoneyDisplay for total.

import type { ReactElement } from "react";
import type { Invoice, InvoiceStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface InvoicesListPageProps {
  readonly invoices: ReadonlyArray<Invoice>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<InvoiceStatus, string> = {
  draft: "Draft",
  approved: "Approved",
  sent: "Sent",
  paid: "Paid",
  void: "Void",
  overdue: "Overdue",
};

function invoiceStatusLabel(status: string): string {
  return STATUS_LABELS[status as InvoiceStatus] ?? status;
}

export function InvoicesListPage({ invoices, isLoading, error }: InvoicesListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="invoices-list-page">
        <div data-testid="invoices-list-loading" role="status" aria-label="Loading invoices">
          Loading invoices...
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div data-testid="invoices-list-page">
        <div data-testid="invoices-list-error" role="alert">{error}</div>
      </div>
    );
  }
  return (
    <div data-testid="invoices-list-page">
      <h1>AR Invoices</h1>
      {invoices.length === 0 ? (
        <div data-testid="invoices-list-empty" role="status">No invoices found.</div>
      ) : (
        <table aria-label="AR invoices">
          <thead>
            <tr>
              <th scope="col">Invoice Number</th>
              <th scope="col">Client</th>
              <th scope="col">Status</th>
              <th scope="col">Period</th>
              <th scope="col">Total</th>
              <th scope="col">Due Date</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((invoice) => (
              <tr key={invoice.id} data-testid="invoice-row">
                <td><a href={`/admin/paysync/invoices/${invoice.id}`}>{invoice.invoice_number}</a></td>
                <td>{invoice.client_name}</td>
                <td><span data-testid="invoice-status-badge" data-status={invoice.status}>{invoiceStatusLabel(invoice.status)}</span></td>
                <td>{invoice.period_start} to {invoice.period_end}</td>
                <td><MoneyDisplay value={invoice.total} /></td>
                <td>{invoice.due_date}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
