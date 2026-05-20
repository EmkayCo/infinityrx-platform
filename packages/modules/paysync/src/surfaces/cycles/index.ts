// packages/modules/paysync/src/surfaces/cycles/index.ts
// Cycles surface: surface descriptor + public component exports.
// Plan B adds CyclesListPage + CycleDetailPage (with RbacGate + ProvenanceBreadcrumb)
// and BFF route handlers wired to CyclesClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const CyclesSurface: SurfaceConfig = {
  id: "cycles",
  path: "/admin/paysync/cycles",
};

export { CyclesListPage, type CyclesListPageProps } from "./CyclesListPage.js";
export { CycleDetailPage, type CycleDetailPageProps } from "./CycleDetailPage.js";
export {
  handleListCycles,
  handleGetCycle,
  handleCloseCycle,
} from "./bff/cycles.js";
