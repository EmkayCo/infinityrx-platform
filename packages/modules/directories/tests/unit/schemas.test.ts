// tests/unit/schemas.test.ts
// Validates zod shapes, ID_PATTERNS, and DatasetKey enum for the directories module.
import { describe, it, expect } from "vitest";
import {
  DatasetKeySchema,
  SearchResultRecordSchema,
  SearchResponseSchema,
  ID_PATTERNS,
} from "../../src/search/schemas.js";

describe("DatasetKeySchema", () => {
  it("accepts all 18 primary source keys", () => {
    const keys = [
      "nppes",
      "ncpdp",
      "fda_ndc",
      "fda_orange_book",
      "fda_purple_book",
      "fda_drug_shortages",
      "fda_rems",
      "rxnorm",
      "hcpcs",
      "icd10_cm",
      "cms_asp",
      "cms_nadac",
      "state_medicaid_bins",
      "cms_opt_out",
      "ofac_sdn",
      "sam_exclusions",
      "oig_leie",
      "dea_registrations",
    ];
    expect(keys).toHaveLength(18);
    for (const key of keys) {
      expect(() => DatasetKeySchema.parse(key)).not.toThrow();
    }
  });

  it("rejects nppes_monthly (scheduler sub-mode, not a browse-cluster key)", () => {
    expect(() => DatasetKeySchema.parse("nppes_monthly")).toThrow();
  });

  it("rejects nppes_deactivation (scheduler sub-mode, not a browse-cluster key)", () => {
    expect(() => DatasetKeySchema.parse("nppes_deactivation")).toThrow();
  });

  it("rejects unknown keys", () => {
    expect(() => DatasetKeySchema.parse("unknown_source")).toThrow();
    expect(() => DatasetKeySchema.parse("")).toThrow();
    expect(() => DatasetKeySchema.parse("fdb")).toThrow();
  });
});

describe("SearchResultRecordSchema", () => {
  it("parses a valid record", () => {
    const record = {
      dataset: "nppes",
      id: "1234567890",
      display: "Dr. Jane Smith",
      secondary: "Internal Medicine",
      source_date: "2026-05-10",
      run_id: "run-abc-123",
    };
    const parsed = SearchResultRecordSchema.parse(record);
    expect(parsed.dataset).toBe("nppes");
    expect(parsed.id).toBe("1234567890");
  });

  it("defaults secondary to empty string when omitted", () => {
    const record = {
      dataset: "fda_ndc",
      id: "12345678901",
      display: "Aspirin 325mg",
      source_date: null,
      run_id: null,
    };
    const parsed = SearchResultRecordSchema.parse(record);
    expect(parsed.secondary).toBe("");
  });

  it("accepts null source_date and run_id", () => {
    const record = {
      dataset: "ncpdp",
      id: "1234567",
      display: "CVS Pharmacy",
      secondary: "Chicago, IL",
      source_date: null,
      run_id: null,
    };
    const parsed = SearchResultRecordSchema.parse(record);
    expect(parsed.source_date).toBeNull();
    expect(parsed.run_id).toBeNull();
  });

  it("rejects empty id", () => {
    expect(() =>
      SearchResultRecordSchema.parse({
        dataset: "nppes",
        id: "",
        display: "Dr. Smith",
        secondary: "",
        source_date: null,
        run_id: null,
      }),
    ).toThrow();
  });

  it("rejects empty display", () => {
    expect(() =>
      SearchResultRecordSchema.parse({
        dataset: "nppes",
        id: "1234567890",
        display: "",
        secondary: "",
        source_date: null,
        run_id: null,
      }),
    ).toThrow();
  });

  it("accepts optional b9_blocked flag", () => {
    const record = {
      dataset: "fda_ndc",
      id: "12345678901",
      display: "Some Drug",
      secondary: "",
      source_date: null,
      run_id: null,
      b9_blocked: true,
    };
    const parsed = SearchResultRecordSchema.parse(record);
    expect(parsed.b9_blocked).toBe(true);
  });
});

describe("SearchResponseSchema", () => {
  it("parses a valid response envelope", () => {
    const response = {
      results: [],
      is_partial: false,
      timed_out_datasets: [],
    };
    const parsed = SearchResponseSchema.parse(response);
    expect(parsed.is_partial).toBe(false);
    expect(parsed.timed_out_datasets).toHaveLength(0);
  });

  it("parses a partial response with timed-out datasets", () => {
    const response = {
      results: [
        {
          dataset: "nppes",
          id: "1234567890",
          display: "Dr. Smith",
          secondary: "",
          source_date: null,
          run_id: null,
        },
      ],
      is_partial: true,
      timed_out_datasets: ["ncpdp", "fda_ndc"],
    };
    const parsed = SearchResponseSchema.parse(response);
    expect(parsed.is_partial).toBe(true);
    expect(parsed.timed_out_datasets).toEqual(["ncpdp", "fda_ndc"]);
    expect(parsed.results).toHaveLength(1);
  });
});

describe("ID_PATTERNS", () => {
  describe("NPI", () => {
    it("matches 10-digit NPI", () => {
      expect(ID_PATTERNS.NPI.test("1234567890")).toBe(true);
      expect(ID_PATTERNS.NPI.test("9876543210")).toBe(true);
    });

    it("rejects non-10-digit strings", () => {
      expect(ID_PATTERNS.NPI.test("123456789")).toBe(false);  // 9 digits
      expect(ID_PATTERNS.NPI.test("12345678901")).toBe(false); // 11 digits
      expect(ID_PATTERNS.NPI.test("123456789A")).toBe(false);  // letter
    });
  });

  describe("NDC_11", () => {
    it("matches 11-digit NDC", () => {
      expect(ID_PATTERNS.NDC_11.test("12345678901")).toBe(true);
    });

    it("rejects non-11-digit", () => {
      expect(ID_PATTERNS.NDC_11.test("1234567890")).toBe(false);
      expect(ID_PATTERNS.NDC_11.test("123456789012")).toBe(false);
    });
  });

  describe("NDC_HYPHENATED", () => {
    it("matches hyphenated NDC formats", () => {
      expect(ID_PATTERNS.NDC_HYPHENATED.test("1234-5678-90")).toBe(true);
      expect(ID_PATTERNS.NDC_HYPHENATED.test("12345-678-90")).toBe(true);
      expect(ID_PATTERNS.NDC_HYPHENATED.test("12345-6789-0")).toBe(true);
    });

    it("rejects non-hyphenated 11-digit NDC", () => {
      expect(ID_PATTERNS.NDC_HYPHENATED.test("12345678901")).toBe(false);
    });
  });

  describe("HCPCS", () => {
    it("matches HCPCS code J0135", () => {
      expect(ID_PATTERNS.HCPCS.test("J0135")).toBe(true);
    });

    it("matches lowercase hcpcs", () => {
      expect(ID_PATTERNS.HCPCS.test("j0135")).toBe(true);
    });

    it("rejects invalid HCPCS", () => {
      expect(ID_PATTERNS.HCPCS.test("10135")).toBe(false); // digit first
      expect(ID_PATTERNS.HCPCS.test("J013")).toBe(false);  // only 3 digits
      expect(ID_PATTERNS.HCPCS.test("J01356")).toBe(false); // 5 digits
    });
  });

  describe("ICD10", () => {
    it("matches ICD-10 code Z87.891", () => {
      expect(ID_PATTERNS.ICD10.test("Z87.891")).toBe(true);
    });

    it("matches ICD-10 without decimal", () => {
      expect(ID_PATTERNS.ICD10.test("Z87")).toBe(true);
    });

    it("matches lowercase icd10", () => {
      expect(ID_PATTERNS.ICD10.test("z87.891")).toBe(true);
    });

    it("rejects invalid ICD-10", () => {
      expect(ID_PATTERNS.ICD10.test("887")).toBe(false);    // digit first
      expect(ID_PATTERNS.ICD10.test("Z8")).toBe(false);     // only 1 digit
    });
  });
});
