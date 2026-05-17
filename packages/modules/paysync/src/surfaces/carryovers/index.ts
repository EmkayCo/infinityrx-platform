// packages/modules/paysync/src/surfaces/carryovers/index.ts
// Carryovers surface: surface descriptor + public component exports.
// Plan C Task 7 adds CarryoversListPage + CarryoverDetailPage (with RbacGate + ProvenanceBreadcrumb)
// and BFF route handlers wired to CarryoversClient from @infinityrx/contract.
// TODO(sp-1-c-C4-followup): re-render carryovers surface for AP-carryforward fields
// (ap_record_id, amount, resolved, resolved_at, resolved_by, upload_id).
// CarryoverSchema was rewritten in fix(sp-1-c-C4); components still render old
// member-accumulator fields (member_id, carried_amount, etc.) and will break at
// runtime. Update components + BFF + client.ts filter params in Task 7.

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
