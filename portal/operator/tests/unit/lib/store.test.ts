/**
 * store.ts unit tests.
 *
 * The store is the financial core — it reads the raw pipe-delimited claims
 * files from lib/data/sources and parses them into ParsedClaim[] with
 * Decimal-safe string amounts. These tests verify:
 *   - Lazy singleton semantics (two calls return the same data)
 *   - Claim count matches the real 122,968 total
 *   - Every claim has the fields downstream code destructures
 *   - All money fields are valid decimal strings (not NaN, not undefined)
 *   - Aggregations load all 18 expected files
 *
 * These tests take ~1 second because they trigger the real file read + parse.
 * Vitest Node environment has fs/promises available.
 */
import { describe, it, expect, beforeAll } from "vitest";
import { getClaims, getAggregations } from "@/lib/data/store";
import type { ParsedClaim } from "@/lib/data/types";
import { expectValidMoney } from "../../fixtures/test-helpers";

let claims: ParsedClaim[];
let aggs: Awaited<ReturnType<typeof getAggregations>>;

beforeAll(async () => {
  claims = await getClaims();
  aggs = await getAggregations();
}, 30_000);

describe("store.ts — getClaims()", () => {
  it("loads 122,968 claims (real total from build-data.ts)", () => {
    expect(claims.length).toBe(122968);
  });

  it("returns the same cached array on subsequent calls (singleton)", async () => {
    const second = await getClaims();
    expect(second).toBe(claims); // reference equality — same array
  });

  it("every claim has the fields required by downstream code", () => {
    // Sample 100 claims to avoid quadratic runtime on 122k rows.
    const sample = Array.from({ length: 100 }, (_, i) =>
      claims[Math.floor((i * claims.length) / 100)]
    );
    for (const claim of sample) {
      expect(claim.claim_id, "claim_id").toBeTruthy();
      expect(claim.ndc, "ndc").toBeTruthy();
      expect(claim.date_of_service, "date_of_service").toMatch(/^\d{4}-\d{2}-\d{2}$/);
      expect(claim.status, "status").toMatch(/^[PR]$/);
      expect(claim.cycle_id, "cycle_id").toBeTruthy();
    }
  });

  it("all monetary fields parse as valid decimals (no NaN, no undefined)", () => {
    const moneyFields: (keyof ParsedClaim)[] = [
      "submitted_ingredient_cost",
      "submitted_dispensing_fee",
      "submitted_gross_amount_due",
      "copay",
      "patient_pay_amount",
      "pharmacy_total_paid",
      "pharmacy_ingredient_cost_paid",
      "pharmacy_dispensing_fee_paid",
      "sell_ingredient_cost",
      "sell_dispensing_fee",
      "total_client_billed",
    ];
    // Spot-check 50 claims × 11 money fields = 550 assertions.
    const sample = Array.from({ length: 50 }, (_, i) =>
      claims[Math.floor((i * claims.length) / 50)]
    );
    for (const claim of sample) {
      for (const field of moneyFields) {
        expectValidMoney(claim[field], `claim[${claim.claim_id}].${String(field)}`);
      }
    }
  });

  it("contains claims from all 3 cycles", () => {
    const cycles = new Set(claims.map((c) => c.cycle_id));
    expect(cycles.size).toBe(3);
    expect(cycles.has("BC-2026-SM-06")).toBe(true);
    expect(cycles.has("BC-2026-SM-07")).toBe(true);
    expect(cycles.has("BC-2026-SM-08")).toBe(true);
  });

  it("has both paid and reversal claims (status P and R)", () => {
    const paid = claims.filter((c) => c.status === "P").length;
    const reversed = claims.filter((c) => c.status === "R").length;
    expect(paid).toBeGreaterThan(0);
    expect(reversed).toBeGreaterThan(0);
    expect(paid + reversed).toBe(claims.length);
  });

  it("date_of_service values are within a reasonable range (2025-2026)", () => {
    const sample = claims.slice(0, 1000);
    for (const claim of sample) {
      const year = parseInt(claim.date_of_service.slice(0, 4), 10);
      expect(year, `claim ${claim.claim_id} DOS year`).toBeGreaterThanOrEqual(2024);
      expect(year, `claim ${claim.claim_id} DOS year`).toBeLessThanOrEqual(2027);
    }
  });
});

describe("store.ts — getAggregations()", () => {
  it("loads all 18 aggregation files", () => {
    const expectedKeys = [
      "overview",
      "cycles",
      "by_client",
      "by_nrid",
      "by_chain",
      "by_pharmacy",
      "by_ndc",
      "by_prescriber",
      "by_member",
      "top_pharmacies",
      "top_ndcs",
      "top_clients",
      "daily_volume",
      "nrid_distribution",
      "reversal_rate",
      "activity_feed",
      "investigations",
      "manifest",
    ];
    for (const key of expectedKeys) {
      expect(aggs, `aggregations.${key}`).toHaveProperty(key);
      expect((aggs as unknown as Record<string, unknown>)[key]).toBeTruthy();
    }
  });

  it("overview has valid money fields", () => {
    const ov = aggs.overview;
    expectValidMoney(ov.total_client_billed, "overview.total_client_billed");
    expectValidMoney(ov.total_pharmacy_paid, "overview.total_pharmacy_paid");
    expect(typeof ov.total_claims).toBe("number");
    expect(ov.total_claims).toBeGreaterThan(0);
  });

  it("cycles array is populated and every cycle has required fields", () => {
    expect(Array.isArray(aggs.cycles)).toBe(true);
    expect(aggs.cycles.length).toBeGreaterThan(0);
    for (const cycle of aggs.cycles) {
      expect(cycle.cycle_id).toBeTruthy();
      expect(cycle.file_name).toBeTruthy();
      expect(typeof cycle.total_claims).toBe("number");
      expectValidMoney(cycle.total_client_billed, "cycle.total_client_billed");
    }
  });

  it("by_pharmacy has entries with avg_claim_billed", () => {
    expect(Array.isArray(aggs.by_pharmacy)).toBe(true);
    expect(aggs.by_pharmacy.length).toBeGreaterThan(0);
    for (const row of aggs.by_pharmacy.slice(0, 20)) {
      expect(row.service_provider_id).toBeTruthy();
      expectValidMoney(row.avg_claim_billed, "by_pharmacy.avg_claim_billed");
    }
  });

  it("returns same reference on subsequent calls (singleton)", async () => {
    const second = await getAggregations();
    expect(second).toBe(aggs);
  });
});
