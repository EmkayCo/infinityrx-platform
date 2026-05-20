// packages/modules/paysync/src/surfaces/bank-settlements/BankSettlementsListPage.tsx
// List view for bank settlement reconciliations.
// Renders status badge with discrepancy indicator, and amount comparison.

import type { ReactElement } from "react";
import type { BankSettlement, BankSettlementStatus } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface BankSettlementsListPageProps {
  readonly settlements: ReadonlyArray<BankSettlement>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

const STATUS_LABELS: Record<BankSettlementStatus, string> = {
  matched: "Matched",
  unmatched: "Unmatched",
  discrepancy: "Discrepancy",
  resolved: "Resolved",
};

function settlementStatusLabel(status: string): string {
  return STATUS_LABELS[status as BankSettlementStatus] ?? status;
}

export function BankSettlementsListPage({
  settlements,
  isLoading,
  error,
}: BankSettlementsListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="bank-settlements-list-page">
        <div data-testid="bank-settlements-list-loading" role="status" aria-label="Loading bank settlements">
          Loading bank settlements...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="bank-settlements-list-page">
        <div data-testid="bank-settlements-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="bank-settlements-list-page">
      <h1>Bank Settlements</h1>

      {settlements.length === 0 ? (
        <div data-testid="bank-settlements-list-empty" role="status">
          No bank settlements found.
        </div>
      ) : (
        <table aria-label="Bank settlements">
          <thead>
            <tr>
              <th scope="col">Bank Reference</th>
              <th scope="col">Status</th>
              <th scope="col">Settlement Date</th>
              <th scope="col">Expected Amount</th>
              <th scope="col">Actual Amount</th>
              <th scope="col">Created</th>
            </tr>
          </thead>
          <tbody>
            {settlements.map((settlement) => (
              <tr key={settlement.id} data-testid="bank-settlement-row">
                <td>
                  <a href={`/admin/paysync/settlements/${settlement.id}`}>
                    {settlement.bank_reference}
                  </a>
                </td>
                <td>
                  <span
                    data-testid="bank-settlement-status-badge"
                    data-status={settlement.status}
                  >
                    {settlementStatusLabel(settlement.status)}
                  </span>
                </td>
                <td>{settlement.settlement_date}</td>
                <td>
                  <MoneyDisplay value={settlement.expected_amount} />
                </td>
                <td>
                  <MoneyDisplay value={settlement.actual_amount} />
                </td>
                <td>
                  <time dateTime={settlement.created_at}>
                    {new Date(settlement.created_at).toLocaleString()}
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
