// packages/modules/paysync/src/inbox/ItemRegistry.ts
// Per-kind registry with REAL dynamic imports — replaces the Task 3 inline
// placeholders in the same commit that creates the 11 card stub files under
// ./cards/ (Plan A R4.3 atomicity). Each card import resolves to a typed
// default-export React component; subsequent plans (B–E) replace the stub
// body without changing the import path or shape.

import type { ComponentType } from "react";
import { INBOX_KIND_ROLE, type InboxItem, type InboxItemKind, type RbacRole } from "./types.js";

export type InboxCardComponent = ComponentType<{ item: InboxItem }>;

export interface InboxRegistration {
  readonly card: () => Promise<{ default: InboxCardComponent }>;
  readonly rbac_required: RbacRole;
}

export const ItemRegistry: Record<InboxItemKind, InboxRegistration> = {
  upload_pending_review:              { card: () => import("./cards/UploadPendingReviewCard.js"),    rbac_required: INBOX_KIND_ROLE.upload_pending_review },
  upload_validated_awaiting_batching: { card: () => import("./cards/UploadValidatedCard.js"),        rbac_required: INBOX_KIND_ROLE.upload_validated_awaiting_batching },
  cycle_pending_close:                { card: () => import("./cards/CyclePendingCloseCard.js"),      rbac_required: INBOX_KIND_ROLE.cycle_pending_close },
  cycle_close_review:                 { card: () => import("./cards/CycleCloseReviewCard.js"),       rbac_required: INBOX_KIND_ROLE.cycle_close_review },
  batch_drafted:                      { card: () => import("./cards/BatchDraftedCard.js"),           rbac_required: INBOX_KIND_ROLE.batch_drafted },
  ar_invoice_draft:                   { card: () => import("./cards/ArInvoiceDraftCard.js"),         rbac_required: INBOX_KIND_ROLE.ar_invoice_draft },
  ap_payment_run_held:                { card: () => import("./cards/ApPaymentRunHeldCard.js"),       rbac_required: INBOX_KIND_ROLE.ap_payment_run_held },
  banking_discrepancy:                { card: () => import("./cards/BankingDiscrepancyCard.js"),     rbac_required: INBOX_KIND_ROLE.banking_discrepancy },
  reconciliation_pending:             { card: () => import("./cards/ReconciliationPendingCard.js"),  rbac_required: INBOX_KIND_ROLE.reconciliation_pending },
  carryover_open:                     { card: () => import("./cards/CarryoverOpenCard.js"),          rbac_required: INBOX_KIND_ROLE.carryover_open },
  journal_periodic_review:            { card: () => import("./cards/JournalPeriodicReviewCard.js"),  rbac_required: INBOX_KIND_ROLE.journal_periodic_review },
};
