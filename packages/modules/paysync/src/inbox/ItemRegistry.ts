// packages/modules/paysync/src/inbox/ItemRegistry.ts
// SELF-CONTAINED registry per Plan A R4.3 fix. Each kind's card is a typed
// placeholder factory in this commit. Task 5 replaces these placeholders with
// real dynamic imports pointing at ./cards/<Name>Card.js (lands in the same
// commit that creates the 11 stub files), so `tsc -b` always sees resolvable
// imports at every commit boundary.

import type { ComponentType } from "react";
import { INBOX_KIND_ROLE, type InboxItem, type InboxItemKind, type RbacRole } from "./types.js";

export type InboxCardComponent = ComponentType<{ item: InboxItem }>;

export interface InboxRegistration {
  readonly card: () => Promise<{ default: InboxCardComponent }>;
  readonly rbac_required: RbacRole;
}

// Placeholder factory returns a no-op component so dynamic-import resolution
// passes typecheck without requiring the card stub files yet. Task 5 replaces
// each entry with `card: () => import("./cards/<Name>Card.js")`.
const placeholderCard = async (): Promise<{ default: InboxCardComponent }> => ({
  default: () => null,
});

export const ItemRegistry: Record<InboxItemKind, InboxRegistration> = {
  upload_pending_review:              { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.upload_pending_review },
  upload_validated_awaiting_batching: { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.upload_validated_awaiting_batching },
  cycle_pending_close:                { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.cycle_pending_close },
  cycle_close_review:                 { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.cycle_close_review },
  batch_drafted:                      { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.batch_drafted },
  ar_invoice_draft:                   { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.ar_invoice_draft },
  ap_payment_run_held:                { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.ap_payment_run_held },
  banking_discrepancy:                { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.banking_discrepancy },
  reconciliation_pending:             { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.reconciliation_pending },
  carryover_open:                     { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.carryover_open },
  journal_periodic_review:            { card: placeholderCard, rbac_required: INBOX_KIND_ROLE.journal_periodic_review },
};
