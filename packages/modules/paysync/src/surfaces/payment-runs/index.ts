// packages/modules/paysync/src/surfaces/payment-runs/index.ts
// Payment-runs surface: surface descriptor + public component exports.

import type { SurfaceConfig } from "../../types/surface.js";

export const PaymentRunsSurface: SurfaceConfig = {
  id: "payment-runs",
  path: "/admin/paysync/payment-runs",
};

export { PaymentRunsListPage, type PaymentRunsListPageProps } from "./PaymentRunsListPage.js";
export { PaymentRunDetailPage, type PaymentRunDetailPageProps } from "./PaymentRunDetailPage.js";
export { ManualApForm, type ManualApFormProps, type ManualApEntry } from "./ManualApForm.js";
export { handleListPaymentRuns, handleGetPaymentRun } from "./bff/payment-runs.js";
