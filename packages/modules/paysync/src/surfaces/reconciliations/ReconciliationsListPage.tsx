// packages/modules/paysync/src/surfaces/reconciliations/ReconciliationsListPage.tsx
// List view for period-level reconciliations.
// Renders status badge, period label, total_billed, and variance.

import type { ReactElement } from "react";
import type { Reconciliation, ReconciliationStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface ReconciliationsListPageProps {
  readonly reconciliations: ReadonlyArray<Reconciliation>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<ReconciliationStatus, string> = {
  pending: "Pending",
  in_progress: "In Progress",
  complete: "Complete",
  failed: "Failed",
};

function reconciliationStatusLabel(status: string): string {
  return STATUS_LABELS[status as ReconciliationStatus] ?? status;
}

export function ReconciliationsListPage({
  reconciliations,
  isLoading,
  error,
}: ReconciliationsListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="reconciliations-list-page">
        <div data-testid="reconciliations-list-loading" role="status" aria-label="Loading reconciliations">
          Loading reconciliations...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="reconciliations-list-page">
        <div data-testid="reconciliations-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="reconciliations-list-page">
      <h1>Reconciliations</h1>

      {reconciliations.length === 0 ? (
        <div data-testid="reconciliations-list-empty" role="status">
          No reconciliations found.
        </div>
      ) : (
        <table aria-label="Reconciliations">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col">Status</th>
              <th scope="col">Total Billed</th>
              <th scope="col">Total Paid</th>
              <th scope="col">Variance</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {reconciliations.map((rec) => (
              <tr key={rec.id} data-testid="reconciliation-row">
                <td>
                  <a href={`/admin/paysync/reconcile/${rec.id}`}>
                    {rec.period_label}
                  </a>
                </td>
                <td>
                  <span
                    data-testid="reconciliation-status-badge"
                    data-status={rec.status}
                  >
                    {reconciliationStatusLabel(rec.status)}
                  </span>
                </td>
                <td>
                  {rec.total_billed !== null ? (
                    <MoneyDisplay value={rec.total_billed} />
                  ) : (
                    <span aria-label="Not yet calculated">--</span>
                  )}
                </td>
                <td>
                  {rec.total_paid !== null ? (
                    <MoneyDisplay value={rec.total_paid} />
                  ) : (
                    <span aria-label="Not yet calculated">--</span>
                  )}
                </td>
                <td>
                  {rec.variance !== null ? (
                    <MoneyDisplay value={rec.variance} />
                  ) : (
                    <span aria-label="Not yet calculated">--</span>
                  )}
                </td>
                <td>
                  <time dateTime={rec.created_at}>
                    {new Date(rec.created_at).toLocaleString()}
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
