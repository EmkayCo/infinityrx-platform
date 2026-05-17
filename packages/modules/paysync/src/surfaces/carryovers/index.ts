// packages/modules/paysync/src/surfaces/carryovers/index.ts
// Carryovers surface: surface descriptor + public component exports.
// Plan C Task 7 adds CarryoversListPage + CarryoverDetailPage (with RbacGate + ProvenanceBreadcrumb)
// and BFF route handlers wired to CarryoversClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const CarryoversSurface: SurfaceConfig = {
  id: "carryovers",
  path: "/admin/paysync/carryovers",
};

export { CarryoversListPage, type CarryoversListPageProps } from "./CarryoversListPage.js";
export { CarryoverDetailPage, type CarryoverDetailPageProps } from "./CarryoverDetailPage.js";
export {
  handleListCarryovers,
  handleGetCarryover,
} from "./bff/carryovers.js";
