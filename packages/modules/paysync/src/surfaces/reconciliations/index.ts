// packages/modules/paysync/src/surfaces/reconciliations/index.ts
// Reconciliations surface: surface descriptor + public component exports.
// Plan C Task 7 adds ReconciliationsListPage + ReconciliationDetailPage (with RbacGate)
// and BFF route handlers wired to ReconciliationsClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const ReconciliationsSurface: SurfaceConfig = {
  id: "reconciliations",
  path: "/admin/paysync/reconcile",
};

export { ReconciliationsListPage, type ReconciliationsListPageProps } from "./ReconciliationsListPage.js";
export { ReconciliationDetailPage, type ReconciliationDetailPageProps } from "./ReconciliationDetailPage.js";
export {
  handleListReconciliations,
  handleGetReconciliation,
} from "./bff/reconciliations.js";
