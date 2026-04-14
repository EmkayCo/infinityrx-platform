// Payment-processing domain TypeScript interfaces matching backend Pydantic schemas.
// Money amounts arrive from backend as strings (Decimal serialized) — never parseFloat.

export type BatchStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "generating"
  | "generated"
  | "transmitting"
  | "transmitted"
  | "acknowledged"
  | "settled"
  | "failed"
  | "voided";

export type VendorType = "nacha" | "echo" | "check_issuing" | "wire";

export type AckStatus = "pending" | "acknowledged" | "rejected" | "failed";

export interface PaymentBatch {
  id: string;
  tenant_id: string;
  status: BatchStatus;
  vendor: VendorType;
  vendor_name: string;
  payment_count: number;
  total_amount: string; // Decimal string
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
  transmitted_at: string | null;
  ack_status: AckStatus | null;
  ack_received_at: string | null;
  nacha_file_id: string | null;
  routing: BatchRouting[];
}

export interface BatchRouting {
  vendor: VendorType;
  vendor_name: string;
  client_id: string;
  client_name: string;
  payment_count: number;
  total_amount: string;
}

export interface NachaFile {
  id: string;
  tenant_id: string;
  batch_id: string;
  filename: string;
  entry_count: number;
  total_debit: string;
  total_credit: string;
  effective_date: string;
  created_at: string;
  transmitted_at: string | null;
  ack_status: AckStatus | null;
  humanized_preview: NachaPreviewEntry[];
  download_url: string;
}

export interface NachaPreviewEntry {
  line_type: "file_header" | "batch_header" | "entry" | "batch_control" | "file_control";
  description: string; // humanized text, NOT raw X9.35
  amount: string | null;
  routing_number: string | null;
  account_number: string | null;
  individual_name: string | null;
  trace_number: string | null;
}

export interface Vendor {
  id: string;
  name: string;
  type: VendorType;
  status: "active" | "inactive" | "error";
  last_health_check: string | null;
  health_status: "healthy" | "degraded" | "down" | null;
}

export interface Submission {
  id: string;
  batch_id: string;
  vendor_id: string;
  vendor_name: string;
  status: "submitted" | "settled" | "returned" | "failed";
  submitted_at: string;
  settled_at: string | null;
  returned_at: string | null;
  total_amount: string;
}

export interface AchReturn {
  id: string;
  submission_id: string;
  return_code: string;
  return_reason: string;
  original_amount: string;
  returned_at: string;
  resolved: boolean;
}

export interface BatchDraft {
  step: number;
  selected_claim_ids?: string[];
  selected_total?: string;
  routing_summary?: BatchRouting[];
  batch_id?: string;
}
