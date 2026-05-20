// packages/modules/paysync/src/surfaces/bank-settlements/BankSettlementDetailPage.tsx
// Detail view for a single bank settlement.
// - RbacGate on resolve discrepancy action: Approver only.
// - Resolve action only available for settlements in "discrepancy" or "unmatched" status.

import type { ReactElement } from "react";
import type { BankSettlement } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface BankSettlementDetailPageProps {
  readonly settlement: BankSettlement | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onResolveDiscrepancy: (settlementId: string) => void;
}

export function BankSettlementDetailPage({
  settlement,
  isLoading,
  error,
  currentRole,
  onResolveDiscrepancy,
}: BankSettlementDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="bank-settlement-detail-loading" role="status" aria-label="Loading bank settlement">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="bank-settlement-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!settlement) {
    return (
      <div data-testid="bank-settlement-detail-page">
        <p>Bank settlement not found.</p>
      </div>
    );
  }

  // Resolve action only available when discrepancy or unmatched.
  const showResolveAction =
    settlement.status === "discrepancy" || settlement.status === "unmatched";

  return (
    <div data-testid="bank-settlement-detail-page">
      <h1>{settlement.bank_reference}</h1>

      <section aria-label="Bank settlement summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="bank-settlement-status-badge" data-status={settlement.status}>
              {settlement.status}
            </span>
          </dd>

          <dt>Batch</dt>
          <dd>
            <a href={`/admin/paysync/batches/${settlement.batch_id}`}>
              {settlement.batch_id.slice(0, 8)}...
            </a>
          </dd>

          <dt>Settlement Date</dt>
          <dd>{settlement.settlement_date}</dd>

          <dt>Expected Amount</dt>
          <dd>
            <MoneyDisplay value={settlement.expected_amount} />
          </dd>

          <dt>Actual Amount</dt>
          <dd>
            <MoneyDisplay value={settlement.actual_amount} />
          </dd>

          <dt>Created</dt>
          <dd>
            <time dateTime={settlement.created_at}>
              {new Date(settlement.created_at).toLocaleString()}
            </time>
          </dd>

          {settlement.resolved_at && (
            <>
              <dt>Resolved At</dt>
              <dd>
                <time dateTime={settlement.resolved_at}>
                  {new Date(settlement.resolved_at).toLocaleString()}
                </time>
              </dd>
            </>
          )}
        </dl>
      </section>

      {showResolveAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="bank-settlement-resolve-button"
            type="button"
            onClick={() => onResolveDiscrepancy(settlement.id)}
          >
            Resolve Discrepancy
          </button>
        </RbacGate>
      )}
    </div>
  );
}
