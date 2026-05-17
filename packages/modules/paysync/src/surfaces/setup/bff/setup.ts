// packages/modules/paysync/src/surfaces/setup/bff/setup.ts
// Next.js BFF route handlers for the paysync setup surface.
// READ handlers are implemented and proxied to the SetupClient interface.
// WRITE handlers are stubbed -- wire-up is Plan F+ scope.
// All mutations are Approver-only; server-side enforcement is required.
// TODO(Plan-F): implement upsert/delete handlers once backend endpoints exist.

export interface BffRequest {
  readonly headers: Record<string, string | undefined>;
  readonly searchParams?: URLSearchParams;
}

export interface BffResponse<T> {
  readonly data: T;
  readonly status: number;
  readonly headers: Record<string, string>;
}

export interface ListResponse<T> {
  readonly results: ReadonlyArray<T>;
  readonly total: number;
}

// Minimal SetupClient interface for the BFF layer.
// The full client implementation is Plan F+ scope once the billing backend
// exposes setup endpoints. These method signatures define the contract.
export interface SetupClient {
  listEmailRecipients(): Promise<ListResponse<unknown>>;
  listEmailTemplates(): Promise<ListResponse<unknown>>;
  listExportTemplates(): Promise<ListResponse<unknown>>;
  listGlAccountMappings(): Promise<ListResponse<unknown>>;
  listInvoiceSequences(): Promise<ListResponse<unknown>>;
  listCycleSchedules(): Promise<ListResponse<unknown>>;
}

/**
 * GET /api/paysync/setup/email-recipients
 * Lists all email notification recipients for the active tenant.
 */
export async function handleListEmailRecipients(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listEmailRecipients();
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/setup/email-templates
 * Lists all email notification templates for the active tenant.
 */
export async function handleListEmailTemplates(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listEmailTemplates();
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/setup/export-templates
 * Lists all export templates for the active tenant.
 */
export async function handleListExportTemplates(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listExportTemplates();
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/setup/gl-account-mappings
 * Lists all GL account mappings for the active tenant.
 */
export async function handleListGlAccountMappings(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listGlAccountMappings();
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/setup/invoice-sequences
 * Lists all invoice sequences for the active tenant.
 */
export async function handleListInvoiceSequences(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listInvoiceSequences();
  return { data, status: 200, headers: {} };
}

/**
 * GET /api/paysync/setup/cycle-schedules
 * Lists all cycle schedules for the active tenant.
 */
export async function handleListCycleSchedules(
  _req: BffRequest,
  client: SetupClient,
): Promise<BffResponse<ListResponse<unknown>>> {
  const data = await client.listCycleSchedules();
  return { data, status: 200, headers: {} };
}
