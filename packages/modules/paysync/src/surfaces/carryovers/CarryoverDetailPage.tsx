// packages/modules/paysync/src/surfaces/carryovers/CarryoverDetailPage.tsx
// Detail view for a single carryover.
// - RbacGate on resolve action: Approver only.
// - ProvenanceBreadcrumb when originUploadId is provided.

import type { ReactElement } from "react";
import type { Carryover } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";
import { RbacGate } from "../../components/RbacGate.js";
import { ProvenanceBreadcrumb, type ProvenanceLink } from "../../components/ProvenanceBreadcrumb.js";
import type { RbacRole } from "../../inbox/types.js";

export interface CarryoverDetailPageProps {
  readonly carryover: Carryover | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly originUploadId?: string;
  readonly onResolve: (carryoverId: string) => void;
}

export function CarryoverDetailPage({
  carryover,
  isLoading,
  error,
  currentRole,
  originUploadId,
  onResolve,
}: CarryoverDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="carryover-detail-loading" role="status" aria-label="Loading carryover">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="carryover-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!carryover) {
    return (
      <div data-testid="carryover-detail-page">
        <p>Carryover not found.</p>
      </div>
    );
  }

  const provenanceChain: ProvenanceLink[] = originUploadId
    ? [
        {
          label: `Upload ${originUploadId.slice(0, 8)}...`,
          href: `/admin/paysync/uploads/${originUploadId}`,
        },
        {
          label: `Carryover ${carryover.id.slice(0, 8)}...`,
          href: `/admin/paysync/carryovers/${carryover.id}`,
        },
      ]
    : [];

  return (
    <div data-testid="carryover-detail-page">
      {provenanceChain.length > 0 && (
        <ProvenanceBreadcrumb chain={provenanceChain} />
      )}

      <h1>Carryover Details</h1>

      <section aria-label="Carryover summary">
        <dl>
          <dt>Member</dt>
          <dd>{carryover.member_id}</dd>

          <dt>Reason</dt>
          <dd>{carryover.reason}</dd>

          <dt>From Period</dt>
          <dd>{carryover.from_period}</dd>

          <dt>To Period</dt>
          <dd>{carryover.to_period}</dd>

          <dt>Original Amount</dt>
          <dd>
            <MoneyDisplay value={carryover.original_amount} />
          </dd>

          <dt>Carried Amount</dt>
          <dd>
            <MoneyDisplay value={carryover.carried_amount} />
          </dd>

          <dt>Created</dt>
          <dd>
            <time dateTime={carryover.created_at}>
              {new Date(carryover.created_at).toLocaleString()}
            </time>
          </dd>
        </dl>
      </section>

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          data-testid="carryover-resolve-button"
          type="button"
          onClick={() => onResolve(carryover.id)}
        >
          Resolve Carryover
        </button>
      </RbacGate>
    </div>
  );
}
