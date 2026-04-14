// Billing cycle wizard local types.
import type { FieldMapping, ValidationResult, FinancialPreview } from "@shared/types/billing";

export interface BillingCycleWizardData {
  // Step 1 — Upload
  upload_id: string | null;
  upload_filename: string | null;
  upload_size_bytes: number | null;
  upload_estimated_rows: number | null;
  detected_columns: string[];
  is_duplicate: boolean;

  // Step 2 — Map Fields
  mapping_template_id: string | null;
  field_mappings: FieldMapping[];

  // Step 3 — Validate
  validation_result: ValidationResult | null;
  proceed_with_valid_only: boolean;

  // Step 4 — Preview
  cycle_id_preview: string | null; // server-generated preview ID
  total_claims: number | null;
  total_ap_amount: string | null;
  total_ar_amount: string | null;
  total_fee_amount: string | null;
  financial_preview: FinancialPreview | null;

  // Step 5 — Approve
  approver_id: string | null;
  approval_notes: string;

  // Step 6 — Generate (output)
  generated_cycle_id: string | null;
}

export const INITIAL_WIZARD_DATA: BillingCycleWizardData = {
  upload_id: null,
  upload_filename: null,
  upload_size_bytes: null,
  upload_estimated_rows: null,
  detected_columns: [],
  is_duplicate: false,
  mapping_template_id: null,
  field_mappings: [],
  validation_result: null,
  proceed_with_valid_only: false,
  cycle_id_preview: null,
  total_claims: null,
  total_ap_amount: null,
  total_ar_amount: null,
  total_fee_amount: null,
  financial_preview: null,
  approver_id: null,
  approval_notes: "",
  generated_cycle_id: null,
};
