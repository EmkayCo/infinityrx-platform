// packages/modules/paysync/src/surfaces/reports/CycleReportsPage.tsx
// Read-only report view for billing cycle summaries.
// All roles can view. No mutations on this surface.
// Monetary totals come server-side as Decimal strings -- rendered via MoneyDisplay.

import type { ReactElement } from "react";
import type { Cycle, CycleStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface CycleReportsPageProps {
  readonly cycles?: ReadonlyArray<Cycle>;
  readonly isLoading?: boolean;
  readonly error?: string | null;
}

const STATUS_LABELS: Record<CycleStatus, string> = {
  open: "Open",
  closing: "Closing",
  closed: "Closed",
  error: "Error",
};

function statusLabel(status: string): string {
  return STATUS_LABELS[status as CycleStatus] ?? status;
}

export function CycleReportsPage({
  cycles = [],
  isLoading = false,
  error = null,
}: CycleReportsPageProps = {}): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="cycle-reports-page">
        <div data-testid="cycle-reports-loading" role="status" aria-label="Loading cycle reports">
          Loading cycle reports...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="cycle-reports-page">
        <div data-testid="cycle-reports-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="cycle-reports-page">
      <h1>Cycle Reports</h1>
      <p>Read-only summary of all billing cycles. All roles can view.</p>

      <div data-testid="export-disabled-notice">
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="PDF/Excel export coming in a future release"
        >
          Export
        </button>
      </div>

      {cycles.length === 0 ? (
        <div data-testid="cycle-reports-empty" role="status">
          No cycle data available.
        </div>
      ) : (
        <table aria-label="Cycle reports">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col">Status</th>
              <th scope="col">Claims</th>
              <th scope="col">Total Billed</th>
              <th scope="col">Closed At</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((cycle) => (
              <tr key={cycle.id} data-testid="cycle-report-row">
                <td>
                  <a href={`/admin/paysync/cycles/${cycle.id}`}>
                    {cycle.period_label}
                  </a>
                </td>
                <td>
                  <span
                    data-testid="cycle-report-status-badge"
                    data-status={cycle.status}
                  >
                    {statusLabel(cycle.status)}
                  </span>
                </td>
                <td>{cycle.claim_count}</td>
                <td>
                  {cycle.total_billed_amount !== null ? (
                    <MoneyDisplay value={cycle.total_billed_amount} />
                  ) : (
                    <span aria-label="not yet available">-</span>
                  )}
                </td>
                <td>
                  {cycle.window_closed_at ? (
                    <time dateTime={cycle.window_closed_at}>
                      {new Date(cycle.window_closed_at).toLocaleDateString()}
                    </time>
                  ) : (
                    <span aria-label="not yet closed">-</span>
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
