// packages/modules/paysync/src/surfaces/batches/BatchDetailPage.tsx
// Detail view for a single payment batch.
// - ProvenanceBreadcrumb: shown when originUploadId is provided (upload -> batch chain).
// - RbacGate on release button: Operator sees it disabled; Approver enabled.
//   Per spec: disabled is visible + aria-disabled, never hidden.
// - Release action only available for batches in "approved" status.
// - Hold action available for "approved" and "validated" batches.

import type { ReactElement } from "react";
import type { Batch } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";
import type { RbacRole } from "../../inbox/types.js";

export interface BatchDetailPageProps {
  readonly batch: Batch | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  /** Upload ID from which this batch originated, for provenance chain. */
  readonly originUploadId?: string;
  readonly onRelease: (batchId: string) => void;
  readonly onHold: (batchId: string) => void;
}

export function BatchDetailPage({
  batch,
  isLoading,
  error,
  currentRole,
  originUploadId,
  onRelease,
  onHold,
}: BatchDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="batch-detail-loading" role="status" aria-label="Loading batch">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="batch-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!batch) {
    return (
      <div data-testid="batch-detail-page">
        <p>Batch not found.</p>
      </div>
    );
  }

  // Build provenance chain when the batch has a known origin upload.
  const provenanceChain: ProvenanceLink[] = originUploadId
    ? [
        {
          label: `Upload ${originUploadId.slice(0, 8)}...`,
          href: `/admin/paysync/uploads/${originUploadId}`,
        },
        {
          label: batch.batch_number,
          href: `/admin/paysync/batches/${batch.id}`,
        },
      ]
    : [];

  // Release action only available for "approved" batches.
  // Hold action available for "approved" and "validated" batches.
  const showReleaseAction = batch.status === "approved";
  const showHoldAction = batch.status === "approved" || batch.status === "validated";

  return (
    <div data-testid="batch-detail-page">
      {provenanceChain.length > 0 && (
        <ProvenanceBreadcrumb chain={provenanceChain} />
      )}

      <h1>{batch.batch_number}</h1>

      <section aria-label="Batch summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="batch-status-badge" data-status={batch.status}>
              {batch.status}
            </span>
          </dd>

          <dt>Payment Route</dt>
          <dd>{batch.payment_route}</dd>

          <dt>Payments</dt>
          <dd>{batch.payment_count}</dd>

          <dt>AP Count</dt>
          <dd>{batch.ap_count}</dd>

          <dt>Total Amount</dt>
          <dd>
            <MoneyDisplay value={batch.total_amount} />
          </dd>

          <dt>Created</dt>
          <dd>
            <time dateTime={batch.created_at}>
              {new Date(batch.created_at).toLocaleString()}
            </time>
          </dd>

          <dt>Updated</dt>
          <dd>
            <time dateTime={batch.updated_at}>
              {new Date(batch.updated_at).toLocaleString()}
            </time>
          </dd>
        </dl>
      </section>

      {showReleaseAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="batch-release-button"
            type="button"
            onClick={() => onRelease(batch.id)}
          >
            Release Batch
          </button>
        </RbacGate>
      )}

      {showHoldAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="batch-hold-button"
            type="button"
            onClick={() => onHold(batch.id)}
          >
            Hold Batch
          </button>
        </RbacGate>
      )}
    </div>
  );
}
