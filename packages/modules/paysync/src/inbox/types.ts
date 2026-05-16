// packages/modules/paysync/src/inbox/types.ts
// Authoritative Inbox taxonomy per SP-1 spec §5.3.
// Add new kinds here first; ItemRegistry registers the card component.

export type RbacRole = "operator" | "approver" | "auditor";

export type InboxItemKind =
  | "upload_pending_review"
  | "upload_validated_awaiting_batching"
  | "cycle_pending_close"
  | "cycle_close_review"
  | "batch_drafted"
  | "ar_invoice_draft"
  | "ap_payment_run_held"
  | "banking_discrepancy"
  | "reconciliation_pending"
  | "carryover_open"
  | "journal_periodic_review";

export type InboxItem = {
  readonly id: string;
  readonly kind: InboxItemKind;
  readonly tenant_id: string;
  // Provenance link to the upload that produced this item.
  // null only for journal_periodic_review (system-generated, not upload-scoped).
  readonly upload_id: string | null;
  readonly rbac_required: RbacRole;
  readonly created_at: string; // ISO 8601
  readonly priority: "normal" | "high";
  // Discriminated-union payload per kind lands in Plan B+ when real items
  // start flowing. For now the registry treats it as opaque.
  readonly payload: Record<string, unknown>;
};

// Maps each InboxItemKind to the role that must action it.
// Exhaustiveness verified by types.test.ts.
export const INBOX_KIND_ROLE: Record<InboxItemKind, RbacRole> = {
  upload_pending_review:              "operator",
  upload_validated_awaiting_batching: "operator",
  cycle_pending_close:                "operator",
  carryover_open:                     "operator",
  cycle_close_review:                 "approver",
  batch_drafted:                      "approver",
  ar_invoice_draft:                   "approver",
  ap_payment_run_held:                "approver",
  banking_discrepancy:                "approver",
  reconciliation_pending:             "approver",
  journal_periodic_review:            "auditor",
};
