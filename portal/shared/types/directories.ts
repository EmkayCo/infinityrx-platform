import type { Money, UUID, ISODateTimeString } from "./common";

// ── Pharmacy ──────────────────────────────────────────────────────────────────

export type NetworkStatus = "in_network" | "out_of_network" | "preferred" | "pending" | "terminated";
export type CredentialingStatus = "credentialed" | "pending" | "suspended" | "revoked" | "expired";
export type PharmacyType = "retail" | "mail_order" | "specialty" | "long_term_care" | "compound" | "hospital";

export type DispensingClass = "retail" | "mail" | "specialty" | "ltc" | "340b";

export interface PharmacyLicense {
  state: string;
  license_number: string;
  expiry: string;
  status: "active" | "expired" | "suspended";
}

export interface PharmacyAccreditation {
  body: string; // e.g. "URAC", "ACHC", "NABP"
  type: string;
  expiry: string;
}

export interface RiskScoreBreakdown {
  overall: number; // 0–100
  billing_anomaly: number;
  network_leakage: number;
  dispensing_pattern: number;
  geographic_outlier: number;
}

export interface Pharmacy {
  id: UUID;
  tenant_id: UUID;
  npi: string;
  name: string;
  address_line1: string;
  address_line2?: string;
  city: string;
  state: string;
  zip: string;
  phone?: string;
  fax?: string;
  email?: string;
  contact_person?: string;
  pharmacy_type: PharmacyType;
  network_status: NetworkStatus;
  credentialing_status: CredentialingStatus;
  ncpdp_id?: string;
  dea_number?: string;
  nabp?: string;
  store_number?: string;
  tax_id?: string;
  // Chain & Network fields
  chain_code?: string;
  pay_to_provider_name?: string;
  pay_to_provider_id?: string;
  reconciliation_vendor?: string;
  network_participation?: string[];
  contract_effective_date?: string;
  contract_term_date?: string;
  // Classification fields
  dispensing_class?: DispensingClass;
  billing_taxonomy?: string;
  is_340b?: boolean;
  specialty_designations?: string[];
  // Operational
  licenses?: PharmacyLicense[];
  accreditations?: PharmacyAccreditation[];
  hours?: string;
  // Risk
  risk_score?: RiskScoreBreakdown;
  // Legacy
  accepts_medicaid: boolean;
  accepts_medicare: boolean;
  latitude?: number;
  longitude?: number;
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

// ── Prescriber ────────────────────────────────────────────────────────────────

export type DEAStatus = "active" | "expired" | "revoked" | "none";
export type LicenseStatus = "active" | "expired" | "suspended" | "revoked";

export interface Prescriber {
  id: UUID;
  tenant_id: UUID;
  npi: string;
  first_name: string;
  last_name: string;
  full_name: string;
  specialty: string;
  subspecialty?: string;
  dea_number?: string;
  dea_status: DEAStatus;
  dea_expiry?: string;
  state_license_number?: string;
  state_license_status: LicenseStatus;
  state_license_expiry?: string;
  address_line1?: string;
  city?: string;
  state?: string;
  zip?: string;
  phone?: string;
  credential_alerts: string[];
  prescribing_summary?: {
    total_claims_90d: number;
    top_drugs: Array<{ ndc: string; drug_name: string; claim_count: number }>;
    avg_days_supply: number;
  };
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

// ── Drug ──────────────────────────────────────────────────────────────────────

export interface DrugPrice {
  awp: Money;
  wac: Money;
  nadac?: Money;
  mac?: Money;
  effective_date: string;
}

export interface DrugInteraction {
  interacting_ndc: string;
  interacting_drug_name: string;
  severity: "contraindicated" | "major" | "moderate" | "minor";
  description: string;
}

export interface TherapeuticEquivalent {
  ndc: string;
  drug_name: string;
  manufacturer: string;
  awp: Money;
}

export interface Drug {
  id: UUID;
  tenant_id: UUID;
  ndc: string;
  brand_name: string;
  generic_name: string;
  manufacturer: string;
  strength: string;
  dosage_form: string;
  route: string;
  gpi?: string; // Generic Product Identifier (14-digit)
  therapeutic_class: string;
  drug_category: string;
  brand_generic: "brand" | "generic"; // explicit classification badge
  is_generic: boolean;
  is_brand: boolean;
  is_controlled: boolean;
  is_specialty?: boolean;
  schedule?: string;
  rems_required: boolean;
  rems_program?: string;
  current_pricing: DrugPrice;
  pricing_history: Array<DrugPrice & { recorded_at: ISODateTimeString }>;
  interactions: DrugInteraction[];
  therapeutic_equivalents: TherapeuticEquivalent[];
  updated_at: ISODateTimeString;
}

// ── Member ────────────────────────────────────────────────────────────────────

export type CoverageStatus = "active" | "terminated" | "cobra" | "suspended" | "pending";
export type BenefitPhase = "deductible" | "initial_coverage" | "coverage_gap" | "catastrophic";
export type PHIAccessLevel = "full" | "partial" | "redacted";

export interface MemberAccumulator {
  benefit_year: number;
  deductible_applied: Money;
  deductible_limit: Money;
  oop_applied: Money;
  oop_limit: Money;
  benefit_phase: BenefitPhase;
  troop_applied?: Money;
  updated_at: ISODateTimeString;
}

export interface CopayEnrollment {
  program_id: string;
  program_name: string;
  card_status: "active" | "inactive" | "pending";
  enrolled_at: string;
  remaining_benefit: Money;
  benefit_limit: Money;
  bin: string;
  pcn: string;
  group_code: string;
}

export interface EligibilityHistoryEntry {
  event: string; // e.g. "Enrolled", "Terminated", "Plan Change", "COBRA Initiated"
  effective_date: string;
  plan_name?: string;
  group_id?: string;
  changed_by?: string;
  recorded_at: ISODateTimeString;
}

export interface Member {
  id: UUID;
  tenant_id: UUID;
  member_id: string;
  // PHI fields — masking applied per access level
  full_name: string | null;
  masked_name: string;
  date_of_birth: string | null;
  masked_dob: string;
  gender?: string;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  // Coverage
  coverage_status: CoverageStatus;
  eligibility_status?: "eligible" | "ineligible" | "pending_verification";
  coverage_effective_date?: string;
  coverage_term_date?: string;
  plan_id?: UUID;
  plan_name?: string;
  group_id?: string;
  coverage_type?: string; // e.g. "Employee", "Spouse", "Dependent"
  // Copay programs
  copay_enrollment?: CopayEnrollment[];
  eligibility_history?: EligibilityHistoryEntry[];
  // Accumulators
  accumulator?: MemberAccumulator;
  // Meta
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

export interface EligibilityResult {
  member_id: string;
  found: boolean;
  coverage_status?: CoverageStatus;
  coverage_effective_date?: string;
  coverage_term_date?: string;
  plan_name?: string;
  group_id?: string;
  checked_at: ISODateTimeString;
  error?: string;
}
