// portal/shared/types/reclaimrx-v2.ts
// New types for ReclaimRx v2 anomaly API. World-B types (LeakageFlag, LeakageCategory,
// Investigation) in reclaimrx.ts are NOT mutated. This file is append-only.

import type { UUID, ISODateTimeString } from "./common";
import type { LeakageCategory, LeakageFlag } from "./reclaimrx";

/** AnomalyRead — matches GET /api/v1/reclaimrx/anomalies item shape. */
export interface AnomalyRead {
  id: UUID;
  tenant_id?: UUID;
  finding_code: string;
  finding_summary: string;
  severity: "critical" | "high" | "medium" | "low" | "informational";
  confidence: string;
  status: "open" | "under_review" | "confirmed" | "dismissed" | "in_recoup" | "in_audit" | "resolved" | "written_off";
  entity_type: "pharmacy" | "prescriber" | "unknown";
  pharmacy_npi: string | null;
  pharmacy_name: string | null;
  prescriber_npi: string | null;
  prescriber_name: string | null;
  ndc: string | null;
  amount_paid: string | null;
  amount_billed: string | null;
  recovery_amount: string | null;
  date_of_service: string | null;
  data_source_run_id: UUID | null;
  created_at: ISODateTimeString;
}

export interface AnomalyListResponse {
  items: AnomalyRead[];
  total: number;
  limit: number;
  offset: number;
}

export interface DetectionRunRead {
  id: UUID;
  run_label: string | null;
  status: "in_progress" | "completed" | "failed" | "cancelled";
  data_source: string | null;
  source_filename: string | null;
  record_count: number;
  anomaly_count: number;
  period_start: string | null;
  period_end: string | null;
  started_at: ISODateTimeString;
  completed_at: ISODateTimeString | null;
  failure_reason: string | null;
  data_quality: Record<string, unknown> | null;
}

export interface DetectionRunDetail extends DetectionRunRead {
  per_rule_breakdown: Array<{ finding_code: string; severity: string; count: number }>;
}

/** Explicit finding_code → LeakageCategory mapping table (§12 H6). */
export const FINDING_CODE_TO_CATEGORY: Record<string, LeakageCategory> = {
  "ALL-001": "pharmacy_misuse",
  "ALL-002": "pharmacy_misuse",
  "ALL-003": "prescriber_anomaly",
  "ALL-005": "patient_anomaly",
  "ALL-006": "pharmacy_misuse",
  "MFR-001": "pharmacy_misuse",
  "MFR-002": "pharmacy_misuse",
  "MFR-003": "pharmacy_misuse",
  "MFR-004": "pharmacy_misuse",
  "HP-005":  "prescriber_anomaly",
  "HP-008":  "patient_anomaly",
  "REJECT-75-70": "pharmacy_misuse",
  "TH-002":  "prescriber_anomaly",
  "TH-005":  "prescriber_anomaly",
};

/** Anomaly status → LeakageFlag status mapping (adapter, page boundary only). */
export const ANOMALY_STATUS_TO_LEAKAGE: Record<string, LeakageFlag["status"]> = {
  "open": "new",
  "under_review": "under_investigation",
  "confirmed": "confirmed",
  "dismissed": "dismissed",
  "in_recoup": "confirmed",
  "in_audit": "under_investigation",
  "resolved": "dismissed",
  "written_off": "dismissed",
};

/** LeakageFlag status → anomaly API status (reverse for filter pushdown). */
export const LEAKAGE_STATUS_TO_ANOMALY: Record<LeakageFlag["status"], string> = {
  "new": "open",
  "under_investigation": "under_review",
  "confirmed": "confirmed",
  "dismissed": "dismissed",
};

/** Build reverse map: LeakageCategory → finding_codes[] (for filter pushdown). */
export const CATEGORY_TO_FINDING_CODES: Record<LeakageCategory, string[]> = (() => {
  const result: Partial<Record<LeakageCategory, string[]>> = {};
  for (const [code, cat] of Object.entries(FINDING_CODE_TO_CATEGORY)) {
    if (!result[cat]) result[cat] = [];
    result[cat]!.push(code);
  }
  return result as Record<LeakageCategory, string[]>;
})();

/** Adapt AnomalyRead → LeakageFlag shape (page boundary only, NOT a shared-type mutation). */
export function anomalyToLeakageFlag(a: AnomalyRead): LeakageFlag {
  const entityName =
    a.entity_type === "prescriber"
      ? (a.prescriber_name ?? a.finding_code)
      : (a.pharmacy_name ?? a.finding_code);

  return {
    id: a.id,
    tenant_id: a.tenant_id ?? "",
    category: FINDING_CODE_TO_CATEGORY[a.finding_code] ?? "pharmacy_misuse",
    entity_type:
      a.entity_type === "prescriber"
        ? "prescriber"
        : a.entity_type === "pharmacy"
        ? "pharmacy"
        : "pharmacy",
    entity_name: entityName,
    entity_id: a.id,
    estimated_leakage: a.amount_paid ?? "0.00",
    status: ANOMALY_STATUS_TO_LEAKAGE[a.status] ?? "new",
    date_flagged: a.created_at,
    investigation_id: undefined,
    program_name: undefined,
  };
}

/**
 * Filter values shape accepted by the leakage page.
 * Used by buildAnomalyQueryParams.
 */
export interface AnomalyFilterValues {
  category?: LeakageCategory[];
  severity?: string;
  status?: string[];
  entity_type?: string;
  finding_code?: string[];
  data_source_run_id?: string;
  page?: number;
  page_size?: number;
}

/**
 * Convert UI filter values into backend query params for GET /anomalies.
 * Maps LeakageCategory → finding_codes (via reverse map) and
 * leakage status → anomaly status (via LEAKAGE_STATUS_TO_ANOMALY).
 */
export function buildAnomalyQueryParams(
  filters: AnomalyFilterValues
): Record<string, unknown> {
  const params: Record<string, unknown> = {};

  // Category → finding_codes (reverse map)
  if (filters.category && filters.category.length > 0) {
    const codes: string[] = [];
    for (const cat of filters.category) {
      const forCat = CATEGORY_TO_FINDING_CODES[cat];
      if (forCat) codes.push(...forCat);
    }
    if (codes.length > 0) params.finding_codes = codes;
  }

  // Explicit finding_code override (rule filter)
  if (filters.finding_code && filters.finding_code.length > 0) {
    params.finding_codes = filters.finding_code;
  }

  if (filters.severity) params.severity = filters.severity;

  // Status: map leakage → anomaly status (single value only — backend is single-status)
  if (filters.status && filters.status.length > 0) {
    const mappedStatus = LEAKAGE_STATUS_TO_ANOMALY[filters.status[0] as LeakageFlag["status"]];
    if (mappedStatus) params.status = mappedStatus;
  }

  if (filters.entity_type) params.entity_type = filters.entity_type;
  if (filters.data_source_run_id) params.data_source_run_id = filters.data_source_run_id;
  if (filters.page != null) params.page = filters.page;
  if (filters.page_size != null) params.page_size = filters.page_size;

  return params;
}
