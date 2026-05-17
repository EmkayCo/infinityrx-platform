// packages/modules/paysync/src/index.ts
// Public surface of @infinityrx/module-paysync.
//
// Consumers (portal/operator, shell composition, qa-harness) import from
// '@infinityrx/module-paysync' which resolves to dist/src/index.js per the
// package.json `exports` field. The module's `module.config.ts` is read
// separately by build tooling via file-path glob and is NOT re-exported here.

// Inbox spine — types, registry, hook, queue component
export {
  INBOX_KIND_ROLE,
  type InboxItem,
  type InboxItemKind,
  type RbacRole,
} from "./inbox/types.js";
export {
  ItemRegistry,
  type InboxCardComponent,
  type InboxRegistration,
} from "./inbox/ItemRegistry.js";
export { useInboxItems, type UseInboxItemsResult } from "./inbox/useInboxItems.js";
export { InboxQueue, type InboxQueueProps } from "./inbox/InboxQueue.js";

// Module-local primitives (excludes dev-only/ — qa-harness reaches it via
// paysyncComposition.qa in module.config.ts under a NODE_ENV guard)
export {
  MoneyDisplay,
  type MoneyDisplayProps,
} from "./components/MoneyDisplay.js";
export {
  MoneyInput,
  type MoneyInputProps,
} from "./components/MoneyInput.js";
export {
  RbacGate,
  type RbacGateProps,
} from "./components/RbacGate.js";
export {
  ProvenanceBreadcrumb,
  type ProvenanceBreadcrumbProps,
  type ProvenanceLink,
} from "./components/ProvenanceBreadcrumb.js";
export {
  HashChainBadge,
  type HashChainBadgeProps,
} from "./components/HashChainBadge.js";

// Surface descriptor type + 13 surface configs
export type { SurfaceConfig } from "./types/surface.js";
export { UploadsSurface } from "./surfaces/uploads/index.js";
export { CyclesSurface } from "./surfaces/cycles/index.js";
export { BatchesSurface } from "./surfaces/batches/index.js";
export { CarryoversSurface } from "./surfaces/carryovers/index.js";
export { InvoicesSurface } from "./surfaces/invoices/index.js";
export { PaymentRunsSurface } from "./surfaces/payment-runs/index.js";
export { FilesSurface } from "./surfaces/files/index.js";
export { BankSettlementsSurface } from "./surfaces/bank-settlements/index.js";
export { ReconciliationsSurface } from "./surfaces/reconciliations/index.js";
export { JournalSurface } from "./surfaces/journal/index.js";
export { ReportsSurface } from "./surfaces/reports/index.js";
export { SetupSurface } from "./surfaces/setup/index.js";
export { EchoSurface } from "./surfaces/echo/index.js";
