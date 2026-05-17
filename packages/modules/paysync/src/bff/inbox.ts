// packages/modules/paysync/src/bff/inbox.ts
// BFF function for GET /api/paysync/inbox?role=<role>.
// Plan B replaces the stub (always returned []) with a real call to InboxClient.
// The caller injects the InboxClient so this function is testable without HTTP.

import type { InboxItem, RbacRole } from "../inbox/types.js";

// Minimal interface for the InboxClient dependency — matches InboxClient from
// @infinityrx/contract without importing the full package here (avoids circular
// dep; the portal's route handler wires the concrete client).
export interface InboxClientLike {
  list(role: RbacRole): Promise<InboxItem[]>;
}

/**
 * Fetches inbox items for the given role from the billing backend via InboxClient.
 *
 * @param role    - The RBAC role to filter items by (Operator/Approver/Auditor).
 * @param client  - InboxClient instance (real or mock). Injected by the caller.
 * @returns       - Array of InboxItem for this role.
 */
export async function listInboxItems(
  role: RbacRole,
  client: InboxClientLike,
): Promise<InboxItem[]> {
  return client.list(role);
}
