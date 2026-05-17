// packages/modules/paysync/src/surfaces/bank-settlements/index.ts
// Bank-settlements surface: surface descriptor + public component exports.
// Plan C Task 7 adds BankSettlementsListPage + BankSettlementDetailPage (with RbacGate)
// and BFF route handlers wired to BankSettlementsClient from @infinityrx/contract.

import type { SurfaceConfig } from "../../types/surface.js";

export const BankSettlementsSurface: SurfaceConfig = {
  id: "bank-settlements",
  path: "/admin/paysync/settlements",
};

export { BankSettlementsListPage, type BankSettlementsListPageProps } from "./BankSettlementsListPage.js";
export { BankSettlementDetailPage, type BankSettlementDetailPageProps } from "./BankSettlementDetailPage.js";
export {
  handleListBankSettlements,
  handleGetBankSettlement,
} from "./bff/bank-settlements.js";
