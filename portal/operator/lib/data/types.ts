/**
 * Types for the InfinityRx claims data layer.
 * Money values are kept as strings throughout to preserve Decimal-safe precision.
 */

export interface ParsedClaim {
  claim_id: string;
  status: "P" | "R";
  bin: string;
  pcn: string;
  date_of_service: string; // YYYY-MM-DD
  date_written: string; // YYYY-MM-DD
  group_number: string;
  client_name: string; // resolved via group→client map
  cardholder_id: string;
  last_name: string;
  first_name: string;
  service_provider_id: string; // pharmacy NPI/NCPDP
  ndc: string;
  rx_number: string;
  quantity: number;
  days_supply: number;
  compound_code: string;
  daw: string;
  // money — string for Decimal-safe display, raw for aggregation done server-side
  submitted_ingredient_cost: string;
  submitted_dispensing_fee: string;
  submitted_gross_amount_due: string;
  copay: string;
  patient_pay_amount: string;
  pharmacy_total_paid: string;
  pharmacy_ingredient_cost_paid: string;
  pharmacy_dispensing_fee_paid: string;
  sell_ingredient_cost: string;
  sell_dispensing_fee: string;
  total_client_billed: string;
  process_date_time: string; // ISO 8601
  prescriber_npi: string;
  drug_tier: string;
  brand_generic: string;
  is_preferred: string;
  network_reimbursement_id: string; // NRID
  claim_processing_fee: string;
  transaction_fees: string;
  primary_chain_code: string;
  // source cycle
  cycle_id: string;
}

// ── Aggregation shapes ────────────────────────────────────────────────────────

export interface OverviewAgg {
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
  total_processing_fees: string;
  total_transaction_fees: string;
  reversal_rate: string; // "0.0234" = 2.34%
}

export interface CycleAgg {
  cycle_id: string;
  file_name: string;
  status: "completed" | "in_progress";
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
  reversal_rate: string;
  dos_min: string;
  dos_max: string;
}

export interface ClientAgg {
  group_number: string;
  client_name: string;
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
  reversal_rate: string;
}

export interface NridAgg {
  nrid: string;
  vendor_name: string;
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
}

export interface ChainAgg {
  primary_chain_code: string;
  total_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
}

export interface PharmacyAgg {
  service_provider_id: string;
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
  avg_claim_billed: string;
  reversal_rate: string;
  primary_chain_code: string;
}

export interface NdcAgg {
  ndc: string;
  drug_tier: string;
  brand_generic: string;
  total_claims: number;
  total_client_billed: string;
  total_pharmacy_paid: string;
  avg_claim_billed: string;
}

export interface PrescriberAgg {
  prescriber_npi: string;
  total_claims: number;
  total_client_billed: string;
  unique_patients: number;
  unique_ndcs: number;
}

export interface MemberAgg {
  cardholder_id: string;
  client_name: string;
  total_claims: number;
  total_client_billed: string;
  unique_ndcs: number;
}

export interface DailyVolumeAgg {
  date: string; // YYYY-MM-DD
  total_claims: number;
  paid_claims: number;
  reversal_claims: number;
  total_client_billed: string;
}

export interface NridDistributionAgg {
  nrid: string;
  vendor_name: string;
  claim_count: number;
  pct_of_total: string;
}

export interface ReversalRateAgg {
  overall_rate: string;
  by_client: Array<{
    client_name: string;
    group_number: string;
    total_claims: number;
    reversal_count: number;
    reversal_rate: string;
  }>;
}

export interface ActivityEvent {
  id: string;
  timestamp: string;
  type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical" | "success";
  amount?: string;
  client_name?: string;
}

export interface InvestigationCard {
  id: string;
  status: "new" | "assigned" | "evidence" | "demand" | "resolved";
  flag: {
    severity: "critical" | "high" | "medium" | "low";
    flag_type: string;
    entity_name: string;
    entity_id: string;
  };
  client_name: string;
  days_open: number;
  estimated_recovery: string;
  assigned_to_name?: string;
  notes: string;
}

export interface ManifestFile {
  name: string;
  rows: number;
  total_billed: string;
  total_paid: string;
  paid_count: number;
  reversal_count: number;
}

export interface Manifest {
  generated_at: string;
  files: ManifestFile[];
  totals: OverviewAgg;
}

export interface Aggregations {
  overview: OverviewAgg;
  cycles: CycleAgg[];
  by_client: ClientAgg[];
  by_nrid: NridAgg[];
  by_chain: ChainAgg[];
  by_pharmacy: PharmacyAgg[];
  by_ndc: NdcAgg[];
  by_prescriber: PrescriberAgg[];
  by_member: MemberAgg[];
  top_pharmacies: PharmacyAgg[];
  top_ndcs: NdcAgg[];
  top_clients: ClientAgg[];
  daily_volume: DailyVolumeAgg[];
  nrid_distribution: NridDistributionAgg[];
  reversal_rate: ReversalRateAgg;
  activity_feed: ActivityEvent[];
  investigations: InvestigationCard[];
  manifest: Manifest;
}
