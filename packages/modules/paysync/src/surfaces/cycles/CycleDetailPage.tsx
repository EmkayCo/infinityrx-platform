// packages/modules/paysync/src/surfaces/cycles/CycleDetailPage.tsx
// Detail view for a single paysync billing cycle.
// - ProvenanceBreadcrumb: shows upload -> cycle chain when origin_upload_id is set.
// - RbacGate on close button: Operator role sees it disabled; Approver enabled.
//   Per spec §5.4: disabled is visible + aria-disabled, never hidden.
// - Close button only shown for cycles in "closing" status.

import type { ReactElement } from "react";
import type { Cycle } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";
import type { RbacRole } from "../../inbox/types.js";

export interface CycleDetailPageProps {
  readonly cycle: Cycle | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onClose: (cycleId: string) => void;
}

export function CycleDetailPage({
  cycle,
  isLoading,
  error,
  currentRole,
  onClose,
}: CycleDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="cycle-detail-loading" role="status" aria-label="Loading cycle">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="cycle-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!cycle) {
    return (
      <div data-testid="cycle-detail-page">
        <p>Cycle not found.</p>
      </div>
    );
  }

  // Build provenance chain when the cycle has a known origin upload.
  const provenanceChain: ProvenanceLink[] = cycle.origin_upload_id
    ? [
        {
          label: `Upload ${cycle.origin_upload_id.slice(0, 8)}...`,
          href: `/admin/paysync/uploads/${cycle.origin_upload_id}`,
        },
        {
          label: `Cycle ${cycle.period_label}`,
          href: `/admin/paysync/cycles/${cycle.id}`,
        },
      ]
    : [];

  // Close action is only available when the cycle is in "closing" status.
  // Approver role can execute it; all others see the button disabled via RbacGate.
  const showCloseAction = cycle.status === "closing";

  return (
    <div data-testid="cycle-detail-page">
      {provenanceChain.length > 0 && (
        <ProvenanceBreadcrumb chain={provenanceChain} />
      )}

      <h1>{cycle.period_label}</h1>

      <section aria-label="Cycle summary">
        <dl>
          <dt>Status</dt>
          <dd>
            <span data-testid="cycle-status-badge" data-status={cycle.status}>
              {cycle.status}
            </span>
          </dd>

          <dt>Claims</dt>
          <dd>{cycle.claim_count}</dd>

          <dt>Total Billed</dt>
          <dd>
            {cycle.total_billed_amount !== null ? (
              <MoneyDisplay value={cycle.total_billed_amount} />
            ) : (
              <span aria-label="not yet computed">-</span>
            )}
          </dd>

          <dt>Window Closed</dt>
          <dd>
            {cycle.window_closed_at !== null ? (
              <time dateTime={cycle.window_closed_at}>
                {new Date(cycle.window_closed_at).toLocaleString()}
              </time>
            ) : (
              <span>-</span>
            )}
          </dd>

          <dt>Created</dt>
          <dd>
            <time dateTime={cycle.created_at}>
              {new Date(cycle.created_at).toLocaleString()}
            </time>
          </dd>

          {cycle.origin_upload_id && (
            <>
              <dt>Origin Upload</dt>
              <dd>
                <a href={`/admin/paysync/uploads/${cycle.origin_upload_id}`}>
                  {cycle.origin_upload_id}
                </a>
              </dd>
            </>
          )}
        </dl>
      </section>

      {showCloseAction && (
        <RbacGate role="approver" currentRole={currentRole}>
          <button
            data-testid="cycle-close-button"
            type="button"
            onClick={() => onClose(cycle.id)}
          >
            Close Cycle
          </button>
        </RbacGate>
      )}
    </div>
  );
}
