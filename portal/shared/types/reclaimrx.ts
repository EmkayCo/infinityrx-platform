import type { Money, UUID, ISODateTimeString } from "./common";

export type InvestigationStatus =
  | "new"
  | "assigned"
  | "evidence"
  | "demand"
  | "resolved";

export type FlagSeverity = "critical" | "high" | "medium" | "low";

export type FlagType =
  | "billing_anomaly"
  | "prescribing_pattern"
  | "network_leakage"
  | "duplicate_claim"
  | "identity_theft"
  | "dme_fraud"
  | "kickback"
  | "other";

// GTN / Leakage category types
export type LeakageCategory =
  | "pharmacy_misuse"
  | "accumulator"
  | "maximizer"
  | "three_forty_b_overlap"
  | "alternative_funding"
  | "prescriber_anomaly"
  | "patient_anomaly";

export type RecoveryMethod = "offset" | "demand_letter" | "legal" | "write_off";
export type RecoveryStatus = "pending" | "in_progress" | "recovered" | "written_off";

export interface FWAFlag {
  id: UUID;
  tenant_id: UUID;
  flag_type: FlagType;
  severity: FlagSeverity;
  entity_type: "pharmacy" | "prescriber" | "member";
  entity_id: UUID;
  entity_name: string;
  estimated_recovery: Money;
  anomaly_narrative: string;
  detected_at: ISODateTimeString;
  claim_count: number;
  investigation_id?: UUID;
}

export interface EvidenceItem {
  id: UUID;
  label: string;
  description?: string;
  required: boolean;
  completed: boolean;
  completed_at?: ISODateTimeString;
  completed_by?: string;
  file_url?: string;
}

export interface InvestigationAction {
  id: UUID;
  investigation_id: UUID;
  action: string;
  performed_by: string;
  performed_at: ISODateTimeString;
  notes?: string;
}

export interface Investigation {
  id: UUID;
  tenant_id: UUID;
  flag_id: UUID;
  flag: FWAFlag;
  status: InvestigationStatus;
  assigned_to?: UUID;
  assigned_to_name?: string;
  days_open: number;
  estimated_recovery: Money;
  demanded_amount?: Money;
  collected_amount?: Money;
  demand_letter?: string;
  corrective_action_plan?: string;
  evidence_items: EvidenceItem[];
  actions: InvestigationAction[];
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

export interface RecoveryRecord {
  id: UUID;
  investigation_id: UUID;
  entity_name: string;
  flag_type: FlagType;
  estimated: Money;
  demanded: Money;
  collected: Money;
  delta: Money;
  status: InvestigationStatus;
  updated_at: ISODateTimeString;
}

export interface FWADashboardStats {
  new_flags_today: number;
  new_flags_this_week: number;
  severity_breakdown: Record<FlagSeverity, number>;
  top_flagged_entities: Array<{
    entity_id: UUID;
    entity_name: string;
    entity_type: string;
    flag_count: number;
    estimated_recovery: Money;
  }>;
  trend_90d: Array<{ date: string; count: number }>;
}

// ─── GTN Summary ─────────────────────────────────────────────────────────────

export interface GTNSummary {
  total_copay_spend: Money;
  identified_leakage: Money;
  gtn_ratio: string; // e.g. "0.8234"
  gtn_ratio_prev: string;
  active_investigations: number;
  recovered: Money;
  recovery_rate: string; // e.g. "0.4512"
  leakage_by_category: Array<{ category: LeakageCategory; amount: Money; count: number }>;
  leakage_by_program: Array<{ program_name: string; amount: Money }>;
  top_flagged_pharmacies: Array<{
    npi: string;
    pharmacy_name: string;
    risk_score: number;
    total_leakage: Money;
    active_investigations: number;
  }>;
}

export interface GTNTrendPoint {
  month: string; // "2026-01"
  gtn_ratio: string;
  leakage_amount: Money;
}

// ─── Leakage Flag ────────────────────────────────────────────────────────────

export interface LeakageFlag {
  id: UUID;
  tenant_id: UUID;
  category: LeakageCategory;
  entity_type: "pharmacy" | "prescriber" | "patient";
  entity_name: string;
  entity_id: UUID;
  estimated_leakage: Money;
  status: "new" | "under_investigation" | "confirmed" | "dismissed";
  date_flagged: ISODateTimeString;
  investigation_id?: UUID;
  program_name?: string;
}

// ─── Pharmacy Risk Score ─────────────────────────────────────────────────────

export interface PharmacyRiskFactor {
  factor: string;
  score: number; // 0-100
  description: string;
}

export interface PharmacyRiskScore {
  npi: string;
  pharmacy_name: string;
  ncpdp: string;
  chain_code: string;
  state: string;
  risk_score: number; // 0-100
  risk_tier: "low" | "medium" | "high" | "critical";
  factors: PharmacyRiskFactor[];
  total_claims: number;
  total_copay_paid: Money;
  reversal_rate: string; // e.g. "0.12"
  active_investigations: number;
  last_updated: ISODateTimeString;
}
