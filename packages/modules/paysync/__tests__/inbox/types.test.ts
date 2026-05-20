// packages/modules/paysync/__tests__/inbox/types.test.ts
// Exhaustiveness check: every value in the InboxItemKind union has a
// corresponding entry in INBOX_KIND_ROLE. Catches kind additions that
// forget to map a role — would silently leave items unactionable.

import { describe, expect, it } from "vitest";
import { INBOX_KIND_ROLE, type InboxItemKind } from "../../src/inbox/types.js";

// Authoritative list — mirrors the union in types.ts. If the union grows,
// extend this list AND add a matching INBOX_KIND_ROLE entry. The
// exhaustiveness check below will fail loudly otherwise.
const KNOWN_KINDS: ReadonlyArray<InboxItemKind> = [
  "upload_pending_review",
  "upload_validated_awaiting_batching",
  "cycle_pending_close",
  "cycle_close_review",
  "batch_drafted",
  "ar_invoice_draft",
  "ap_payment_run_held",
  "banking_discrepancy",
  "reconciliation_pending",
  "carryover_open",
  "journal_periodic_review",
];

describe("INBOX_KIND_ROLE", () => {
  it("contains an entry for every known InboxItemKind", () => {
    const mappedKinds = Object.keys(INBOX_KIND_ROLE).sort();
    expect(mappedKinds).toEqual([...KNOWN_KINDS].sort());
  });

  it("maps every kind to a recognized RbacRole", () => {
    const validRoles = new Set(["operator", "approver", "auditor"]);
    for (const kind of KNOWN_KINDS) {
      expect(validRoles.has(INBOX_KIND_ROLE[kind])).toBe(true);
    }
  });

  it("upload kinds are operator-actionable", () => {
    expect(INBOX_KIND_ROLE.upload_pending_review).toBe("operator");
    expect(INBOX_KIND_ROLE.upload_validated_awaiting_batching).toBe("operator");
  });

  it("approval kinds are approver-actionable", () => {
    expect(INBOX_KIND_ROLE.cycle_close_review).toBe("approver");
    expect(INBOX_KIND_ROLE.batch_drafted).toBe("approver");
    expect(INBOX_KIND_ROLE.ar_invoice_draft).toBe("approver");
  });

  it("audit kind is auditor-actionable", () => {
    expect(INBOX_KIND_ROLE.journal_periodic_review).toBe("auditor");
  });
});
