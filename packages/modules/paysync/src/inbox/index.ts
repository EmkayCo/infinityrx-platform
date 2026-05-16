// packages/modules/paysync/src/inbox/index.ts
// Barrel for the Inbox spine.

export type {
  InboxItem,
  InboxItemKind,
  RbacRole,
} from "./types.js";
export { INBOX_KIND_ROLE } from "./types.js";
export type { InboxRegistration, InboxCardComponent } from "./ItemRegistry.js";
export { ItemRegistry } from "./ItemRegistry.js";
export { useInboxItems, type UseInboxItemsResult } from "./useInboxItems.js";
export { InboxQueue, type InboxQueueProps } from "./InboxQueue.js";
