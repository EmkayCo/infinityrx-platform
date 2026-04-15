// @vitest-environment node
/**
 * Unit tests for new GTN/ReclaimRx mock handlers.
 *
 * Verifies that the four new GTN endpoints return valid shapes and
 * that all monetary fields are valid decimal strings (no floats, no NaN).
 */
import { describe, it, expect, beforeAll } from "vitest";
import { mockResponse } from "@shared/lib/mock-data";
import { expectShape, expectValidMoney } from "../../fixtures/test-helpers";

beforeAll(() => {
  process.env.NEXT_PUBLIC_USE_MOCK_DATA = "true";
});

// ─── GTN Summary ─────────────────────────────────────────────────────────────

describe("mock handler: /api/v1/reclaimrx/gtn-summary", () => {
  it("returns required GTN summary fields", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/reclaimrx/gtn-summary"
    );
    expectShape(data, [
      "total_copay_spend",
      "identified_leakage",
      "gtn_ratio",
      "gtn_ratio_prev",
      "active_investigations",
      "recovered",
      "recovery_rate",
      "leakage_by_category",
      "leakage_by_program",
      "top_flagged_pharmacies",
    ]);
  });

  it("monetary fields are valid decimal strings", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/reclaimrx/gtn-summary"
    );
    expectValidMoney(data.total_copay_spend, "total_copay_spend");
    expectValidMoney(data.identified_leakage, "identified_leakage");
    expectValidMoney(data.recovered, "recovered");
  });

  it("gtn_ratio is a string parseable as a decimal between 0 and 1", async () => {
    const data = await mockResponse<Record<string, unknown>>(
      "GET",
      "/api/v1/reclaimrx/gtn-summary"
    );
    const ratio = parseFloat(data.gtn_ratio as string);
    expect(Number.isFinite(ratio)).toBe(true);
    expect(ratio).toBeGreaterThan(0);
    expect(ratio).toBeLessThan(1);
  });

  it("leakage_by_category is a non-empty array with category and amount fields", async () => {
    const data = await mockResponse<{ leakage_by_category: unknown[] }>(
      "GET",
      "/api/v1/reclaimrx/gtn-summary"
    );
    expect(Array.isArray(data.leakage_by_category)).toBe(true);
    expect(data.leakage_by_category.length).toBeGreaterThan(0);

    for (const item of data.leakage_by_category as Record<string, unknown>[]) {
      expect(typeof item.category).toBe("string");
      expectValidMoney(item.amount, `leakage_by_category[${item.category as string}].amount`);
      expect(typeof item.count).toBe("number");
    }
  });

  it("top_flagged_pharmacies has npi, pharmacy_name, risk_score", async () => {
    const data = await mockResponse<{ top_flagged_pharmacies: unknown[] }>(
      "GET",
      "/api/v1/reclaimrx/gtn-summary"
    );
    expect(Array.isArray(data.top_flagged_pharmacies)).toBe(true);
    for (const p of data.top_flagged_pharmacies as Record<string, unknown>[]) {
      expect(typeof p.npi).toBe("string");
      expect(typeof p.pharmacy_name).toBe("string");
      expect(typeof p.risk_score).toBe("number");
      expect(p.risk_score as number).toBeGreaterThanOrEqual(0);
      expect(p.risk_score as number).toBeLessThanOrEqual(100);
      expectValidMoney(p.total_leakage, "total_leakage");
    }
  });
});

// ─── GTN Trend ───────────────────────────────────────────────────────────────

describe("mock handler: /api/v1/reclaimrx/gtn-trend", () => {
  it("returns an array of 12 monthly data points", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/gtn-trend"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(12);
  });

  it("each point has month (YYYY-MM), gtn_ratio, leakage_amount", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/gtn-trend"
    );
    for (const point of data as Record<string, unknown>[]) {
      expect(typeof point.month).toBe("string");
      expect(point.month as string).toMatch(/^\d{4}-\d{2}$/);
      const ratio = parseFloat(point.gtn_ratio as string);
      expect(Number.isFinite(ratio)).toBe(true);
      expectValidMoney(point.leakage_amount, `trend[${point.month as string}].leakage_amount`);
    }
  });
});

// ─── Leakage Flags ───────────────────────────────────────────────────────────

describe("mock handler: /api/v1/reclaimrx/leakage", () => {
  it("returns a non-empty array of leakage flags", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/leakage"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
  });

  it("each flag has required fields including category and estimated_leakage", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/leakage"
    );
    for (const flag of data as Record<string, unknown>[]) {
      expectShape(flag, ["id", "category", "entity_type", "entity_name", "estimated_leakage", "status"]);
      expectValidMoney(flag.estimated_leakage, `flag[${flag.id as string}].estimated_leakage`);
      expect(typeof flag.category).toBe("string");
      expect([
        "pharmacy_misuse",
        "accumulator",
        "maximizer",
        "three_forty_b_overlap",
        "alternative_funding",
        "prescriber_anomaly",
        "patient_anomaly",
      ]).toContain(flag.category);
    }
  });

  it("all monetary fields are valid decimal strings (no floats)", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/leakage"
    );
    for (const flag of data as Record<string, unknown>[]) {
      const amount = flag.estimated_leakage as string;
      // Must be a decimal string, not a float (no scientific notation, no NaN)
      expect(amount).toMatch(/^\d+\.\d{2}$/);
    }
  });
});

// ─── Pharmacy Risk Scores ─────────────────────────────────────────────────────

describe("mock handler: /api/v1/reclaimrx/risk-scores", () => {
  it("returns an array of pharmacy risk scores", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/risk-scores"
    );
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBeGreaterThan(0);
  });

  it("each pharmacy has npi, risk_score (0-100), risk_tier, factors[]", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/risk-scores"
    );
    for (const p of data as Record<string, unknown>[]) {
      expectShape(p, ["npi", "pharmacy_name", "risk_score", "risk_tier", "factors", "total_copay_paid"]);
      const score = p.risk_score as number;
      expect(typeof score).toBe("number");
      expect(score).toBeGreaterThanOrEqual(0);
      expect(score).toBeLessThanOrEqual(100);
      expect(["low", "medium", "high", "critical"]).toContain(p.risk_tier);
      expect(Array.isArray(p.factors)).toBe(true);
      expectValidMoney(p.total_copay_paid, `pharmacy[${p.npi as string}].total_copay_paid`);
    }
  });

  it("risk_tier is consistent with risk_score ranges", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/risk-scores"
    );
    for (const p of data as Record<string, unknown>[]) {
      const score = p.risk_score as number;
      const tier = p.risk_tier as string;
      if (score >= 75) expect(tier).toBe("critical");
      else if (score >= 50) expect(tier).toBe("high");
      else if (score >= 25) expect(tier).toBe("medium");
      else expect(tier).toBe("low");
    }
  });

  it("NPI is exactly 10 digits", async () => {
    const data = await mockResponse<unknown[]>(
      "GET",
      "/api/v1/reclaimrx/risk-scores"
    );
    for (const p of data as Record<string, unknown>[]) {
      expect(p.npi as string).toMatch(/^\d{10}$/);
    }
  });
});
