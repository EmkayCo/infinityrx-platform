// packages/modules/paysync/src/surfaces/invoices/index.ts
// Invoices surface: surface descriptor + public component exports.

import type { SurfaceConfig } from "../../types/surface.js";

export const InvoicesSurface: SurfaceConfig = {
  id: "invoices",
  path: "/admin/paysync/invoices",
};

export { InvoicesListPage, type InvoicesListPageProps } from "./InvoicesListPage.js";
export { InvoiceDetailPage, type InvoiceDetailPageProps } from "./InvoiceDetailPage.js";
export { handleListInvoices, handleGetInvoice } from "./bff/invoices.js";
