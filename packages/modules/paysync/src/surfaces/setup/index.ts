// packages/modules/paysync/src/surfaces/setup/index.ts
// Setup surface: surface descriptor + public component exports.
// Plan E adds SetupHomePage + 6 setup area pages (email-recipients,
// email-templates, export-templates, gl-account-mappings, invoice-sequences,
// cycle-schedules) and BFF read handlers.
// All save/create/delete actions are Approver-only (RbacGate role="approver").
// Write wire-up is Plan F+ scope.

import type { SurfaceConfig } from "../../types/surface.js";

export const SetupSurface: SurfaceConfig = {
  id: "setup",
  path: "/admin/paysync/setup",
};

export { SetupHomePage } from "./SetupHomePage.js";

export { EmailRecipientsPage } from "./EmailRecipientsPage.js";
export type { EmailRecipientsPageProps, EmailRecipient } from "./EmailRecipientsPage.js";

export { EmailTemplatesPage } from "./EmailTemplatesPage.js";
export type { EmailTemplatesPageProps, EmailTemplate } from "./EmailTemplatesPage.js";

export { ExportTemplatesPage } from "./ExportTemplatesPage.js";
export type { ExportTemplatesPageProps, ExportTemplate, ExportFormat } from "./ExportTemplatesPage.js";

export { GlAccountMappingsPage } from "./GlAccountMappingsPage.js";
export type { GlAccountMappingsPageProps, GlAccountMapping } from "./GlAccountMappingsPage.js";

export { InvoiceSequencesPage } from "./InvoiceSequencesPage.js";
export type { InvoiceSequencesPageProps, InvoiceSequence } from "./InvoiceSequencesPage.js";

export { CycleSchedulesPage } from "./CycleSchedulesPage.js";
export type { CycleSchedulesPageProps, CycleSchedule, CycleFrequency } from "./CycleSchedulesPage.js";

export {
  handleListEmailRecipients,
  handleListEmailTemplates,
  handleListExportTemplates,
  handleListGlAccountMappings,
  handleListInvoiceSequences,
  handleListCycleSchedules,
} from "./bff/setup.js";
export type { BffRequest, BffResponse, SetupClient, ListResponse } from "./bff/setup.js";
