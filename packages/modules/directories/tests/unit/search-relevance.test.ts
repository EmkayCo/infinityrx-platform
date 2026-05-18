// tests/unit/search-relevance.test.ts
// Search relevance regression tests using fixture data.
// Verifies all 4 ranking tiers from rankResults.ts against fixture records.
// Pure unit tests — no backend, no BFF, no network required.
import { describe, test, expect } from "vitest";
import { rankResults } from "../../src/search/rankResults.js";
import type { SearchResultRecord } from "../../src/search/schemas.js";

// ── Fixture records (mirror packages/modules/directories/fixtures/) ─────────
// NPI 8084000008 is the first fixture prescriber (Jane Smith DO).

const FIXTURE_PRESCRIBER: SearchResultRecord = {
  dataset: "nppes",
  id: "8084000008",
  display: "Dr. Jane Smith DO",
  secondary: "Internal Medicine",
  source_date: "2026-05-10",
  run_id: "aaaaaaaa-0001-0001-0001-000000000001",
};

const FIXTURE_DRUG: SearchResultRecord = {
  dataset: "fda_ndc",
  // Public NDC — atorvastatin 20mg (first fixture in drugs-fda-ndc.json)
  id: "00071015523",
  display: "Atorvastatin Calcium (Lipitor)",
  secondary: "atorvastatin calcium",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_HCPCS: SearchResultRecord = {
  dataset: "hcpcs",
  id: "J0135",
  display: "Adalimumab injection",
  secondary: "J0135",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_ICD10: SearchResultRecord = {
  dataset: "icd10_cm",
  id: "Z87.891",
  display: "Personal history of nicotine dependence",
  secondary: "Z87.891",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_SAM: SearchResultRecord = {
  dataset: "sam_exclusions",
  id: "SAM-GUID-00001",
  display: "ABC Medical Supply Co",
  secondary: "INELIGIBLE",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_PHARMACY: SearchResultRecord = {
  dataset: "ncpdp",
  id: "1234567",
  display: "Sunrise Community Pharmacy",
  secondary: "Chicago IL",
  source_date: "2026-05-10",
  run_id: null,
};

const FIXTURE_NADAC: SearchResultRecord = {
  dataset: "cms_nadac",
  id: "00093314956",
  display: "Metformin HCl 500 mg tablet",
  secondary: "metformin hydrochloride",
  source_date: "2026-01-08",
  run_id: null,
};

const FIXTURE_CMS_ASP: SearchResultRecord = {
  dataset: "cms_asp",
  id: "J0135",
  display: "Adalimumab injection (CMS-ASP)",
  secondary: "J0135 — 2026Q1",
  source_date: "2026-01-01",
  run_id: null,
};

const FIXTURE_OIG: SearchResultRecord = {
  dataset: "oig_leie",
  id: "OIG-00001",
  display: "Eastside Medical Clinic",
  secondary: "Exclusion type: MANDATORY",
  source_date: "2026-05-01",
  run_id: null,
};

const FIXTURE_DEA: SearchResultRecord = {
  dataset: "dea_registrations",
  id: "AB1234567",
  display: "Anderson Thomas MD",
  secondary: "Schedule II-V — FL",
  source_date: "2026-05-01",
  run_id: null,
};

const ALL_FIXTURES = [
  FIXTURE_PRESCRIBER,
  FIXTURE_DRUG,
  FIXTURE_HCPCS,
  FIXTURE_ICD10,
  FIXTURE_SAM,
  FIXTURE_PHARMACY,
  FIXTURE_NADAC,
  FIXTURE_CMS_ASP,
  FIXTURE_OIG,
  FIXTURE_DEA,
];

// ── Tier 0: exact id match ────────────────────────────────────────────────────

describe("search relevance regression — Tier 0: exact id match", () => {
  test("NPI exact match scores top over display matches", () => {
    const results = rankResults(ALL_FIXTURES, "8084000008");
    expect(results[0].dataset).toBe("nppes");
    expect(results[0].id).toBe("8084000008");
  });

  test("NDC exact match scores top", () => {
    const results = rankResults(ALL_FIXTURES, "00071015523");
    expect(results[0].dataset).toBe("fda_ndc");
    expect(results[0].id).toBe("00071015523");
  });

  test("HCPCS exact code match (id match)", () => {
    const results = rankResults(ALL_FIXTURES, "J0135");
    // Both hcpcs and cms_asp have id "J0135" — both should be tier 0
    const tier0 = results.filter((r) => r.id.toLowerCase() === "j0135");
    expect(tier0.length).toBeGreaterThanOrEqual(1);
    expect(tier0[0].id).toBe("J0135");
  });

  test("ICD-10 code exact id match", () => {
    const results = rankResults(ALL_FIXTURES, "Z87.891");
    expect(results[0].id).toBe("Z87.891");
  });

  test("SAM GUID exact match", () => {
    const results = rankResults(ALL_FIXTURES, "SAM-GUID-00001");
    expect(results[0].dataset).toBe("sam_exclusions");
    expect(results[0].id).toBe("SAM-GUID-00001");
  });
});

// ── Tier 1: display prefix match ─────────────────────────────────────────────

describe("search relevance regression — Tier 1: display prefix match", () => {
  test("'Dr. Jane' prefix match on prescriber display", () => {
    const results = rankResults(ALL_FIXTURES, "Dr. Jane");
    expect(results[0].dataset).toBe("nppes");
    expect(results[0].display).toContain("Jane");
  });

  test("'Sunrise' prefix match on pharmacy display", () => {
    const results = rankResults(ALL_FIXTURES, "Sunrise");
    expect(results[0].dataset).toBe("ncpdp");
  });

  test("'Personal history' prefix match on ICD-10 display", () => {
    const results = rankResults(ALL_FIXTURES, "Personal history");
    expect(results[0].id).toBe("Z87.891");
  });
});

// ── Tier 2: display substring match ─────────────────────────────────────────

describe("search relevance regression — Tier 2: display substring match", () => {
  test("'lipitor' substring match → fda_ndc drug ranks first", () => {
    const results = rankResults(
      [FIXTURE_DRUG, FIXTURE_PRESCRIBER, FIXTURE_SAM],
      "lipitor",
    );
    expect(results[0].dataset).toBe("fda_ndc");
    expect(results[0].display).toContain("Lipitor");
  });

  test("'adalimumab' substring match → hcpcs ranks first (or cms_asp — both are tier 2)", () => {
    const results = rankResults(ALL_FIXTURES, "adalimumab");
    // Both hcpcs J0135 and cms_asp J0135 display contains "Adalimumab"
    const top = results[0];
    expect(["hcpcs", "cms_asp"]).toContain(top.dataset);
    expect(top.display.toLowerCase()).toContain("adalimumab");
  });

  test("'metformin' substring match → cms_nadac drug ranks top among subset", () => {
    const results = rankResults([FIXTURE_NADAC, FIXTURE_PRESCRIBER, FIXTURE_OIG], "metformin");
    expect(results[0].dataset).toBe("cms_nadac");
  });

  test("'anderson' substring match on prescriber secondary", () => {
    // DEA fixture has "Anderson Thomas MD" in display — substring match
    const results = rankResults([FIXTURE_DEA, FIXTURE_PHARMACY, FIXTURE_SAM], "anderson");
    expect(results[0].dataset).toBe("dea_registrations");
  });
});

// ── Tier 3: secondary field match ────────────────────────────────────────────

describe("search relevance regression — Tier 3: secondary field match", () => {
  test("'internal medicine' secondary match on prescriber", () => {
    const results = rankResults(
      [FIXTURE_PRESCRIBER, FIXTURE_PHARMACY, FIXTURE_SAM],
      "internal medicine",
    );
    expect(results[0].dataset).toBe("nppes");
  });

  test("'ineligible' secondary match on SAM exclusion", () => {
    const results = rankResults(
      [FIXTURE_SAM, FIXTURE_PHARMACY, FIXTURE_DRUG],
      "ineligible",
    );
    expect(results[0].dataset).toBe("sam_exclusions");
  });

  test("'atorvastatin calcium' secondary match on fda_ndc", () => {
    const results = rankResults(
      [FIXTURE_DRUG, FIXTURE_PRESCRIBER, FIXTURE_ICD10],
      "atorvastatin calcium",
    );
    // "atorvastatin calcium" is the secondary field of FIXTURE_DRUG
    // It's also in the display, so it could be tier 2 or tier 3
    expect(results[0].dataset).toBe("fda_ndc");
  });

  test("'2026Q1' secondary match on cms_asp", () => {
    const results = rankResults([FIXTURE_CMS_ASP, FIXTURE_PRESCRIBER, FIXTURE_PHARMACY], "2026Q1");
    expect(results[0].dataset).toBe("cms_asp");
  });
});

// ── NDC prefix match (plan spec §9.4) ────────────────────────────────────────

describe("search relevance regression — NDC prefix match", () => {
  test("NDC prefix match (first 8 digits) → fda_ndc scores top", () => {
    const results = rankResults([FIXTURE_DRUG, FIXTURE_PRESCRIBER], "00071015");
    // "00071015" is a prefix of "00071015523" — id starts with query → tier 0
    expect(results[0].dataset).toBe("fda_ndc");
  });

  test("NDC prefix match (first 5 digits) → fda_ndc scores top", () => {
    const results = rankResults([FIXTURE_DRUG, FIXTURE_NADAC, FIXTURE_PRESCRIBER], "00071");
    // "00071" is a prefix of "00071015523" — id starts with query → tier 0
    expect(results[0].id).toBe("00071015523");
  });
});

// ── Cross-dataset ranking with full fixture set ───────────────────────────────

describe("search relevance regression — cross-dataset full fixture ranking", () => {
  test("empty query returns all results unchanged", () => {
    const results = rankResults(ALL_FIXTURES, "");
    expect(results).toHaveLength(ALL_FIXTURES.length);
    expect(results[0]).toBe(ALL_FIXTURES[0]);
  });

  test("ranking does not mutate input", () => {
    const copy = [...ALL_FIXTURES];
    rankResults(ALL_FIXTURES, "lipitor");
    expect(ALL_FIXTURES).toEqual(copy);
  });

  test("all fixture records survive ranking (no records lost)", () => {
    const results = rankResults(ALL_FIXTURES, "something");
    expect(results).toHaveLength(ALL_FIXTURES.length);
  });

  test("multiple ID-matching records all appear in tier 0", () => {
    // Both hcpcs and cms_asp have id "J0135"
    const results = rankResults(ALL_FIXTURES, "J0135");
    const tier0Ids = results
      .filter((r) => r.id.toLowerCase() === "j0135")
      .map((r) => r.dataset);
    expect(tier0Ids).toContain("hcpcs");
    expect(tier0Ids).toContain("cms_asp");
    // Both must appear before any tier-1+ results
    const tier0Indices = results
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => r.id.toLowerCase() === "j0135")
      .map(({ i }) => i);
    const firstNonTier0Index = results.findIndex(
      (r) => r.id.toLowerCase() !== "j0135",
    );
    if (firstNonTier0Index !== -1) {
      expect(Math.max(...tier0Indices)).toBeLessThan(firstNonTier0Index);
    }
  });
});
