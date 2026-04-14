import type { Money, UUID, ISODateTimeString } from "./common";

export type MedicalClaimStatus =
  | "pending"
  | "approved"
  | "denied"
  | "adjusted"
  | "void";

export type SiteOfCare =
  | "11"  // Office
  | "12"  // Home
  | "21"  // Inpatient Hospital
  | "22"  // Outpatient Hospital
  | "23"  // Emergency Room
  | "24"  // Ambulatory Surgical Center
  | "31"  // Skilled Nursing Facility
  | "61"  // Comprehensive Inpatient Rehab
  | string;

export interface HCPCSNDCMapping {
  hcpcs: string;
  ndc: string;
  drug_name: string;
  strength: string;
  units_per_claim: number;
  confidence_score: number;
  mapping_source: "cms" | "manual" | "ml";
  effective_date?: string;
}

export interface MedicalClaim {
  id: UUID;
  tenant_id: UUID;
  claim_number: string;
  hcpcs_code: string;
  hcpcs_description?: string;
  ndc?: string;
  drug_name?: string;
  provider_npi: string;
  provider_name: string;
  member_id: UUID;
  masked_member_name: string;
  date_of_service: string;
  place_of_service: SiteOfCare;
  billed_amount: Money;
  allowed_amount?: Money;
  paid_amount?: Money;
  patient_responsibility?: Money;
  status: MedicalClaimStatus;
  is_340b: boolean;
  units_billed: number;
  units_administered?: number;
  waste_units?: number;
  waste_amount?: Money;
  asp_unit_price?: Money;
  asp_total?: Money;
  hcpcs_ndc_mapping?: HCPCSNDCMapping;
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

export interface UnifiedDrugSpend {
  member_id: UUID;
  drug_name: string;
  ndc: string;
  period_months: Array<{
    month: string;
    pharmacy_spend: Money;
    medical_spend: Money;
    total_spend: Money;
  }>;
  total_pharmacy: Money;
  total_medical: Money;
  total_combined: Money;
}

export interface ThreeFourtyBSummary {
  flagged_count: number;
  entity_match_count: number;
  total_program_amount: Money;
  potential_savings: Money;
  recent_claims: MedicalClaim[];
}

export interface SiteOfCareAnalysis {
  place_of_service: SiteOfCare;
  pos_description: string;
  claim_count: number;
  total_billed: Money;
  total_paid: Money;
  avg_paid: Money;
}
