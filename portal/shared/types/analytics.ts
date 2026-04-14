import type { Money, UUID, ISODateTimeString } from "./common";

export interface LiveMetrics {
  claims_per_hour: number;
  dollars_flowing: Money;
  flags_per_day: number;
  claims_per_hour_delta: number;
  as_of: ISODateTimeString;
}

export interface DrugTrendPoint {
  date: string;
  spend: Money;
  claim_count: number;
  brand_spend?: Money;
  generic_spend?: Money;
}

export interface GenericBrandBreakdown {
  brand_spend: Money;
  generic_spend: Money;
  brand_pct: number;
  generic_pct: number;
  glp1_spend: Money;
  biosimilar_spend: Money;
}

export interface PharmacyScorecard {
  pharmacy_id: UUID;
  pharmacy_name: string;
  npi: string;
  claim_volume: number;
  avg_cost_per_claim: Money;
  reject_rate: number;
  mac_ratio: number;
  generic_dispense_rate: number;
  network_tier: string;
}

export interface NetworkAdequacySummary {
  total_members: number;
  members_within_5mi: number;
  members_within_10mi: number;
  coverage_pct_5mi: number;
  coverage_pct_10mi: number;
  gap_counties: string[];
}

export interface MemberAdherence {
  drug_class: string;
  pdc_score: number;
  cms_threshold: number;
  member_count: number;
  adherent_count: number;
  star_rating_impact: "positive" | "neutral" | "negative";
}

export interface HighCostMember {
  member_id: UUID;
  masked_name: string;
  ytd_spend: Money;
  primary_condition?: string;
  specialty_drug_count: number;
}

export interface FinancialMetrics {
  pmpm: Money;
  pmpm_prior_year: Money;
  pmpm_change_pct: number;
  cost_driver_breakdown: Array<{
    category: string;
    amount: Money;
    pct_of_total: number;
  }>;
  pmpm_trend: Array<{ month: string; pmpm: Money; prior_year_pmpm: Money }>;
  spread_analysis: {
    total_billed: Money;
    total_paid: Money;
    spread: Money;
    spread_pct: number;
  };
}

export interface DataQualityScore {
  overall_score: number;
  accuracy_score: number;
  completeness_score: number;
  timeliness_score: number;
  consistency_score: number;
  trend_90d: Array<{ date: string; score: number }>;
  component_issues: Array<{
    component: string;
    issue: string;
    severity: "high" | "medium" | "low";
    record_count: number;
  }>;
}
