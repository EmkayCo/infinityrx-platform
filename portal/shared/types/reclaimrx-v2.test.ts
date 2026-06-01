/**
 * Unit tests for reclaimrx-v2 types and adapter.
 * Covers: FINDING_CODE_TO_CATEGORY mapping, ANOMALY_STATUS_TO_LEAKAGE mapping,
 * anomalyToLeakageFlag adapter, and filter-pushdown query-param construction.
 */
import { describe, it, expect } from "vitest";
import {
  FINDING_CODE_TO_CATEGORY,
  ANOMALY_STATUS_TO_LEAKAGE,
  anomalyToLeakageFlag,
  buildAnomalyQueryParams,
} from "./reclaimrx-v2";
import type { AnomalyRead } from "./reclaimrx-v2";

const BASE_ANOMALY: AnomalyRead = {
  id: "aaa-111-222-333",
  tenant_id: "bbb-222-333-444",
  finding_code: "ALL-002",
  finding_summary: "Phantom pharmacy",
  severity: "critical",
  confidence: "0.9000",
  status: "open",
  entity_type: "pharmacy",
  pharmacy_npi: "1234567890",
  pharmacy_name: "Test Pharmacy",
  prescriber_npi: null,
  prescriber_name: null,
  ndc: null,
  amount_paid: "120.50",
  amount_billed: "130.00",
  recovery_amount: null,
  date_of_service: "2026-01-15",
  data_source_run_id: null,
  created_at: "2026-05-31T10:00:00Z",
};

// ─── FINDING_CODE_TO_CATEGORY ────────────────────────────────────────────────

describe("FINDING_CODE_TO_CATEGORY", () => {
  it("maps ALL-001 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-001"]).toBe("pharmacy_misuse");
  });
  it("maps ALL-002 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-002"]).toBe("pharmacy_misuse");
  });
  it("maps ALL-003 to prescriber_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-003"]).toBe("prescriber_anomaly");
  });
  it("maps ALL-005 to patient_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-005"]).toBe("patient_anomaly");
  });
  it("maps ALL-006 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["ALL-006"]).toBe("pharmacy_misuse");
  });
  it("maps MFR-001 through MFR-004 to pharmacy_misuse", () => {
    for (const code of ["MFR-001", "MFR-002", "MFR-003", "MFR-004"]) {
      expect(FINDING_CODE_TO_CATEGORY[code]).toBe("pharmacy_misuse");
    }
  });
  it("maps HP-005 to prescriber_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["HP-005"]).toBe("prescriber_anomaly");
  });
  it("maps HP-008 to patient_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["HP-008"]).toBe("patient_anomaly");
  });
  it("maps REJECT-75-70 to pharmacy_misuse", () => {
    expect(FINDING_CODE_TO_CATEGORY["REJECT-75-70"]).toBe("pharmacy_misuse");
  });
  it("maps TH-002 to prescriber_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["TH-002"]).toBe("prescriber_anomaly");
  });
  it("maps TH-005 to prescriber_anomaly", () => {
    expect(FINDING_CODE_TO_CATEGORY["TH-005"]).toBe("prescriber_anomaly");
  });
  it("returns undefined for unknown code (default handled at adapter)", () => {
    expect(FINDING_CODE_TO_CATEGORY["UNKNOWN-99"]).toBeUndefined();
  });
});

// ─── ANOMALY_STATUS_TO_LEAKAGE ────────────────────────────────────────────────

describe("ANOMALY_STATUS_TO_LEAKAGE", () => {
  it("maps open → new", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["open"]).toBe("new");
  });
  it("maps under_review → under_investigation", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["under_review"]).toBe("under_investigation");
  });
  it("maps confirmed → confirmed", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["confirmed"]).toBe("confirmed");
  });
  it("maps dismissed → dismissed", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["dismissed"]).toBe("dismissed");
  });
  it("maps in_recoup → confirmed", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["in_recoup"]).toBe("confirmed");
  });
  it("maps in_audit → under_investigation", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["in_audit"]).toBe("under_investigation");
  });
  it("maps resolved → dismissed", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["resolved"]).toBe("dismissed");
  });
  it("maps written_off → dismissed", () => {
    expect(ANOMALY_STATUS_TO_LEAKAGE["written_off"]).toBe("dismissed");
  });
});

// ─── anomalyToLeakageFlag adapter ────────────────────────────────────────────

describe("anomalyToLeakageFlag", () => {
  it("maps open status → new", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.status).toBe("new");
  });
  it("maps under_review status → under_investigation", () => {
    const flag = anomalyToLeakageFlag({ ...BASE_ANOMALY, status: "under_review" });
    expect(flag.status).toBe("under_investigation");
  });
  it("maps finding_code ALL-002 → pharmacy_misuse", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.category).toBe("pharmacy_misuse");
  });
  it("maps finding_code ALL-003 → prescriber_anomaly", () => {
    const flag = anomalyToLeakageFlag({ ...BASE_ANOMALY, finding_code: "ALL-003" });
    expect(flag.category).toBe("prescriber_anomaly");
  });
  it("defaults unknown finding_code to pharmacy_misuse", () => {
    const flag = anomalyToLeakageFlag({ ...BASE_ANOMALY, finding_code: "UNKNOWN-99" });
    expect(flag.category).toBe("pharmacy_misuse");
  });
  it("sets estimated_leakage from amount_paid", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.estimated_leakage).toBe("120.50");
  });
  it("defaults estimated_leakage to 0.00 when amount_paid is null", () => {
    const flag = anomalyToLeakageFlag({ ...BASE_ANOMALY, amount_paid: null });
    expect(flag.estimated_leakage).toBe("0.00");
  });
  it("sets entity_name from pharmacy_name field", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.entity_name).toBe("Test Pharmacy");
  });
  it("falls back entity_name to finding_code when name is null", () => {
    const flag = anomalyToLeakageFlag({ ...BASE_ANOMALY, pharmacy_name: null });
    expect(flag.entity_name).toBe("ALL-002");
  });
  it("sets id from anomaly id", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.id).toBe("aaa-111-222-333");
  });
  it("sets entity_type pharmacy", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.entity_type).toBe("pharmacy");
  });
  it("sets entity_type prescriber", () => {
    const flag = anomalyToLeakageFlag({
      ...BASE_ANOMALY,
      entity_type: "prescriber",
      pharmacy_npi: null,
      pharmacy_name: null,
      prescriber_npi: "9876543210",
      prescriber_name: "Dr. Smith",
    });
    expect(flag.entity_type).toBe("prescriber");
  });
  it("sets date_flagged from created_at", () => {
    const flag = anomalyToLeakageFlag(BASE_ANOMALY);
    expect(flag.date_flagged).toBe("2026-05-31T10:00:00Z");
  });
});

// ─── Filter-pushdown: buildAnomalyQueryParams ─────────────────────────────────

describe("buildAnomalyQueryParams", () => {
  it("returns empty object when no filters", () => {
    const params = buildAnomalyQueryParams({});
    expect(params).toEqual({});
  });

  it("maps severity filter through", () => {
    const params = buildAnomalyQueryParams({ severity: "critical" });
    expect(params.severity).toBe("critical");
  });

  it("maps entity_type filter through", () => {
    const params = buildAnomalyQueryParams({ entity_type: "pharmacy" });
    expect(params.entity_type).toBe("pharmacy");
  });

  it("maps status filter through (single value)", () => {
    const params = buildAnomalyQueryParams({ status: ["new"] });
    // new → open in anomaly API
    expect(params.status).toBe("open");
  });

  it("maps category → finding_code using FINDING_CODE_TO_CATEGORY reverse map", () => {
    // pharmacy_misuse should produce finding_codes that map to it
    const params = buildAnomalyQueryParams({ category: ["pharmacy_misuse"] });
    expect(Array.isArray(params.finding_codes)).toBe(true);
    const codes = params.finding_codes as string[];
    expect(codes).toContain("ALL-001");
    expect(codes).toContain("ALL-002");
    expect(codes).toContain("MFR-001");
  });

  it("maps prescriber_anomaly category to correct finding_codes", () => {
    const params = buildAnomalyQueryParams({ category: ["prescriber_anomaly"] });
    const codes = params.finding_codes as string[];
    expect(codes).toContain("ALL-003");
    expect(codes).toContain("HP-005");
    expect(codes).toContain("TH-002");
    expect(codes).toContain("TH-005");
  });

  it("maps data_source_run_id filter through", () => {
    const params = buildAnomalyQueryParams({ data_source_run_id: "run-abc-123" });
    expect(params.data_source_run_id).toBe("run-abc-123");
  });

  it("includes page and page_size when provided", () => {
    const params = buildAnomalyQueryParams({ page: 2, page_size: 50 });
    expect(params.page).toBe(2);
    expect(params.page_size).toBe(50);
  });
});
