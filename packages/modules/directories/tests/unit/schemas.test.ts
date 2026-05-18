// tests/unit/schemas.test.ts
// Validates zod shapes, ID_PATTERNS, and DatasetKey enum for the directories module.
// Plan D: adds IngestionSourceKeySchema, DatasetQualitySchema, QualityResponseSchema.
import { describe, it, expect } from "vitest";
import {
  DatasetKeySchema,
  IngestionSourceKeySchema,
  DatasetQualitySchema,
  QualityResponseSchema,
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

// ── Plan D: IngestionSourceKeySchema ────────────────────────────────────────

describe("IngestionSourceKeySchema", () => {
  it("accepts all 18 browse-cluster keys", () => {
    const browseKeys = [
      "nppes", "ncpdp", "fda_ndc", "fda_orange_book", "fda_purple_book",
      "fda_drug_shortages", "fda_rems", "rxnorm", "hcpcs", "icd10_cm",
      "cms_asp", "cms_nadac", "state_medicaid_bins", "cms_opt_out",
      "ofac_sdn", "sam_exclusions", "oig_leie", "dea_registrations",
    ];
    for (const key of browseKeys) {
      expect(() => IngestionSourceKeySchema.parse(key)).not.toThrow();
    }
  });

  it("accepts the 3 ingestion-only keys", () => {
    expect(() => IngestionSourceKeySchema.parse("nppes_monthly")).not.toThrow();
    expect(() => IngestionSourceKeySchema.parse("nppes_deactivation")).not.toThrow();
    expect(() => IngestionSourceKeySchema.parse("fdb")).not.toThrow();
  });

  it("has 21 total keys (18 browse + 3 ingestion-only)", () => {
    // The enum values array length verifies the superset count.
    expect(IngestionSourceKeySchema.options).toHaveLength(21);
  });

  it("rejects bpg (live API, no IngestionSchedule row)", () => {
    expect(() => IngestionSourceKeySchema.parse("bpg")).toThrow();
  });

  it("rejects relay-health (not a loader)", () => {
    expect(() => IngestionSourceKeySchema.parse("relay-health")).toThrow();
  });

  it("rejects unknown keys", () => {
    expect(() => IngestionSourceKeySchema.parse("unknown_source")).toThrow();
    expect(() => IngestionSourceKeySchema.parse("")).toThrow();
  });
});

// ── Plan D: DatasetQualitySchema ─────────────────────────────────────────────

describe("DatasetQualitySchema", () => {
  const validQualityRow = {
    source: "nppes" as const,
    last_run_at: "2026-05-15T12:00:00Z",
    last_success_at: "2026-05-15T12:00:00Z",
    last_run_status: "completed" as const,
    records_inserted: 100000,
    records_errored: 0,
    cron_expression: "0 3 1 * *",
    next_run_at: "2026-06-01T03:00:00Z",
    cluster: "prescribers" as const,
  };

  it("parses a valid quality row with defaults", () => {
    const parsed = DatasetQualitySchema.parse(validQualityRow);
    expect(parsed.source).toBe("nppes");
    expect(parsed.cluster).toBe("prescribers");
    expect(parsed.is_dismissed).toBe(false);
    expect(parsed.no_loader).toBe(false);
    expect(parsed.b9_blocked).toBe(false);
  });

  it("is_dismissed defaults to false when omitted", () => {
    const parsed = DatasetQualitySchema.parse(validQualityRow);
    expect(parsed.is_dismissed).toBe(false);
  });

  it("accepts is_dismissed: true", () => {
    const parsed = DatasetQualitySchema.parse({ ...validQualityRow, is_dismissed: true });
    expect(parsed.is_dismissed).toBe(true);
  });

  it("accepts null last_run_at and last_success_at", () => {
    const parsed = DatasetQualitySchema.parse({
      ...validQualityRow,
      last_run_at: null,
      last_success_at: null,
      last_run_status: null,
      records_inserted: null,
      records_errored: null,
      cron_expression: null,
      next_run_at: null,
    });
    expect(parsed.last_run_at).toBeNull();
    expect(parsed.last_success_at).toBeNull();
    expect(parsed.last_run_status).toBeNull();
  });

  it("accepts all valid last_run_status values", () => {
    const statuses = ["completed", "completed_core", "failed", "skipped_unchanged", "running"] as const;
    for (const status of statuses) {
      const parsed = DatasetQualitySchema.parse({ ...validQualityRow, last_run_status: status });
      expect(parsed.last_run_status).toBe(status);
    }
  });

  it("accepts fdb with b9_blocked and no_loader flags", () => {
    const parsed = DatasetQualitySchema.parse({
      source: "fdb",
      last_run_at: null,
      last_success_at: null,
      last_run_status: null,
      records_inserted: null,
      records_errored: null,
      cron_expression: null,
      next_run_at: null,
      cluster: "drugs",
      b9_blocked: true,
      no_loader: true,
    });
    expect(parsed.source).toBe("fdb");
    expect(parsed.b9_blocked).toBe(true);
    expect(parsed.no_loader).toBe(true);
  });

  it("rejects unknown cluster value", () => {
    expect(() =>
      DatasetQualitySchema.parse({ ...validQualityRow, cluster: "unknown_cluster" }),
    ).toThrow();
  });

  it("rejects bpg as source (not in IngestionSourceKeySchema)", () => {
    expect(() =>
      DatasetQualitySchema.parse({ ...validQualityRow, source: "bpg" }),
    ).toThrow();
  });
});

// ── Plan D: QualityResponseSchema ────────────────────────────────────────────

describe("QualityResponseSchema", () => {
  it("parses a valid quality response envelope", () => {
    const response = {
      datasets: [
        {
          source: "nppes",
          last_run_at: "2026-05-15T12:00:00Z",
          last_success_at: "2026-05-15T12:00:00Z",
          last_run_status: "completed",
          records_inserted: 9000000,
          records_errored: 0,
          cron_expression: "0 3 1 * *",
          next_run_at: "2026-06-01T03:00:00Z",
          cluster: "prescribers",
        },
      ],
      as_of: "2026-05-18T07:00:00Z",
    };
    const parsed = QualityResponseSchema.parse(response);
    expect(parsed.datasets).toHaveLength(1);
    expect(parsed.as_of).toBe("2026-05-18T07:00:00Z");
    expect(parsed.is_partial).toBe(false);
  });

  it("parses empty datasets array with as_of string", () => {
    const response = { datasets: [], as_of: "2026-05-18T07:00:00Z" };
    const parsed = QualityResponseSchema.parse(response);
    expect(parsed.datasets).toHaveLength(0);
  });

  it("is_partial defaults to false when omitted", () => {
    const parsed = QualityResponseSchema.parse({ datasets: [], as_of: "2026-05-18T07:00:00Z" });
    expect(parsed.is_partial).toBe(false);
  });

  it("accepts is_partial: true for degraded backend responses", () => {
    const parsed = QualityResponseSchema.parse({
      datasets: [],
      as_of: "2026-05-18T07:00:00Z",
      is_partial: true,
    });
    expect(parsed.is_partial).toBe(true);
  });
});
