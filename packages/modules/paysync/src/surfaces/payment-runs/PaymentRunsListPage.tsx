// packages/modules/paysync/src/surfaces/payment-runs/PaymentRunsListPage.tsx
// List view for paysync payment runs. Renders status badge and MoneyDisplay for total_amount.

import type { ReactElement } from "react";
import type { PaymentRun, PaymentRunStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface PaymentRunsListPageProps {
  readonly runs: ReadonlyArray<PaymentRun>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<PaymentRunStatus, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  held: "Held",
};

function runStatusLabel(status: string): string {
  return STATUS_LABELS[status as PaymentRunStatus] ?? status;
}

export function PaymentRunsListPage({ runs, isLoading, error }: PaymentRunsListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="payment-runs-list-page">
        <div data-testid="payment-runs-list-loading" role="status" aria-label="Loading payment runs">
          Loading payment runs...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="payment-runs-list-page">
        <div data-testid="payment-runs-list-error" role="alert">{error}</div>
      </div>
    );
  }

  return (
    <div data-testid="payment-runs-list-page">
      <h1>Payment Runs</h1>

      {runs.length === 0 ? (
        <div data-testid="payment-runs-list-empty" role="status">
          No payment runs found.
        </div>
      ) : (
        <table aria-label="Payment runs">
          <thead>
            <tr>
              <th scope="col">Run ID</th>
              <th scope="col">Status</th>
              <th scope="col">Payments</th>
              <th scope="col">Total Amount</th>
              <th scope="col">Run At</th>
              <th scope="col">Completed At</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} data-testid="payment-run-row">
                <td>
                  <a href={`/admin/paysync/payment-runs/${run.id}`}>
                    {run.id.slice(0, 8)}...
                  </a>
                </td>
                <td>
                  <span data-testid="payment-run-status-badge" data-status={run.status}>
                    {runStatusLabel(run.status)}
                  </span>
                </td>
                <td>{run.payment_count}</td>
                <td><MoneyDisplay value={run.total_amount} /></td>
                <td><time dateTime={run.run_at}>{new Date(run.run_at).toLocaleString()}</time></td>
                <td>
                  {run.completed_at !== null ? (
                    <time dateTime={run.completed_at}>{new Date(run.completed_at).toLocaleString()}</time>
                  ) : (
                    <span>-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
