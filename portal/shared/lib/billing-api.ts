// T2: Billing module API client — wraps all /billing/v1/ endpoints.
// Money amounts are strings (Decimal serialized). Never parseFloat.
import { apiGet, apiPost, apiPut, buildUrl } from "./api-client";
import { API_URLS } from "./constants";
import type {
  BillingCycle,
  Claim,
  Invoice,
  ValidationResult,
  MappingTemplate,
  FinancialPreview,
} from "@shared/types/billing";
import type { PaginatedResponse } from "@shared/types/api";

const BASE = `${API_URLS.billing}/billing/v1`;

// ── Cycles ─────────────────────────────────────────────────────────────────

export interface CycleListParams {
  client_id?: string;
  status?: string;
  page?: number;
  page_size?: number;
}

export async function listCycles(params?: CycleListParams): Promise<PaginatedResponse<BillingCycle>> {
  return apiGet<PaginatedResponse<BillingCycle>>(buildUrl(`${BASE}/cycles`, params));
}

export async function getCycle(id: string): Promise<BillingCycle> {
  return apiGet<BillingCycle>(`${BASE}/cycles/${id}`);
}

// ── Upload ──────────────────────────────────────────────────────────────────

export interface UploadResponse {
  upload_id: string;
  filename: string;
  size_bytes: number;
  estimated_row_count: number;
  detected_columns: string[];
  is_duplicate: boolean;
}

export async function uploadClaimsFile(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadResponse> {
  return new Promise<UploadResponse>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${BASE}/uploads`);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as UploadResponse);
        } catch {
          reject(new Error("Invalid JSON response from upload endpoint"));
        }
      } else {
        reject(new Error(`Upload failed: HTTP ${xhr.status}`));
      }
    };

    xhr.onerror = () => reject(new Error("Network error during upload"));

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

// ── Field mappings ──────────────────────────────────────────────────────────

export interface SaveMappingTemplateRequest {
  name: string;
  client_id: string;
  upload_id: string;
  mappings: Array<{ source_column: string; target_field: string }>;
}

export async function getMappingTemplates(client_id?: string): Promise<MappingTemplate[]> {
  return apiGet<MappingTemplate[]>(
    buildUrl(`${BASE}/mapping-templates`, client_id ? { client_id } : undefined)
  );
}

export async function saveMappingTemplate(req: SaveMappingTemplateRequest): Promise<MappingTemplate> {
  return apiPost<MappingTemplate>(`${BASE}/mapping-templates`, req);
}

// ── Validation ──────────────────────────────────────────────────────────────

export async function validateUpload(
  upload_id: string,
  mappings: Array<{ source_column: string; target_field: string }>
): Promise<ValidationResult> {
  return apiPost<ValidationResult>(`${BASE}/uploads/${upload_id}/validate`, { mappings });
}

export async function downloadErrorCsv(upload_id: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/uploads/${upload_id}/errors.csv`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.blob();
}

// ── Preview & Financial ─────────────────────────────────────────────────────

export async function getFinancialPreview(upload_id: string): Promise<FinancialPreview> {
  return apiGet<FinancialPreview>(`${BASE}/uploads/${upload_id}/financial-preview`);
}

// ── Cycle approval ──────────────────────────────────────────────────────────

export interface ApproveCycleRequest {
  upload_id: string;
  mapping_template_id?: string;
  mappings: Array<{ source_column: string; target_field: string }>;
  approver_id?: string;
  notes?: string;
}

export async function approveCycle(req: ApproveCycleRequest): Promise<BillingCycle> {
  return apiPost<BillingCycle>(`${BASE}/cycles`, req);
}

export interface TransmitNachaRequest {
  cycle_id: string;
  artifact_id: string;
}

export async function transmitNacha(req: TransmitNachaRequest): Promise<{ status: string }> {
  return apiPost<{ status: string }>(`${BASE}/cycles/${req.cycle_id}/transmit`, {
    artifact_id: req.artifact_id,
  });
}

// ── Claims ──────────────────────────────────────────────────────────────────

export interface ClaimsListParams {
  cycle_id?: string;
  client_id?: string;
  program_id?: string;
  pharmacy_npi?: string;
  drug_ndc?: string;
  status?: string;
  fill_date_from?: string;
  fill_date_to?: string;
  amount_min?: string;
  amount_max?: string;
  page?: number;
  page_size?: number;
}

export async function listClaims(params?: ClaimsListParams): Promise<PaginatedResponse<Claim>> {
  return apiGet<PaginatedResponse<Claim>>(buildUrl(`${BASE}/claims`, params));
}

export async function getClaim(id: string): Promise<Claim> {
  return apiGet<Claim>(`${BASE}/claims/${id}`);
}

export async function bulkUpdateClaimStatus(
  ids: string[],
  action: "approve" | "reject" | "flag",
  reason?: string
): Promise<{ success_count: number; failures: Array<{ id: string; reason: string }> }> {
  return apiPost(`${BASE}/claims/bulk-action`, { ids, action, reason });
}

// ── Invoices ────────────────────────────────────────────────────────────────

export interface InvoicesListParams {
  status?: string;
  client_id?: string;
  page?: number;
  page_size?: number;
}

export async function listInvoices(params?: InvoicesListParams): Promise<PaginatedResponse<Invoice>> {
  return apiGet<PaginatedResponse<Invoice>>(buildUrl(`${BASE}/invoices`, params));
}

export async function getInvoice(id: string): Promise<Invoice> {
  return apiGet<Invoice>(`${BASE}/invoices/${id}`);
}

export async function approveInvoice(id: string): Promise<Invoice> {
  return apiPost<Invoice>(`${BASE}/invoices/${id}/approve`, {});
}

export async function sendInvoice(id: string): Promise<Invoice> {
  return apiPost<Invoice>(`${BASE}/invoices/${id}/send`, {});
}

export async function voidInvoice(id: string, reason: string): Promise<Invoice> {
  return apiPost<Invoice>(`${BASE}/invoices/${id}/void`, { reason });
}

export async function getInvoicePdf(id: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/invoices/${id}/pdf`);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.blob();
}

// ── AP/AR Summary ───────────────────────────────────────────────────────────

export interface APSummary {
  total_ap: string;
  total_ar: string;
  net_outstanding: string;
  this_cycle: string;
  this_month: string;
  last_updated: string;
}

export async function getAPARSummary(): Promise<APSummary> {
  return apiGet<APSummary>(`${BASE}/ap-records/summary`);
}
