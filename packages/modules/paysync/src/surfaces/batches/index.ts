// packages/modules/paysync/src/surfaces/batches/index.ts
// Batches surface: surface descriptor + public component exports.
// Plan C adds BatchesListPage + BatchDetailPage (with RbacGate + ProvenanceBreadcrumb)
// and BFF route handlers wired to BatchesClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const BatchesSurface: SurfaceConfig = {
  id: "batches",
  path: "/admin/paysync/batches",
};

export { BatchesListPage, type BatchesListPageProps } from "./BatchesListPage.js";
export { BatchDetailPage, type BatchDetailPageProps } from "./BatchDetailPage.js";
export {
  handleListBatches,
  handleGetBatch,
} from "./bff/batches.js";
