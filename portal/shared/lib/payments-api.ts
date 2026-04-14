// T2: Payment-processing module API client — wraps all payment-processing endpoints.
// Money amounts are strings (Decimal serialized). Never parseFloat.
import { apiGet, apiPost, buildUrl } from "./api-client";
import { API_URLS } from "./constants";
import type {
  PaymentBatch,
  NachaFile,
  Vendor,
  Submission,
  AchReturn,
  BatchRouting,
} from "@shared/types/payments";
import type { PaginatedResponse } from "@shared/types/api";
import type { Claim } from "@shared/types/billing";

const BASE = API_URLS.payments;

// ── Vendors ─────────────────────────────────────────────────────────────────

export async function listVendors(): Promise<Vendor[]> {
  return apiGet<Vendor[]>(`${BASE}/vendors`);
}

export async function getVendorHealth(id: string): Promise<Vendor> {
  return apiGet<Vendor>(`${BASE}/vendors/${id}/health`);
}

// ── Payment Batches ──────────────────────────────────────────────────────────

export interface BatchListParams {
  status?: string;
  vendor?: string;
  page?: number;
  page_size?: number;
}

export async function listBatches(params?: BatchListParams): Promise<PaginatedResponse<PaymentBatch>> {
  return apiGet<PaginatedResponse<PaymentBatch>>(buildUrl(`${BASE}/batches`, params));
}

export async function getBatch(id: string): Promise<PaymentBatch> {
  return apiGet<PaymentBatch>(`${BASE}/batches/${id}`);
}

export interface CreateBatchRequest {
  claim_ids: string[];
  notes?: string;
}

export async function createBatch(req: CreateBatchRequest): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(`${BASE}/batches`, req);
}

export async function approveBatch(
  id: string,
  approver_id?: string,
  notes?: string
): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(`${BASE}/batches/${id}/approve`, { approver_id, notes });
}

export async function submitBatch(id: string): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(`${BASE}/batches/${id}/submit`, {});
}

export async function voidBatch(id: string, reason: string): Promise<PaymentBatch> {
  return apiPost<PaymentBatch>(`${BASE}/batches/${id}/void`, { reason });
}

// ── Routing preview ──────────────────────────────────────────────────────────

export async function previewRouting(claim_ids: string[]): Promise<BatchRouting[]> {
  return apiPost<BatchRouting[]>(`${BASE}/batches/routing-preview`, { claim_ids });
}

// ── NACHA Files ──────────────────────────────────────────────────────────────

export interface NachaListParams {
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listNachaFiles(params?: NachaListParams): Promise<PaginatedResponse<NachaFile>> {
  return apiGet<PaginatedResponse<NachaFile>>(buildUrl(`${BASE}/nacha`, params));
}

export async function getNachaFile(id: string): Promise<NachaFile> {
  return apiGet<NachaFile>(`${BASE}/nacha/${id}`);
}

export async function transmitNachaFile(id: string): Promise<NachaFile> {
  return apiPost<NachaFile>(`${BASE}/nacha/${id}/transmit`, {});
}

export async function downloadNacha(id: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/nacha/${id}/download`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.blob();
}

// ── Eligible claims for batch ────────────────────────────────────────────────

export interface EligibleClaimsParams {
  client_id?: string;
  fill_date_from?: string;
  fill_date_to?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listEligibleClaims(params?: EligibleClaimsParams): Promise<PaginatedResponse<Claim>> {
  return apiGet<PaginatedResponse<Claim>>(buildUrl(`${BASE}/eligible-claims`, params));
}

// ── Submissions ──────────────────────────────────────────────────────────────

export async function listSubmissions(batch_id?: string): Promise<Submission[]> {
  return apiGet<Submission[]>(buildUrl(`${BASE}/submissions`, batch_id ? { batch_id } : undefined));
}

export async function retrySubmission(id: string): Promise<Submission> {
  return apiPost<Submission>(`${BASE}/submissions/${id}/retry`, {});
}

// ── Returns ──────────────────────────────────────────────────────────────────

export async function listReturns(): Promise<AchReturn[]> {
  return apiGet<AchReturn[]>(`${BASE}/returns`);
}

// ── Dashboard ────────────────────────────────────────────────────────────────

export interface PaymentsDashboard {
  pending_batches: number;
  total_pending_amount: string;
  settled_today: string;
  returned_today: number;
  vendor_health: Vendor[];
}

export async function getPaymentsDashboard(): Promise<PaymentsDashboard> {
  return apiGet<PaymentsDashboard>(`${BASE}/dashboard`);
}
