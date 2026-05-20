// packages/modules/paysync/src/surfaces/payment-runs/PaymentRunDetailPage.tsx
// Detail view for a single payment run.
// - ProvenanceBreadcrumb: shown when originUploadId is provided.
// - RbacGate on release button: Operator disabled; Approver enabled.
// - Release only for "pending" or "held" runs.
// - Per spec: fail-fast on backend error — no optimistic commit; error toast must include correlation_id.

import type { ReactElement } from "react";
import type { PaymentRun } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";
import type { RbacRole } from "../../inbox/types.js";

export interface PaymentRunDetailPageProps {
  readonly run: PaymentRun | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly originUploadId?: string;
  readonly onRelease: (runId: string) => void;
}

export function PaymentRunDetailPage({
  run,
  isLoading,
  error,
  currentRole,
  originUploadId,
  onRelease,
}: PaymentRunDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="payment-run-detail-loading" role="status" aria-label="Loading payment run">
        Loading...
      </div>
    );
  }

  if (error) {
    return <div data-testid="payment-run-detail-error" role="alert">{error}</div>;
  }

  if (!run) {
    return <div data-testid="payment-run-detail-page"><p>Payment run not found.</p></div>;
  }

  const provenanceChain: ProvenanceLink[] = originUploadId
    ? [
        {
          label: `Upload ${originUploadId.slice(0, 8)}...`,
          href: `/admin/paysync/uploads/${originUploadId}`,
        },
        {
          label: `Run ${run.id.slice(0, 8)}...`,
          href: `/admin/paysync/payment-runs/${run.id}`,
        },
      ]
    : [];

  // Release available for "pending" and "held" runs only.
  // Held runs are the primary use case (OFAC hold lifted, manual review cleared).
  const showReleaseAction = run.status === "pending" || run.status === "held";

  return (
    <div data-testid="payment-run-detail-page">
      {provenanceChain.length > 0 && <ProvenanceBreadcrumb chain={provenanceChain} />}

      <h1>Payment Run</h1>

      <section aria-label="Payment run summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="payment-run-status-badge" data-status={run.status}>
              {run.status}
            </span>
          </dd>
          <dt>Batch</dt>
          <dd>
            <a href={`/admin/paysync/batches/${run.batch_id}`}>
              {run.batch_id.slice(0, 8)}...
            </a>
          </dd>
          <dt>Payments</dt><dd>{run.payment_count}</dd>
          <dt>Total Amount</dt><dd><MoneyDisplay value={run.total_amount} /></dd>
          <dt>Run At</dt>
          <dd><time dateTime={run.run_at}>{new Date(run.run_at).toLocaleString()}</time></dd>
          <dt>Completed At</dt>
          <dd>
            {run.completed_at !== null ? (
              <time dateTime={run.completed_at}>{new Date(run.completed_at).toLocaleString()}</time>
            ) : (
              <span aria-label="not yet completed">-</span>
            )}
          </dd>
          <dt>Created</dt>
          <dd><time dateTime={run.created_at}>{new Date(run.created_at).toLocaleString()}</time></dd>
        </dl>
      </section>

      {showReleaseAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="payment-run-release-button"
            type="button"
            onClick={() => onRelease(run.id)}
          >
            Release Payment Run
          </button>
        </RbacGate>
      )}
    </div>
  );
}
