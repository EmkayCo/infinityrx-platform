// packages/modules/paysync/src/surfaces/invoices/InvoiceDetailPage.tsx
// Detail view for a single AR invoice.
// - ProvenanceBreadcrumb: upload -> cycle -> batch -> invoice chain when origin IDs provided.
// - RbacGate on send button: Operator disabled; Approver enabled.
// - Send action only for invoices in "approved" status.

import type { ReactElement } from "react";
import type { Invoice } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";
import type { RbacRole } from "../../inbox/types.js";

export interface InvoiceDetailPageProps {
  readonly invoice: Invoice | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly originUploadId?: string;
  readonly originCycleId?: string;
  readonly originBatchId?: string;
  readonly onSend: (invoiceId: string) => void;
}

export function InvoiceDetailPage({
  invoice,
  isLoading,
  error,
  currentRole,
  originUploadId,
  originCycleId,
  originBatchId,
  onSend,
}: InvoiceDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="invoice-detail-loading" role="status" aria-label="Loading invoice">
        Loading...
      </div>
    );
  }
  if (error) {
    return <div data-testid="invoice-detail-error" role="alert">{error}</div>;
  }
  if (!invoice) {
    return <div data-testid="invoice-detail-page"><p>Invoice not found.</p></div>;
  }

  const provenanceChain: ProvenanceLink[] = [];
  if (originUploadId) {
    provenanceChain.push({
      label: `Upload ${originUploadId.slice(0, 8)}...`,
      href: `/admin/paysync/uploads/${originUploadId}`,
    });
  }
  if (originCycleId) {
    provenanceChain.push({
      label: `Cycle ${originCycleId.slice(0, 8)}...`,
      href: `/admin/paysync/cycles/${originCycleId}`,
    });
  }
  if (originBatchId) {
    provenanceChain.push({
      label: `Batch ${originBatchId.slice(0, 8)}...`,
      href: `/admin/paysync/batches/${originBatchId}`,
    });
  }
  if (provenanceChain.length > 0) {
    provenanceChain.push({
      label: invoice.invoice_number,
      href: `/admin/paysync/invoices/${invoice.id}`,
    });
  }

  const showSendAction = invoice.status === "approved";

  return (
    <div data-testid="invoice-detail-page">
      {provenanceChain.length > 0 && <ProvenanceBreadcrumb chain={provenanceChain} />}
      <h1>{invoice.invoice_number}</h1>
      <section aria-label="Invoice summary">
        <dl>
          <dt>Status</dt>
          <dd><span data-testid="invoice-status-badge" data-status={invoice.status}>{invoice.status}</span></dd>
          <dt>Client</dt><dd>{invoice.client_name}</dd>
          <dt>Invoice Type</dt><dd>{invoice.invoice_type}</dd>
          <dt>Period</dt><dd>{invoice.period_start} to {invoice.period_end}</dd>
          <dt>Claims</dt><dd>{invoice.claim_count}</dd>
          <dt>Claims Subtotal</dt><dd><MoneyDisplay value={invoice.claims_subtotal} /></dd>
          <dt>Fees Subtotal</dt><dd><MoneyDisplay value={invoice.fees_subtotal} /></dd>
          <dt>Adjustments</dt><dd><MoneyDisplay value={invoice.adjustments} /></dd>
          <dt>Late Fees</dt><dd><MoneyDisplay value={invoice.late_fees} /></dd>
          <dt>Total</dt><dd><MoneyDisplay value={invoice.total} /></dd>
          <dt>Paid Amount</dt><dd><MoneyDisplay value={invoice.paid_amount} /></dd>
          <dt>Due Date</dt><dd>{invoice.due_date}</dd>
          <dt>Created</dt>
          <dd><time dateTime={invoice.created_at}>{new Date(invoice.created_at).toLocaleString()}</time></dd>
        </dl>
      </section>
      {showSendAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button data-testid="invoice-send-button" type="button" onClick={() => onSend(invoice.id)}>
            Send Invoice
          </button>
        </RbacGate>
      )}
    </div>
  );
}
