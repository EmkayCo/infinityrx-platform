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
