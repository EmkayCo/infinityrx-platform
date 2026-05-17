// packages/modules/paysync/src/surfaces/cycles/CyclesListPage.tsx
// List view for paysync billing cycles. Consumes CyclesClient via TanStack Query.
// Renders status badge and MoneyDisplay for total_billed_amount.

import type { ReactElement } from "react";
import type { Cycle, CycleStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface CyclesListPageProps {
  readonly cycles: ReadonlyArray<Cycle>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<CycleStatus, string> = {
  open: "Open",
  closing: "Closing",
  closed: "Closed",
  error: "Error",
};

function cycleStatusLabel(status: string): string {
  return STATUS_LABELS[status as CycleStatus] ?? status;
}

export function CyclesListPage({ cycles, isLoading, error }: CyclesListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="cycles-list-page">
        <div data-testid="cycles-list-loading" role="status" aria-label="Loading cycles">
          Loading cycles...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="cycles-list-page">
        <div data-testid="cycles-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="cycles-list-page">
      <h1>Billing Cycles</h1>

      {cycles.length === 0 ? (
        <div data-testid="cycles-list-empty" role="status">
          No billing cycles found.
        </div>
      ) : (
        <table aria-label="Billing cycles">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col">Status</th>
              <th scope="col">Claims</th>
              <th scope="col">Total Billed</th>
              <th scope="col">Window Closed</th>
            </tr>
          </thead>
          <tbody>
            {cycles.map((cycle) => (
              <tr key={cycle.id} data-testid="cycle-row">
                <td>
                  <a href={`/admin/paysync/cycles/${cycle.id}`}>
                    {cycle.period_label}
                  </a>
                </td>
                <td>
                  <span data-testid="cycle-status-badge" data-status={cycle.status}>
                    {cycleStatusLabel(cycle.status)}
                  </span>
                </td>
                <td>{cycle.claim_count}</td>
                <td>
                  {cycle.total_billed_amount !== null ? (
                    <MoneyDisplay value={cycle.total_billed_amount} />
                  ) : (
                    <span aria-label="not yet computed">-</span>
                  )}
                </td>
                <td>
                  {cycle.window_closed_at !== null ? (
                    <time dateTime={cycle.window_closed_at}>
                      {new Date(cycle.window_closed_at).toLocaleString()}
                    </time>
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
