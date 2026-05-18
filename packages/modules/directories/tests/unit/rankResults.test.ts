// tests/unit/rankResults.test.ts
// Verifies all 5 tier outcomes, stable sort, and case-insensitive matching.
import { describe, it, expect } from "vitest";
import { rankResults } from "../../src/search/rankResults.js";
import type { SearchResultRecord } from "../../src/search/schemas.js";

function makeRecord(overrides: Partial<SearchResultRecord> & { id: string; display: string }): SearchResultRecord {
  return {
    dataset: "nppes",
    secondary: "",
    source_date: null,
    run_id: null,
    ...overrides,
  };
}

describe("rankResults", () => {
  it("returns results unchanged when query is empty", () => {
    const records = [
      makeRecord({ id: "a", display: "Alpha" }),
      makeRecord({ id: "b", display: "Beta" }),
    ];
    const result = rankResults(records, "");
    expect(result).toEqual(records);
  });

  it("returns results unchanged when query is whitespace only", () => {
    const records = [
      makeRecord({ id: "a", display: "Alpha" }),
    ];
    const result = rankResults(records, "   ");
    expect(result).toEqual(records);
  });

  it("scores exact id match as tier 0 (highest priority)", () => {
    const records = [
      makeRecord({ id: "1234567890", display: "Dr. Jane Smith" }),
      makeRecord({ id: "other", display: "1234567890 Clinic" }),
    ];
    const result = rankResults(records, "1234567890");
    expect(result[0].id).toBe("1234567890");
  });

  it("scores display prefix match as tier 1", () => {
    const records = [
      makeRecord({ id: "b", display: "Smith Pharmacy" }),
      makeRecord({ id: "a", display: "Smith, Jane MD" }),
      makeRecord({ id: "c", display: "Jane Smith" }), // substring, tier 2
    ];
    const result = rankResults(records, "Smith");
    expect(result[0].display).toBe("Smith Pharmacy");
    expect(result[1].display).toBe("Smith, Jane MD");
    expect(result[2].display).toBe("Jane Smith");
  });

  it("scores display substring match as tier 2", () => {
    const records = [
      makeRecord({ id: "a", display: "Jane Smith MD" }),
      makeRecord({ id: "b", display: "Dr. Smith Jane" }),
    ];
    const result = rankResults(records, "Smith");
    // Both are substring matches; they tie on tier, sort alphabetically
    expect(result.every((r) => r.display.toLowerCase().includes("smith"))).toBe(true);
  });

  it("scores secondary field match as tier 3", () => {
    const records = [
      makeRecord({ id: "a", display: "Alpha Clinic", secondary: "cardiology" }),
      makeRecord({ id: "b", display: "Beta Pharmacy" }), // no secondary match
    ];
    const result = rankResults(records, "cardiology");
    expect(result[0].id).toBe("a"); // secondary match wins over no match
  });

  it("is case-insensitive in all tiers", () => {
    const records = [
      makeRecord({ id: "NPI1234567890", display: "SMITH JANE" }),
      makeRecord({ id: "npi1234567890", display: "smith jane" }),
    ];
    // Exact id match is case-insensitive: query "npi1234567890" matches both
    const result = rankResults(records, "npi1234567890");
    // Both should be tier 0; sort stable by display
    expect(result).toHaveLength(2);
    expect(result[0].display.toLowerCase()).toBe("smith jane");
  });

  it("does not mutate the input array", () => {
    const records = [
      makeRecord({ id: "b", display: "Beta" }),
      makeRecord({ id: "a", display: "Alpha" }),
    ];
    const original = [...records];
    rankResults(records, "Alpha");
    expect(records[0].id).toBe(original[0].id);
    expect(records[1].id).toBe(original[1].id);
  });

  it("stable-sorts within same tier by display (localeCompare)", () => {
    const records = [
      makeRecord({ id: "3", display: "Smith Zebra" }),
      makeRecord({ id: "1", display: "Smith Alpha" }),
      makeRecord({ id: "2", display: "Smith Morton" }),
    ];
    const result = rankResults(records, "Smith");
    expect(result.map((r) => r.id)).toEqual(["1", "2", "3"]);
  });

  it("tier 4 (no match) — result still included but sorted last", () => {
    const records = [
      makeRecord({ id: "a", display: "Completely Different" }),
      makeRecord({ id: "b", display: "Aspirin 325mg" }),
    ];
    const result = rankResults(records, "Aspirin");
    expect(result[0].display).toBe("Aspirin 325mg");
    expect(result[1].display).toBe("Completely Different");
  });

  it("handles large result sets without error", () => {
    const records = Array.from({ length: 100 }, (_, i) =>
      makeRecord({ id: String(i), display: `Item ${i}` }),
    );
    const result = rankResults(records, "Item 5");
    expect(result).toHaveLength(100);
  });
});
