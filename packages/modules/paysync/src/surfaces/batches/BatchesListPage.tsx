// packages/modules/paysync/src/surfaces/batches/BatchesListPage.tsx
// List view for paysync payment batches.
// Renders status badge and MoneyDisplay for total_amount.
// Data is received via props (BFF/TanStack Query owns the fetch).

import type { ReactElement } from "react";
import type { Batch, BatchStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface BatchesListPageProps {
  readonly batches: ReadonlyArray<Batch>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<BatchStatus, string> = {
  generated: "Generated",
  validated: "Validated",
  approved: "Approved",
  submitted: "Submitted",
  settled: "Settled",
  void: "Void",
};

function batchStatusLabel(status: string): string {
  return STATUS_LABELS[status as BatchStatus] ?? status;
}

export function BatchesListPage({
  batches,
  isLoading,
  error,
}: BatchesListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="batches-list-page">
        <div data-testid="batches-list-loading" role="status" aria-label="Loading batches">
          Loading batches...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="batches-list-page">
        <div data-testid="batches-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="batches-list-page">
      <h1>Payment Batches</h1>

      {batches.length === 0 ? (
        <div data-testid="batches-list-empty" role="status">
          No payment batches found.
        </div>
      ) : (
        <table aria-label="Payment batches">
          <thead>
            <tr>
              <th scope="col">Batch Number</th>
              <th scope="col">Status</th>
              <th scope="col">Route</th>
              <th scope="col">Payments</th>
              <th scope="col">Total Amount</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} data-testid="batch-row">
                <td>
                  <a href={`/admin/paysync/batches/${batch.id}`}>
                    {batch.batch_number}
                  </a>
                </td>
                <td>
                  <span data-testid="batch-status-badge" data-status={batch.status}>
                    {batchStatusLabel(batch.status)}
                  </span>
                </td>
                <td>{batch.payment_route}</td>
                <td>{batch.payment_count}</td>
                <td>
                  <MoneyDisplay value={batch.total_amount} />
                </td>
                <td>
                  <time dateTime={batch.created_at}>
                    {new Date(batch.created_at).toLocaleString()}
                  </time>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
