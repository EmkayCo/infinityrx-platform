// Billing domain TypeScript interfaces matching backend Pydantic schemas.
// Money amounts arrive from backend as strings (Decimal serialized) — never parseFloat.

export type CycleStatus =
  | "draft"
  | "validating"
  | "pending_approval"
  | "approved"
  | "generating"
  | "completed"
  | "voided";

export type ClaimStatus =
  | "pending"
  | "valid"
  | "warning"
  | "error"
  | "approved"
  | "rejected"
  | "flagged";

export type InvoiceStatus =
  | "generated"
  | "sent"
  | "paid"
  | "overdue"
  | "voided";

export interface BillingCycle {
  id: string;
  tenant_id: string;
  client_id: string;
  client_name: string;
  program_id: string;
  program_name: string;
  cycle_period: string; // "2026-04"
  status: CycleStatus;
  total_claims: number;
  total_ap_amount: string; // Decimal string
  total_ar_amount: string;
  total_fee_amount: string;
  created_at: string; // ISO datetime
  updated_at: string;
  approved_at: string | null;
  approved_by: string | null;
  generated_at: string | null;
  artifacts: CycleArtifact[];
  comparison?: CycleComparison;
  anomaly_flags?: AnomalyFlag[];
}

export interface CycleArtifact {
  id: string;
  type: "saasant_excel" | "835" | "nacha" | "report";
  filename: string;
  download_url: string;
  generated_at: string;
  transmitted_at: string | null;
  ack_status: "pending" | "acknowledged" | "rejected" | null;
}

export interface CycleComparison {
  prev_cycle_period: string;
  prev_total_claims: number;
  prev_total_ap_amount: string;
  claims_delta: number;
  claims_delta_pct: string;
  ap_amount_delta: string;
  ap_amount_delta_pct: string;
}

export interface AnomalyFlag {
  severity: "info" | "warning" | "critical";
  message: string; // AI narrative from backend
}

export interface Claim {
  id: string;
  tenant_id: string;
  cycle_id: string | null;
  client_id: string;
  client_name: string;
  program_id: string;
  program_name: string;
  pharmacy_npi: string;
  pharmacy_name: string;
  member_id: string;
  drug_ndc: string;
  drug_name: string;
  fill_date: string;
  quantity: string;
  days_supply: number;
  ingredient_cost: string;
  dispensing_fee: string;
  copay: string;
  plan_paid: string;
  status: ClaimStatus;
  rejection_reason: string | null;
  created_at: string;
}

export interface ValidationResult {
  upload_id: string;
  total_rows: number;
  valid_count: number;
  warning_count: number;
  error_count: number;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

export interface ValidationError {
  row: number;
  field: string;
  error_message: string;
  original_value: string;
}

export interface ValidationWarning {
  row: number;
  field: string;
  warning_message: string;
  original_value: string;
}

export interface FieldMapping {
  source_column: string;
  target_field: string;
  confidence: number; // 0-1, from fuzzy match
}

export interface MappingTemplate {
  id: string;
  name: string;
  client_id: string;
  mappings: FieldMapping[];
  created_at: string;
}

export interface Invoice {
  id: string;
  tenant_id: string;
  client_id: string;
  client_name: string;
  cycle_id: string | null;
  invoice_number: string;
  status: InvoiceStatus;
  total_amount: string;
  due_date: string;
  issued_at: string | null;
  paid_at: string | null;
  pdf_url: string | null;
  line_items: InvoiceLineItem[];
  timeline: InvoiceTimelineEntry[];
}

export interface InvoiceLineItem {
  id: string;
  description: string;
  quantity: number;
  unit_price: string;
  total: string;
}

export interface InvoiceTimelineEntry {
  action: string;
  actor: string;
  timestamp: string;
  notes: string | null;
}

export interface FinancialPreview {
  ap_total: string;
  ar_total: string;
  fee_total: string;
  net_settlement: string;
  journal_entries: JournalEntryPreview[];
}

export interface JournalEntryPreview {
  account: string;
  debit: string;
  credit: string;
  description: string;
}

export interface CycleDraft {
  step: number;
  upload_id?: string;
  upload_filename?: string;
  mapping_template_id?: string;
  field_mappings?: FieldMapping[];
  validation_result?: ValidationResult;
  cycle_id?: string;
}
