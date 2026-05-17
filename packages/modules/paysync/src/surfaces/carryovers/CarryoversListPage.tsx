// packages/modules/paysync/src/surfaces/carryovers/CarryoversListPage.tsx
// List view for member accumulator carryovers.
// Renders carried_amount via MoneyDisplay, from/to period, and reason.

import type { ReactElement } from "react";
import type { Carryover } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface CarryoversListPageProps {
  readonly carryovers: ReadonlyArray<Carryover>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

export function CarryoversListPage({
  carryovers,
  isLoading,
  error,
}: CarryoversListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="carryovers-list-page">
        <div data-testid="carryovers-list-loading" role="status" aria-label="Loading carryovers">
          Loading carryovers...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="carryovers-list-page">
        <div data-testid="carryovers-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="carryovers-list-page">
      <h1>Carryovers</h1>

      {carryovers.length === 0 ? (
        <div data-testid="carryovers-list-empty" role="status">
          No carryovers found.
        </div>
      ) : (
        <table aria-label="Carryovers">
          <thead>
            <tr>
              <th scope="col">Member</th>
              <th scope="col">Reason</th>
              <th scope="col">From Period</th>
              <th scope="col">To Period</th>
              <th scope="col">Original Amount</th>
              <th scope="col">Carried Amount</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {carryovers.map((carryover) => (
              <tr key={carryover.id} data-testid="carryover-row">
                <td>
                  <a href={`/admin/paysync/carryovers/${carryover.id}`}>
                    {carryover.member_id.slice(0, 8)}...
                  </a>
                </td>
                <td>
                  <span data-testid="carryover-reason">{carryover.reason}</span>
                </td>
                <td>{carryover.from_period}</td>
                <td>{carryover.to_period}</td>
                <td>
                  <MoneyDisplay value={carryover.original_amount} />
                </td>
                <td>
                  <MoneyDisplay value={carryover.carried_amount} />
                </td>
                <td>
                  <time dateTime={carryover.created_at}>
                    {new Date(carryover.created_at).toLocaleString()}
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
