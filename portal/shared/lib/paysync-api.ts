// PaySync admin API client — wraps the Wave 35-39 admin endpoints
// mounted on adjudication-engine's /admin/paysync/* and
// /admin/network/* surfaces.
//
// All paysync write endpoints require platform_admin; reads accept
// operator | platform_admin. The backend returns structured
// {error: {code, message, correlation_id, field?}} bodies that
// ApiClientError surfaces.

import { apiGet, apiPost, apiPatch, apiDelete, buildUrl } from "./api-client";
import { API_URLS } from "./constants";

const PAYSYNC_BASE = `${API_URLS.adjudicationEngine}/admin/paysync`;
const NETWORK_BASE = `${API_URLS.adjudicationEngine}/admin/network`;

// ─── Common types ─────────────────────────────────────────────

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PageQuery {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}

// ─── Cycles ───────────────────────────────────────────────────

export type CycleType = "payment_cycle" | "invoice_cycle";
export type CycleStatus =
  | "open"
  | "closing"
  | "closed"
  | "invoiced"
  | "paid"
  | "reconciled"
  | "closed_finalized";

export interface Cycle {
  id: string;
  tenant_id: string;
  cycle_label: string;
  cycle_type: CycleType;
  schedule_id: string | null;
  schedule_name: string | null;
  period_start: string;
  period_end: string;
  status: CycleStatus;
  claim_count: number;
  total_billed: string;
  total_pay: string;
  reconciliation_status: "pending" | "partial" | "matched" | "mismatched" | null;
  created_at: string;
  closed_at: string | null;
}

export interface CycleListQuery extends PageQuery {
  cycle_type?: CycleType;
  status?: CycleStatus;
  period_start_gte?: string;
  period_end_lte?: string;
  schedule_id?: string;
}

export async function listCycles(q: CycleListQuery = {}): Promise<Page<Cycle>> {
  return apiGet<Page<Cycle>>(buildUrl(`${PAYSYNC_BASE}/cycles`, q));
}

export async function getCycle(cycleId: string): Promise<Cycle> {
  return apiGet<Cycle>(`${PAYSYNC_BASE}/cycles/${cycleId}`);
}

// ─── Cycle close ──────────────────────────────────────────────

export type CloseStepName =
  | "preflight"
  | "hold_detection"
  | "manual_ap_recognition"
  | "carryover_ingestion"
  | "batch_generation"
  | "nacha_generation"
  | "eight_thirty_five_generation"
  | "invoice_generation"
  | "reconciliation"
  | "finalization";

export type StepState = "pending" | "running" | "succeeded" | "skipped" | "failed";

export interface CloseStepStatus {
  name: CloseStepName;
  state: StepState;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  metrics: Record<string, unknown>;
}

export interface CycleCloseRun {
  id: string;
  cycle_id: string;
  status: "in_progress" | "succeeded" | "failed";
  started_at: string;
  finished_at: string | null;
  initiated_by: string | null;
  override_pending_manual_ap: boolean;
  step_status: CloseStepStatus[];
  error_message: string | null;
}

export interface CloseCycleRequest {
  invoice_cycle_ids?: string[];
  override_pending_manual_ap?: boolean;
  effective_period_end?: string;
}

export async function closeCycle(
  cycleId: string,
  body: CloseCycleRequest = {},
): Promise<CycleCloseRun> {
  return apiPost<CycleCloseRun>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/close`, body,
  );
}

export async function getCloseStatus(cycleId: string): Promise<CycleCloseRun | null> {
  return apiGet<CycleCloseRun | null>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/close-status`,
  );
}

// ─── Reconciliation ───────────────────────────────────────────

export type TieStatus = "match" | "mismatch";

export interface TieResult {
  status: TieStatus;
  expected: string;
  actual: string;
  delta: string;
  reasons: string[];
}

export interface ReconciliationFinding {
  tie: 1 | 2 | 3;
  category: string;
  detail: string;
  amount: string | null;
  related_entity_id: string | null;
}

export interface CycleReconciliation {
  id: string;
  cycle_id: string;
  run_at: string;
  run_by: string | null;
  tie_1: TieResult;
  tie_2: TieResult;
  tie_3: TieResult;
  findings: ReconciliationFinding[];
  finalized: boolean;
  finalized_at: string | null;
  finalized_by: string | null;
  accepted_deltas: boolean;
  operator_notes: string | null;
}

export async function runReconciliation(cycleId: string): Promise<CycleReconciliation> {
  return apiPost<CycleReconciliation>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/reconcile`, {},
  );
}

export async function listReconciliations(cycleId: string): Promise<CycleReconciliation[]> {
  return apiGet<CycleReconciliation[]>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/reconciliations`,
  );
}

export interface FinalizeReconciliationRequest {
  accepted_deltas: boolean;
  operator_notes?: string;
}

export async function finalizeReconciliation(
  reconId: string,
  body: FinalizeReconciliationRequest,
): Promise<CycleReconciliation> {
  return apiPost<CycleReconciliation>(
    `${PAYSYNC_BASE}/reconciliations/${reconId}/finalize`, body,
  );
}

// ─── Claims (cycle-scoped detail) ─────────────────────────────

export interface PaysyncClaim {
  id: string;
  auth_num: string;
  date_of_service: string;
  pharmacy_npi: string;
  pharmacy_name: string | null;
  ndc: string;
  group_id: string | null;
  client_billed: string;
  total_pay: string;
  channel: string | null;
  sub_channel: string | null;
  status: string;
  has_hold: boolean;
  has_manual_ap: boolean;
  has_carryover: boolean;
  payment_cycle_id: string | null;
  invoice_cycle_id: string | null;
  reversed_auth_num: string | null;
}

export interface ClaimListQuery extends PageQuery {
  pharmacy_npi?: string;
  ndc?: string;
  group_id?: string;
  status?: string;
  has_hold?: boolean;
  has_manual_ap?: boolean;
  has_carryover?: boolean;
}

export async function listCycleClaims(
  cycleId: string, q: ClaimListQuery = {},
): Promise<Page<PaysyncClaim>> {
  return apiGet<Page<PaysyncClaim>>(
    buildUrl(`${PAYSYNC_BASE}/cycles/${cycleId}/claims`, q),
  );
}

// ─── Holds ────────────────────────────────────────────────────

export interface HeldClaim {
  id: string;
  cycle_id: string;
  claim_id: string;
  auth_num: string;
  pharmacy_npi: string;
  reason: string;
  held_at: string;
  held_by: string | null;
  released_at: string | null;
  released_by: string | null;
  released_reason: string | null;
}

export async function listHeldClaims(cycleId: string): Promise<HeldClaim[]> {
  return apiGet<HeldClaim[]>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/held-claims`,
  );
}

export async function autoHoldCycle(cycleId: string): Promise<{ held_count: number }> {
  return apiPost<{ held_count: number }>(
    `${PAYSYNC_BASE}/cycles/${cycleId}/auto-hold`, {},
  );
}

export async function releaseHeldClaim(
  heldId: string, reason: string,
): Promise<HeldClaim> {
  return apiPost<HeldClaim>(
    `${PAYSYNC_BASE}/held-claims/${heldId}/release`, { reason },
  );
}

// ─── Manual AP ────────────────────────────────────────────────

export type ManualApStatus =
  | "draft" | "pending" | "recognized" | "submitted" | "processed"
  | "failed" | "voided";

export interface ManualApRecord {
  id: string;
  cycle_id: string | null;
  claim_id: string | null;
  channel: string;
  payee_name: string;
  payee_npi: string | null;
  payment_amount: string;
  external_reference: string | null;
  status: ManualApStatus;
  submitted_at: string | null;
  processed_at: string | null;
  failure_reason: string | null;
  notes: string | null;
  created_at: string;
}

export interface ManualApListQuery extends PageQuery {
  cycle_id?: string;
  channel?: string;
  status?: ManualApStatus;
  date_from?: string;
  date_to?: string;
  payee_npi?: string;
}

export async function listManualAp(q: ManualApListQuery = {}): Promise<Page<ManualApRecord>> {
  return apiGet<Page<ManualApRecord>>(
    buildUrl(`${PAYSYNC_BASE}/manual-ap-records`, q),
  );
}

export interface CreateManualApRequest {
  channel: string;
  payee_name: string;
  payee_npi?: string;
  payment_amount: string;
  external_reference?: string;
  cycle_id?: string;
  claim_id?: string;
  notes?: string;
}

export async function createManualAp(
  body: CreateManualApRequest,
): Promise<ManualApRecord> {
  return apiPost<ManualApRecord>(`${PAYSYNC_BASE}/manual-ap-records`, body);
}

export async function updateManualApStatus(
  id: string, status: ManualApStatus, failure_reason?: string,
): Promise<ManualApRecord> {
  return apiPatch<ManualApRecord>(
    `${PAYSYNC_BASE}/manual-ap-records/${id}`,
    { status, failure_reason },
  );
}

// ─── Carryovers ───────────────────────────────────────────────

export type CarryoverType =
  | "pharmacy_owes_remainder"
  | "pharmacy_overpayment"
  | "failed_manual_ap"
  | "bank_return_bounce"
  | "statement_underpayment"
  | "rebate_offset"
  | "correction_adjustment";

export type CarryoverDirection = "we_owe_pharmacy" | "pharmacy_owes_us";

export interface Carryover {
  id: string;
  carryover_type: CarryoverType;
  direction: CarryoverDirection;
  amount: string;
  pay_to_entity_id: string | null;
  pay_to_external_id: string | null;
  origin_cycle_id: string | null;
  resolution_cycle_id: string | null;
  status: "open" | "applied" | "written_off";
  source_type: string;
  source_id: string;
  notes: string | null;
  created_at: string;
}

export interface CarryoverListQuery extends PageQuery {
  carryover_type?: CarryoverType;
  direction?: CarryoverDirection;
  status?: string;
  origin_cycle_id?: string;
  resolution_cycle_id?: string;
  pay_to_entity_id?: string;
}

export async function listCarryovers(q: CarryoverListQuery = {}): Promise<Page<Carryover>> {
  return apiGet<Page<Carryover>>(buildUrl(`${PAYSYNC_BASE}/carryovers`, q));
}

export async function resolveCarryover(
  id: string, resolution_method: string, notes?: string,
): Promise<Carryover> {
  return apiPost<Carryover>(
    `${PAYSYNC_BASE}/carryovers/${id}/resolve`,
    { resolution_method, notes },
  );
}

export async function writeOffCarryover(id: string, reason: string): Promise<Carryover> {
  return apiPost<Carryover>(
    `${PAYSYNC_BASE}/carryovers/${id}/write-off`, { reason },
  );
}

// ─── Batches ──────────────────────────────────────────────────

export type BatchStatus =
  | "draft" | "pending_approval" | "approved" | "submitted"
  | "settled" | "reconciled" | "voided" | "failed";

export interface PaymentBatch {
  id: string;
  cycle_id: string;
  cycle_label: string;
  batch_number: number;
  status: BatchStatus;
  effective_entry_date: string;
  file_id_modifier: string;
  entry_class_code: string | null;
  total_credit_amount: string;
  credit_entry_count: number;
  claim_count: number;
  created_at: string;
  approved_at: string | null;
  submitted_at: string | null;
}

export interface BatchListQuery extends PageQuery {
  cycle_id?: string;
  status?: BatchStatus;
  pay_to_entity_id?: string;
  date_from?: string;
  date_to?: string;
}

export async function listBatches(q: BatchListQuery = {}): Promise<Page<PaymentBatch>> {
  return apiGet<Page<PaymentBatch>>(buildUrl(`${PAYSYNC_BASE}/batches`, q));
}

export async function getBatch(id: string): Promise<PaymentBatch> {
  return apiGet<PaymentBatch>(`${PAYSYNC_BASE}/batches/${id}`);
}

export interface BatchCredit {
  id: string;
  pay_to_entity_id: string;
  pay_to_external_id: string;
  pay_to_name: string;
  pay_to_type: string;
  credit_amount: string;
  claim_count: number;
  banking_account_last_four: string | null;
  banking_routing: string | null;
  trace_number: string | null;
  entry_class_code: string;
  claim_ids: string[];
}

export async function listBatchCredits(batchId: string): Promise<BatchCredit[]> {
  return apiGet<BatchCredit[]>(`${PAYSYNC_BASE}/batches/${batchId}/credits`);
}

export interface BatchAuditEntry {
  id: string;
  event_type: string;
  occurred_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

export async function listBatchAudit(batchId: string): Promise<BatchAuditEntry[]> {
  return apiGet<BatchAuditEntry[]>(`${PAYSYNC_BASE}/batches/${batchId}/audit-log`);
}

export async function approveBatch(batchId: string): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(`${PAYSYNC_BASE}/batches/${batchId}/approve`, {});
}

export async function voidBatch(batchId: string, reason: string): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(
    `${PAYSYNC_BASE}/batches/${batchId}/void`, { reason },
  );
}

export interface GenerateNachaResponse {
  batch_id: string;
  file_id: string;
  file_path: string;
  sha256: string;
  size_bytes: number;
  trace_count: number;
}

export async function generateNacha(batchId: string): Promise<GenerateNachaResponse> {
  return apiPost<GenerateNachaResponse>(
    `${PAYSYNC_BASE}/batches/${batchId}/generate-nacha`, {},
  );
}

export interface Generate835Response {
  batch_id: string;
  files: Array<{
    pay_to_entity_id: string;
    destination_id: string | null;
    file_id: string;
    file_path: string;
    sha256: string;
    size_bytes: number;
  }>;
}

export async function generate835(
  batchId: string, pay_to_entity_id?: string,
): Promise<Generate835Response> {
  return apiPost<Generate835Response>(
    `${PAYSYNC_BASE}/batches/${batchId}/generate-835`,
    pay_to_entity_id ? { pay_to_entity_id } : {},
  );
}

// ─── Files ────────────────────────────────────────────────────

export interface PaysyncFile {
  id: string;
  cycle_id: string | null;
  batch_id: string | null;
  invoice_id: string | null;
  file_type: string;
  file_path: string;
  sha256: string;
  size_bytes: number;
  pay_to_entity_id: string | null;
  created_at: string;
}

export async function listCycleFiles(cycleId: string): Promise<PaysyncFile[]> {
  return apiGet<PaysyncFile[]>(`${PAYSYNC_BASE}/cycles/${cycleId}/files`);
}

export async function downloadFileUrl(fileId: string): Promise<{ url: string; expires_at: string }> {
  return apiGet<{ url: string; expires_at: string }>(
    `${PAYSYNC_BASE}/files/${fileId}/download-url`,
  );
}

// ─── Invoices ────────────────────────────────────────────────

export type InvoiceSequenceType = "reimbursement" | "client_fees";
export type InvoiceStatus =
  | "draft" | "finalized" | "sent" | "paid" | "partial" | "reconciled" | "voided";

export interface Invoice {
  id: string;
  invoice_number: string;
  sequence_type: InvoiceSequenceType;
  cycle_id: string;
  cycle_label: string;
  bill_to_id: string;
  bill_to_name: string;
  invoice_date: string;
  due_date: string | null;
  total_amount: string;
  paid_amount: string;
  status: InvoiceStatus;
  sent_at: string | null;
  paid_at: string | null;
  voided_at: string | null;
  created_at: string;
}

export interface InvoiceListQuery extends PageQuery {
  cycle_id?: string;
  sequence_type?: InvoiceSequenceType;
  bill_to_id?: string;
  status?: InvoiceStatus;
  date_from?: string;
  date_to?: string;
}

export async function listInvoices(q: InvoiceListQuery = {}): Promise<Page<Invoice>> {
  return apiGet<Page<Invoice>>(buildUrl(`${PAYSYNC_BASE}/invoices`, q));
}

export async function getInvoice(id: string): Promise<Invoice> {
  return apiGet<Invoice>(`${PAYSYNC_BASE}/invoices/${id}`);
}

export interface InvoiceLine {
  id: string;
  invoice_id: string;
  line_number: number;
  line_type: string;
  description: string;
  quantity: string;
  unit_amount: string;
  line_amount: string;
  source_claim_id: string | null;
  gl_account: string | null;
}

export async function listInvoiceLines(invoiceId: string): Promise<InvoiceLine[]> {
  return apiGet<InvoiceLine[]>(`${PAYSYNC_BASE}/invoices/${invoiceId}/lines`);
}

export interface InvoiceAttachment {
  id: string;
  invoice_id: string;
  attachment_type: string;
  file_path: string;
  sha256: string;
  size_bytes: number;
  created_at: string;
}

export async function listInvoiceAttachments(invoiceId: string): Promise<InvoiceAttachment[]> {
  return apiGet<InvoiceAttachment[]>(
    `${PAYSYNC_BASE}/invoices/${invoiceId}/attachments`,
  );
}

export interface EmailDelivery {
  id: string;
  invoice_id: string;
  to_addresses: string[];
  cc_addresses: string[];
  subject: string;
  status: "pending" | "sent" | "failed";
  sent_at: string | null;
  failure_reason: string | null;
  attachment_paths: string[];
}

export async function listInvoiceEmailDeliveries(invoiceId: string): Promise<EmailDelivery[]> {
  return apiGet<EmailDelivery[]>(
    `${PAYSYNC_BASE}/invoices/${invoiceId}/email-deliveries`,
  );
}

export interface InvoiceAuditEntry {
  id: string;
  event_type: string;
  occurred_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

export async function listInvoiceAudit(invoiceId: string): Promise<InvoiceAuditEntry[]> {
  return apiGet<InvoiceAuditEntry[]>(
    `${PAYSYNC_BASE}/invoices/${invoiceId}/audit-log`,
  );
}

export async function generateReimbursementInvoice(cycle_id: string, bill_to_id: string): Promise<Invoice> {
  return apiPost<Invoice>(
    `${PAYSYNC_BASE}/invoices/generate-reimbursement`,
    { cycle_id, bill_to_id },
  );
}

export async function generateClientFeeInvoice(
  cycle_id: string, bill_to_id: string, fee_schedule_id: string,
): Promise<Invoice> {
  return apiPost<Invoice>(
    `${PAYSYNC_BASE}/invoices/generate-client-fees`,
    { cycle_id, bill_to_id, fee_schedule_id },
  );
}

export async function finalizeInvoice(id: string): Promise<Invoice> {
  return apiPost<Invoice>(`${PAYSYNC_BASE}/invoices/${id}/finalize`, {});
}

export interface SendInvoiceRequest {
  override_recipients?: string[];
  override_subject?: string;
  override_body?: string;
  is_resend?: boolean;
}

export async function sendInvoice(
  id: string, body: SendInvoiceRequest = {},
): Promise<EmailDelivery> {
  return apiPost<EmailDelivery>(`${PAYSYNC_BASE}/invoices/${id}/send`, body);
}

export interface MarkPaidRequest {
  paid_amount: string;
  reference?: string;
  paid_at?: string;
}

export async function markInvoicePaid(
  id: string, body: MarkPaidRequest,
): Promise<Invoice> {
  return apiPost<Invoice>(`${PAYSYNC_BASE}/invoices/${id}/mark-paid`, body);
}

export interface VoidInvoiceRequest {
  reason: string;
  force_paid_void?: boolean;
}

export async function voidInvoice(id: string, body: VoidInvoiceRequest): Promise<Invoice> {
  return apiPost<Invoice>(`${PAYSYNC_BASE}/invoices/${id}/void`, body);
}

// ─── Network Management ──────────────────────────────────────

export type EntityType =
  | "pharmacy_npi" | "chain" | "pay_center" | "manufacturer" | "client";

export interface PayToEntity {
  id: string;
  external_id: string;
  name: string;
  entity_type: EntityType;
  status: string;
  effective_from: string;
  termination_date: string | null;
  has_active_banking: boolean;
  contract_count: number;
}

export interface PayToListQuery extends PageQuery {
  entity_type?: EntityType;
  status?: string;
  has_banking?: boolean;
  search?: string;
}

export async function listPayToEntities(q: PayToListQuery = {}): Promise<Page<PayToEntity>> {
  return apiGet<Page<PayToEntity>>(buildUrl(`${NETWORK_BASE}/pay-to-entities`, q));
}

export async function getPayToEntity(id: string): Promise<PayToEntity> {
  return apiGet<PayToEntity>(`${NETWORK_BASE}/pay-to-entities/${id}`);
}

export interface BankingRecord {
  id: string;
  pay_to_entity_id: string;
  routing_number: string;
  account_number_last_four: string;
  account_type: string;
  effective_from: string;
  termination_date: string | null;
  source: string;
  verified_at: string | null;
  verified_by: string | null;
  is_active: boolean;
}

export async function getBankingForEntity(entityId: string): Promise<BankingRecord[]> {
  return apiGet<BankingRecord[]>(
    `${NETWORK_BASE}/banking/by-entity/${entityId}`,
  );
}

export interface CreateBankingRequest {
  pay_to_entity_id: string;
  routing_number: string;
  account_number: string;
  account_type: "checking" | "savings" | "business_checking" | "business_savings";
  effective_from?: string;
  source?: string;
}

export async function createBanking(body: CreateBankingRequest): Promise<BankingRecord> {
  return apiPost<BankingRecord>(`${NETWORK_BASE}/banking`, body);
}

export async function verifyBanking(id: string): Promise<BankingRecord> {
  return apiPost<BankingRecord>(`${NETWORK_BASE}/banking/${id}/verify`, {});
}

export async function terminateBanking(id: string, reason: string): Promise<BankingRecord> {
  return apiPost<BankingRecord>(
    `${NETWORK_BASE}/banking/${id}/terminate`, { reason },
  );
}

export interface BankingChangeLogEntry {
  id: string;
  pay_to_entity_id: string;
  banking_id: string;
  change_type: string;
  occurred_at: string;
  actor: string | null;
  metadata: Record<string, unknown>;
}

export async function listBankingChangeLog(entityId: string): Promise<BankingChangeLogEntry[]> {
  return apiGet<BankingChangeLogEntry[]>(
    `${NETWORK_BASE}/banking/by-entity/${entityId}/change-log`,
  );
}

export interface BankingDiscrepancyReview {
  id: string;
  pay_to_entity_id: string;
  pay_to_name: string;
  imported_routing: string;
  imported_account_last_four: string;
  network_routing: string;
  network_account_last_four: string;
  status: "pending" | "resolved" | "dismissed";
  detected_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution: string | null;
}

export async function listBankingDiscrepancies(
  q: PageQuery & { status?: string } = {},
): Promise<Page<BankingDiscrepancyReview>> {
  return apiGet<Page<BankingDiscrepancyReview>>(
    buildUrl(`${NETWORK_BASE}/banking-discrepancy-reviews`, q),
  );
}

export async function resolveBankingDiscrepancy(
  id: string,
  resolution: "keep_network" | "accept_imported" | "ignore",
  notes?: string,
): Promise<BankingDiscrepancyReview> {
  return apiPost<BankingDiscrepancyReview>(
    `${NETWORK_BASE}/banking-discrepancy-reviews/${id}/resolve`,
    { resolution, notes },
  );
}

export interface TenantAchOrigination {
  id: string;
  tenant_id: string;
  immediate_destination: string;
  immediate_origin: string;
  originating_dfi_id: string;
  company_name: string;
  company_identification: string;
  company_entry_description: string;
  service_class_code: string;
  file_id_modifier_seed: string;
  effective_entry_date_offset_days: number;
  company_descriptive_date: string | null;
  effective_from: string;
  termination_date: string | null;
}

export async function getTenantAchOrigination(): Promise<TenantAchOrigination | null> {
  return apiGet<TenantAchOrigination | null>(
    `${NETWORK_BASE}/tenant-ach-origination`,
  );
}

export type UpsertTenantAchOriginationRequest = Omit<
  TenantAchOrigination, "id" | "tenant_id" | "termination_date"
>;

export async function upsertTenantAchOrigination(
  body: UpsertTenantAchOriginationRequest,
): Promise<TenantAchOrigination> {
  return apiPost<TenantAchOrigination>(
    `${NETWORK_BASE}/tenant-ach-origination`, body,
  );
}

// ─── Cycle schedules ─────────────────────────────────────────

export type Cadence = "daily" | "weekly" | "bi_weekly" | "semi_monthly" | "monthly";
export type ScheduleScope =
  | "tenant" | "client" | "program" | "pharmacy_npi" | "pharmacy_state";

export interface CycleSchedule {
  id: string;
  name: string;
  cycle_type: CycleType;
  cadence: Cadence;
  cadence_config: Record<string, unknown>;
  scope_type: ScheduleScope;
  scope_value: string | null;
  effective_from: string;
  termination_date: string | null;
  created_at: string;
}

export async function listCycleSchedules(): Promise<CycleSchedule[]> {
  return apiGet<CycleSchedule[]>(`${PAYSYNC_BASE}/cycle-schedules`);
}

export type CreateCycleScheduleRequest = Omit<
  CycleSchedule, "id" | "created_at" | "termination_date"
>;

export async function createCycleSchedule(
  body: CreateCycleScheduleRequest,
): Promise<CycleSchedule> {
  return apiPost<CycleSchedule>(`${PAYSYNC_BASE}/cycle-schedules`, body);
}

export async function updateCycleSchedule(
  id: string, body: Partial<CreateCycleScheduleRequest>,
): Promise<CycleSchedule> {
  return apiPatch<CycleSchedule>(`${PAYSYNC_BASE}/cycle-schedules/${id}`, body);
}

export async function deleteCycleSchedule(id: string): Promise<void> {
  return apiDelete<void>(`${PAYSYNC_BASE}/cycle-schedules/${id}`);
}

// ─── Bank settlements ────────────────────────────────────────

export interface BankSettlement {
  id: string;
  settlement_date: string;
  bank_reference: string;
  settled_amount: string;
  payment_batch_id: string | null;
  source: "manual" | "sftp_ingest";
  status: "pending" | "matched" | "discrepancy" | "ignored";
  bounce_count: number;
  carryover_count: number;
  ingested_at: string;
}

export interface BankSettlementListQuery extends PageQuery {
  source?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  payment_batch_id?: string;
}

export async function listBankSettlements(
  q: BankSettlementListQuery = {},
): Promise<Page<BankSettlement>> {
  return apiGet<Page<BankSettlement>>(
    buildUrl(`${PAYSYNC_BASE}/bank-settlements`, q),
  );
}

export async function getBankSettlement(id: string): Promise<BankSettlement> {
  return apiGet<BankSettlement>(`${PAYSYNC_BASE}/bank-settlements/${id}`);
}

export interface BankSettlementEntry {
  id: string;
  bank_settlement_id: string;
  trace_number: string;
  settled_amount: string;
  returned: boolean;
  return_reason_code: string | null;
  carryover_id: string | null;
  payment_batch_credit_id: string | null;
  matched: boolean;
}

export async function listSettlementEntries(
  settlementId: string,
): Promise<BankSettlementEntry[]> {
  return apiGet<BankSettlementEntry[]>(
    `${PAYSYNC_BASE}/bank-settlements/${settlementId}/entries`,
  );
}

export interface ManualSettlementRequest {
  settlement_date: string;
  bank_reference: string;
  payment_batch_id?: string;
  entries: Array<{
    trace_number: string;
    settled_amount: string;
    returned: boolean;
    return_reason_code?: string;
  }>;
}

export async function createManualSettlement(
  body: ManualSettlementRequest,
): Promise<BankSettlement> {
  return apiPost<BankSettlement>(
    `${PAYSYNC_BASE}/bank-settlements`, body,
  );
}

// ─── Export templates ────────────────────────────────────────

export type TemplateType =
  | "backup_excel" | "claims_export" | "pharmacy_statement"
  | "cycle_summary" | "saasant" | "custom";
export type TemplateFormat = "xlsx" | "csv" | "pipe_delimited";

export interface ExportTemplate {
  id: string;
  name: string;
  template_type: TemplateType;
  format: TemplateFormat;
  column_definitions: Array<Record<string, unknown>>;
  filter_definitions: Array<Record<string, unknown>>;
  sort_definitions: Array<Record<string, unknown>>;
  summary_definitions: Array<Record<string, unknown>>;
  serialize_phi: boolean;
  serialization_seed: string | null;
  applies_to_clients: string[];
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export async function listExportTemplates(
  q: { template_type?: TemplateType } = {},
): Promise<ExportTemplate[]> {
  return apiGet<ExportTemplate[]>(
    buildUrl(`${PAYSYNC_BASE}/export-templates`, q),
  );
}

export async function getExportTemplate(id: string): Promise<ExportTemplate> {
  return apiGet<ExportTemplate>(`${PAYSYNC_BASE}/export-templates/${id}`);
}

export type UpsertExportTemplateRequest = Omit<
  ExportTemplate, "id" | "created_at" | "updated_at"
>;

export async function createExportTemplate(
  body: UpsertExportTemplateRequest,
): Promise<ExportTemplate> {
  return apiPost<ExportTemplate>(`${PAYSYNC_BASE}/export-templates`, body);
}

export async function updateExportTemplate(
  id: string, body: Partial<UpsertExportTemplateRequest>,
): Promise<ExportTemplate> {
  return apiPatch<ExportTemplate>(
    `${PAYSYNC_BASE}/export-templates/${id}`, body,
  );
}

export async function cloneExportTemplate(
  id: string, name: string,
): Promise<ExportTemplate> {
  return apiPost<ExportTemplate>(
    `${PAYSYNC_BASE}/export-templates/${id}/clone`, { name },
  );
}

export async function deleteExportTemplate(id: string): Promise<void> {
  return apiDelete<void>(`${PAYSYNC_BASE}/export-templates/${id}`);
}

export interface RenderTestResponse {
  preview_rows: Array<Record<string, unknown>>;
  summary_rows: Array<Record<string, unknown>>;
  warnings: string[];
}

export async function renderTestExportTemplate(
  id: string, sample_size = 10,
): Promise<RenderTestResponse> {
  return apiPost<RenderTestResponse>(
    `${PAYSYNC_BASE}/export-templates/${id}/render-test`,
    { sample_size },
  );
}

// ─── Email templates + recipients ────────────────────────────

export interface EmailTemplate {
  id: string;
  applies_to_event: string;
  subject_template: string;
  body_text_template: string;
  body_html_template: string | null;
  is_default: boolean;
  created_at: string;
}

export async function listEmailTemplates(): Promise<EmailTemplate[]> {
  return apiGet<EmailTemplate[]>(`${PAYSYNC_BASE}/email-templates`);
}

export async function upsertEmailTemplate(
  body: Omit<EmailTemplate, "id" | "created_at">,
): Promise<EmailTemplate> {
  return apiPost<EmailTemplate>(`${PAYSYNC_BASE}/email-templates`, body);
}

export interface EmailRecipient {
  id: string;
  bill_to_scope_type: string;
  bill_to_id: string;
  email_address: string;
  recipient_name: string | null;
  is_primary: boolean;
  is_cc: boolean;
  effective_from: string;
  termination_date: string | null;
}

export async function listEmailRecipients(
  bill_to_id?: string,
): Promise<EmailRecipient[]> {
  return apiGet<EmailRecipient[]>(
    buildUrl(`${PAYSYNC_BASE}/email-recipients`, { bill_to_id }),
  );
}

export async function upsertEmailRecipient(
  body: Omit<EmailRecipient, "id" | "termination_date">,
): Promise<EmailRecipient> {
  return apiPost<EmailRecipient>(`${PAYSYNC_BASE}/email-recipients`, body);
}

// ─── GL mappings + invoice sequences ─────────────────────────

export interface GlAccountMapping {
  id: string;
  mapping_key: string;
  gl_account: string;
  account_name: string | null;
  effective_from: string;
  termination_date: string | null;
  is_active: boolean;
}

export async function listGlMappings(): Promise<GlAccountMapping[]> {
  return apiGet<GlAccountMapping[]>(`${PAYSYNC_BASE}/gl-account-mappings`);
}

export async function upsertGlMapping(
  body: Omit<GlAccountMapping, "id" | "termination_date" | "is_active">,
): Promise<GlAccountMapping> {
  return apiPost<GlAccountMapping>(
    `${PAYSYNC_BASE}/gl-account-mappings`, body,
  );
}

export interface InvoiceSequence {
  id: string;
  sequence_type: InvoiceSequenceType;
  scope_type: "tenant" | "program" | "client";
  scope_value: string | null;
  prefix: string;
  next_invoice_number: number;
  starting_value: number;
  created_at: string;
  updated_at: string;
}

export async function listInvoiceSequences(): Promise<InvoiceSequence[]> {
  return apiGet<InvoiceSequence[]>(`${PAYSYNC_BASE}/invoice-sequences`);
}

export async function setInvoiceSequenceNumber(
  id: string, next_invoice_number: number, reason: string, force_decrement = false,
): Promise<InvoiceSequence> {
  return apiPost<InvoiceSequence>(
    `${PAYSYNC_BASE}/invoice-sequences/${id}/set-next`,
    { next_invoice_number, reason, force_decrement },
  );
}

// ─── Dashboard ────────────────────────────────────────────────

export interface PaysyncDashboard {
  open_cycles_count: number;
  open_cycles_claim_count: number;
  pending_close_count: number;
  pending_reconciliation_count: number;
  open_carryovers_count: number;
  open_carryovers_we_owe: string;
  open_carryovers_pharmacy_owes: string;
  banking_discrepancies_pending: number;
  recent_activity: Array<{
    id: string;
    event_type: string;
    occurred_at: string;
    actor: string | null;
    description: string;
    related_entity_url: string | null;
  }>;
}

export async function getPaysyncDashboard(): Promise<PaysyncDashboard> {
  return apiGet<PaysyncDashboard>(`${PAYSYNC_BASE}/dashboard`);
}

// ─── Echo Spec 400 (Wave 41) ──────────────────────────────────

export type EchoRunStatus =
  | "pending_submission" | "submitted" | "status_received"
  | "reconciled" | "failed";

export interface EchoSpec400Run {
  id: string;
  run_date: string;
  file_path: string | null;
  file_sha256: string | null;
  record_count: number;
  total_amount: string;
  submitted_at: string | null;
  submitted_by: string | null;
  status_file_received_at: string | null;
  status_file_processed_at: string | null;
  manual_ap_record_ids: string[];
  status: EchoRunStatus;
  created_at: string;
}

export interface EchoSpec400ListQuery extends PageQuery {
  status?: EchoRunStatus;
  date_from?: string;
  date_to?: string;
}

export async function listEchoRuns(
  q: EchoSpec400ListQuery = {},
): Promise<Page<EchoSpec400Run>> {
  return apiGet<Page<EchoSpec400Run>>(
    buildUrl(`${PAYSYNC_BASE}/echo/spec-400-runs`, q),
  );
}

export async function getEchoRun(id: string): Promise<EchoSpec400Run> {
  return apiGet<EchoSpec400Run>(`${PAYSYNC_BASE}/echo/spec-400-runs/${id}`);
}

export interface EchoCandorRunResult {
  eligible_count: number;
  generation: { run_id: string; record_count: number; total_amount: string } | null;
  upload_remote_path: string | null;
  status_files_polled: number;
  status_files_ingested: number;
  skipped_reason: string | null;
}

export async function runEchoCandor(): Promise<EchoCandorRunResult> {
  return apiPost<EchoCandorRunResult>(
    `${PAYSYNC_BASE}/echo/candor/run`, {},
  );
}

export interface EchoStatusFileIngestion {
  id: string;
  remote_filename: string;
  local_path: string;
  file_sha256: string;
  downloaded_at: string;
  parsed_at: string | null;
  parse_error: string | null;
  record_count: number | null;
  records_matched: number | null;
  records_unmatched: number | null;
  archived_at: string | null;
  status: "downloaded" | "parsed" | "failed" | "archived";
}

export async function listEchoIngestions(): Promise<EchoStatusFileIngestion[]> {
  return apiGet<EchoStatusFileIngestion[]>(
    `${PAYSYNC_BASE}/echo/status-file-ingestions`,
  );
}

// ─── Search ───────────────────────────────────────────────────

export interface SearchResult {
  type: "cycle" | "batch" | "invoice" | "claim" | "pay_to_entity";
  id: string;
  label: string;
  sublabel: string | null;
  url: string;
}

export async function paysyncSearch(query: string): Promise<SearchResult[]> {
  return apiGet<SearchResult[]>(
    buildUrl(`${PAYSYNC_BASE}/search`, { q: query }),
  );
}
