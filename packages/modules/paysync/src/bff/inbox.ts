// packages/modules/paysync/src/bff/inbox.ts
// BFF stub — STUB ONLY (not a complete Inbox implementation).
// Plan B replaces this with a real backend call to GET /api/v1/billing/inbox?role=<role>.
// The Plan A gate explicitly accepts this as stub-scope.

import type { InboxItem, RbacRole } from "../inbox/types.js";

/**
 * GET /api/paysync/inbox?role=<role>
 *
 * Plan A: returns an empty array regardless of role.
 * Plan B: proxies to billing module's real inbox endpoint and applies tenant
 *         + RBAC filtering before returning.
 */
export async function listInboxItems(_role: RbacRole): Promise<InboxItem[]> {
  return [];
}
