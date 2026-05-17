// packages/modules/paysync/src/surfaces/reconciliations/ReconciliationDetailPage.tsx
// Detail view for a single reconciliation.
// - RbacGate on finalize action: Approver only.
// - Finalize action only available for "pending" or "in_progress" reconciliations.

import type { ReactElement } from "react";
import type { Reconciliation } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface ReconciliationDetailPageProps {
  readonly reconciliation: Reconciliation | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onFinalize: (reconciliationId: string) => void;
}

export function ReconciliationDetailPage({
  reconciliation,
  isLoading,
  error,
  currentRole,
  onFinalize,
}: ReconciliationDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="reconciliation-detail-loading" role="status" aria-label="Loading reconciliation">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="reconciliation-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!reconciliation) {
    return (
      <div data-testid="reconciliation-detail-page">
        <p>Reconciliation not found.</p>
      </div>
    );
  }

  // Finalize only available for pending or in_progress reconciliations.
  const showFinalizeAction =
    reconciliation.status === "pending" || reconciliation.status === "in_progress";

  return (
    <div data-testid="reconciliation-detail-page">
      <h1>{reconciliation.period_label}</h1>

      <section aria-label="Reconciliation summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="reconciliation-status-badge" data-status={reconciliation.status}>
              {reconciliation.status}
            </span>
          </dd>

          <dt>Total Billed</dt>
          <dd>
            {reconciliation.total_billed !== null ? (
              <MoneyDisplay value={reconciliation.total_billed} />
            ) : (
              <span aria-label="Not yet calculated">--</span>
            )}
          </dd>

          <dt>Total Paid</dt>
          <dd>
            {reconciliation.total_paid !== null ? (
              <MoneyDisplay value={reconciliation.total_paid} />
            ) : (
              <span aria-label="Not yet calculated">--</span>
            )}
          </dd>

          <dt>Variance</dt>
          <dd>
            {reconciliation.variance !== null ? (
              <MoneyDisplay value={reconciliation.variance} />
            ) : (
              <span aria-label="Not yet calculated">--</span>
            )}
          </dd>

          <dt>Created</dt>
          <dd>
            <time dateTime={reconciliation.created_at}>
              {new Date(reconciliation.created_at).toLocaleString()}
            </time>
          </dd>

          <dt>Updated</dt>
          <dd>
            <time dateTime={reconciliation.updated_at}>
              {new Date(reconciliation.updated_at).toLocaleString()}
            </time>
          </dd>

          {reconciliation.finalized_at && (
            <>
              <dt>Finalized At</dt>
              <dd>
                <time dateTime={reconciliation.finalized_at}>
                  {new Date(reconciliation.finalized_at).toLocaleString()}
                </time>
              </dd>
            </>
          )}
        </dl>
      </section>

      {showFinalizeAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="reconciliation-finalize-button"
            type="button"
            onClick={() => onFinalize(reconciliation.id)}
          >
            Finalize Reconciliation
          </button>
        </RbacGate>
      )}
    </div>
  );
}
