// tests/unit/fixtures-valid.test.ts
// Validates that all fixture JSON files in packages/modules/directories/fixtures/
// parse without error and contain the expected top-level structure.
//
// Pure unit tests — no backend, no BFF, no network required.
// Fixtures are loaded via URL import (Vite/Vitest handles JSON imports natively).
import { describe, test, expect } from "vitest";
import { z } from "zod";

// ── Fixture imports ────────────────────────────────────────────────────────────
// Using JSON imports resolved by Vite. Each import is typed as unknown[] or
// unknown and validated below against its expected schema.

import prescribers from "../../fixtures/prescribers.json";
import pharmacies from "../../fixtures/pharmacies.json";
import drugsFdaNdc from "../../fixtures/drugs-fda-ndc.json";
import drugsFdbMock from "../../fixtures/drugs-fdb-mock.json";
import codesHcpcs from "../../fixtures/codes-hcpcs.json";
import codesIcd10 from "../../fixtures/codes-icd10.json";
import pricingCmsAsp from "../../fixtures/pricing-cms-asp.json";
import pricingCmsNadac from "../../fixtures/pricing-cms-nadac.json";
import exclusionsOfac from "../../fixtures/exclusions-ofac.json";
import exclusionsSam from "../../fixtures/exclusions-sam.json";
import ingestionRuns from "../../fixtures/ingestion-runs.json";
import ingestionSchedules from "../../fixtures/ingestion-schedules.json";

// ── Shared schemas ─────────────────────────────────────────────────────────────

const RunStatusSchema = z.enum(["completed", "failed", "running", "pending"]);

const IngestionRunSchema = z.object({
  id: z.string().uuid(),
  source: z.string().min(1),
  run_type: z.string().min(1),
  status: RunStatusSchema,
  records_processed: z.number().int().nonnegative(),
  records_inserted: z.number().int().nonnegative(),
  records_updated: z.number().int().nonnegative(),
  records_skipped: z.number().int().nonnegative(),
  records_errored: z.number().int().nonnegative(),
  started_at: z.string().min(1),
  completed_at: z.string().nullable(),
  duration_seconds: z.number().int().nonnegative().nullable(),
  error_message: z.string().nullable(),
});

const IngestionScheduleSchema = z.object({
  source: z.string().min(1),
  cron_expression: z.string().nullable(),
  enabled: z.boolean(),
  run_type: z.string().min(1),
});

// ── NPI Luhn validation helper ────────────────────────────────────────────────
// NPI = 10-digit number. Luhn check: prepend "80840" (prefix) to form 15-char string.
// Apply standard Luhn algorithm; valid NPI yields check digit = 0.
function isValidNpi(npi: string): boolean {
  if (!/^\d{10}$/.test(npi)) return false;
  const digits = `80840${npi}`.split("").map(Number);
  let sum = 0;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits[i]!;
    if ((digits.length - 1 - i) % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  return sum % 10 === 0;
}

// ── Prescribers fixture ────────────────────────────────────────────────────────

describe("fixtures/prescribers.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(prescribers)).toBe(true);
    expect(prescribers.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: npi, name_first, name_last, credential", () => {
    for (const p of prescribers as Array<Record<string, unknown>>) {
      expect(typeof p["npi"]).toBe("string");
      expect(typeof p["name_first"]).toBe("string");
      expect(typeof p["name_last"]).toBe("string");
      expect(typeof p["credential"]).toBe("string");
    }
  });

  test("all NPI values pass Luhn check with prefix 80840", () => {
    for (const p of prescribers as Array<Record<string, unknown>>) {
      const npi = p["npi"] as string;
      expect(isValidNpi(npi), `NPI ${npi} failed Luhn check`).toBe(true);
    }
  });

  test("NPI 8084000008 (Jane Smith DO) is present", () => {
    const npis = (prescribers as Array<Record<string, unknown>>).map((p) => p["npi"]);
    expect(npis).toContain("8084000008");
  });

  test("NPI 8084009009 (Thomas Anderson — SAM cross-link) is present", () => {
    const npis = (prescribers as Array<Record<string, unknown>>).map((p) => p["npi"]);
    expect(npis).toContain("8084009009");
  });
});

// ── Pharmacies fixture ─────────────────────────────────────────────────────────

describe("fixtures/pharmacies.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(pharmacies)).toBe(true);
    expect(pharmacies.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: nabp, name, npi", () => {
    for (const p of pharmacies as Array<Record<string, unknown>>) {
      expect(typeof p["nabp"]).toBe("string");
      expect(typeof p["name"]).toBe("string");
      expect(typeof p["npi"]).toBe("string");
    }
  });
});

// ── FDA NDC drugs fixture ──────────────────────────────────────────────────────

describe("fixtures/drugs-fda-ndc.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(drugsFdaNdc)).toBe(true);
    expect(drugsFdaNdc.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: ndc11, brand_name, generic_name", () => {
    for (const d of drugsFdaNdc as Array<Record<string, unknown>>) {
      expect(typeof d["ndc11"]).toBe("string");
      expect(typeof d["brand_name"]).toBe("string");
      expect(typeof d["generic_name"]).toBe("string");
    }
  });

  test("every NDC11 value is exactly 11 digits", () => {
    for (const d of drugsFdaNdc as Array<Record<string, unknown>>) {
      const ndc = d["ndc11"] as string;
      expect(/^\d{11}$/.test(ndc), `NDC11 '${ndc}' is not 11 digits`).toBe(true);
    }
  });

  test("NDC 00071015523 (Atorvastatin/Lipitor) is present", () => {
    const ndcs = (drugsFdaNdc as Array<Record<string, unknown>>).map((d) => d["ndc11"]);
    expect(ndcs).toContain("00071015523");
  });
});

// ── FDB mock drugs fixture ─────────────────────────────────────────────────────

describe("fixtures/drugs-fdb-mock.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(drugsFdbMock)).toBe(true);
    expect(drugsFdbMock.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has _mock=true and b9_blocked=true", () => {
    for (const d of drugsFdbMock as Array<Record<string, unknown>>) {
      expect(d["_mock"]).toBe(true);
      expect(d["b9_blocked"]).toBe(true);
    }
  });
});

// ── HCPCS codes fixture ────────────────────────────────────────────────────────

describe("fixtures/codes-hcpcs.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(codesHcpcs)).toBe(true);
    expect(codesHcpcs.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: code, description", () => {
    for (const c of codesHcpcs as Array<Record<string, unknown>>) {
      expect(typeof c["code"]).toBe("string");
      expect(typeof c["description"]).toBe("string");
    }
  });

  test("HCPCS code J0135 (Adalimumab injection) is present", () => {
    const codes = (codesHcpcs as Array<Record<string, unknown>>).map((c) => c["code"]);
    expect(codes).toContain("J0135");
  });
});

// ── ICD-10 codes fixture ───────────────────────────────────────────────────────

describe("fixtures/codes-icd10.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(codesIcd10)).toBe(true);
    expect(codesIcd10.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: code, description", () => {
    for (const c of codesIcd10 as Array<Record<string, unknown>>) {
      expect(typeof c["code"]).toBe("string");
      expect(typeof c["description"]).toBe("string");
    }
  });

  test("ICD-10 code Z87.891 (Personal history of nicotine dependence) is present", () => {
    const codes = (codesIcd10 as Array<Record<string, unknown>>).map((c) => c["code"]);
    expect(codes).toContain("Z87.891");
  });
});

// ── CMS-ASP pricing fixture ────────────────────────────────────────────────────

describe("fixtures/pricing-cms-asp.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(pricingCmsAsp)).toBe(true);
    expect(pricingCmsAsp.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: hcpcs_code, asp_price, quarter", () => {
    for (const p of pricingCmsAsp as Array<Record<string, unknown>>) {
      expect(typeof p["hcpcs_code"]).toBe("string");
      expect(typeof p["asp_price"]).toBe("string");
      expect(typeof p["quarter"]).toBe("string");
    }
  });
});

// ── CMS NADAC pricing fixture ──────────────────────────────────────────────────

describe("fixtures/pricing-cms-nadac.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(pricingCmsNadac)).toBe(true);
    expect(pricingCmsNadac.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: ndc11, nadac_per_unit, effective_date", () => {
    for (const p of pricingCmsNadac as Array<Record<string, unknown>>) {
      expect(typeof p["ndc11"]).toBe("string");
      expect(typeof p["nadac_per_unit"]).toBe("string");
      expect(typeof p["effective_date"]).toBe("string");
    }
  });
});

// ── OFAC SDN exclusions fixture ────────────────────────────────────────────────

describe("fixtures/exclusions-ofac.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(exclusionsOfac)).toBe(true);
    expect(exclusionsOfac.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: entity_name, program, sdn_type", () => {
    for (const e of exclusionsOfac as Array<Record<string, unknown>>) {
      expect(typeof e["entity_name"]).toBe("string");
      expect(typeof e["program"]).toBe("string");
      expect(typeof e["sdn_type"]).toBe("string");
    }
  });
});

// ── SAM exclusions fixture ─────────────────────────────────────────────────────

describe("fixtures/exclusions-sam.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(exclusionsSam)).toBe(true);
    expect(exclusionsSam.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry has required fields: sam_guid, entity_name, exclusion_type", () => {
    for (const e of exclusionsSam as Array<Record<string, unknown>>) {
      expect(typeof e["sam_guid"]).toBe("string");
      expect(typeof e["entity_name"]).toBe("string");
      expect(typeof e["exclusion_type"]).toBe("string");
    }
  });

  test("SAM-GUID-00001 is present and cross-links to NPI 8084009009", () => {
    const entry = (exclusionsSam as Array<Record<string, unknown>>).find(
      (e) => e["sam_guid"] === "SAM-GUID-00001",
    );
    expect(entry).toBeDefined();
    expect(entry!["entity_npi"]).toBe("8084009009");
  });
});

// ── Ingestion runs fixture ─────────────────────────────────────────────────────

describe("fixtures/ingestion-runs.json", () => {
  test("is an array with at least 1 entry", () => {
    expect(Array.isArray(ingestionRuns)).toBe(true);
    expect(ingestionRuns.length).toBeGreaterThanOrEqual(1);
  });

  test("every entry validates against IngestionRunSchema", () => {
    for (const run of ingestionRuns) {
      const result = IngestionRunSchema.safeParse(run);
      expect(result.success, `Run ${(run as Record<string, unknown>)["id"]} failed schema: ${!result.success ? JSON.stringify(result.error.flatten()) : ""}`).toBe(true);
    }
  });

  test("contains a completed nppes run with run_id aaaaaaaa-0001-0001-0001-000000000001", () => {
    const run = (ingestionRuns as Array<Record<string, unknown>>).find(
      (r) => r["id"] === "aaaaaaaa-0001-0001-0001-000000000001",
    );
    expect(run).toBeDefined();
    expect(run!["source"]).toBe("nppes");
    expect(run!["status"]).toBe("completed");
  });

  test("contains a failed fda_ndc run", () => {
    const run = (ingestionRuns as Array<Record<string, unknown>>).find(
      (r) => r["source"] === "fda_ndc" && r["status"] === "failed",
    );
    expect(run).toBeDefined();
    expect((run!["records_errored"] as number)).toBeGreaterThan(0);
  });

  test("contains a running ncpdp run with null completed_at", () => {
    const run = (ingestionRuns as Array<Record<string, unknown>>).find(
      (r) => r["source"] === "ncpdp" && r["status"] === "running",
    );
    expect(run).toBeDefined();
    expect(run!["completed_at"]).toBeNull();
  });
});

// ── Ingestion schedules fixture ────────────────────────────────────────────────

describe("fixtures/ingestion-schedules.json", () => {
  const EXPECTED_SOURCE_COUNT = 21; // All 21 IngestionSourceKeySchema keys

  test("is an array", () => {
    expect(Array.isArray(ingestionSchedules)).toBe(true);
  });

  test(`contains all ${EXPECTED_SOURCE_COUNT} IngestionSourceKeySchema keys`, () => {
    expect(ingestionSchedules.length).toBe(EXPECTED_SOURCE_COUNT);
  });

  test("every entry validates against IngestionScheduleSchema", () => {
    for (const schedule of ingestionSchedules) {
      const result = IngestionScheduleSchema.safeParse(schedule);
      expect(
        result.success,
        `Schedule for source '${(schedule as Record<string, unknown>)["source"]}' failed schema: ${!result.success ? JSON.stringify(result.error.flatten()) : ""}`,
      ).toBe(true);
    }
  });

  test("nppes schedule is enabled with weekly full cron", () => {
    const s = (ingestionSchedules as Array<Record<string, unknown>>).find(
      (s) => s["source"] === "nppes",
    );
    expect(s).toBeDefined();
    expect(s!["enabled"]).toBe(true);
    expect(s!["run_type"]).toBe("full");
    expect(s!["cron_expression"]).toBe("0 3 * * SUN");
  });

  test("ncpdp schedule is disabled with null cron (manual_only)", () => {
    const s = (ingestionSchedules as Array<Record<string, unknown>>).find(
      (s) => s["source"] === "ncpdp",
    );
    expect(s).toBeDefined();
    expect(s!["enabled"]).toBe(false);
    expect(s!["cron_expression"]).toBeNull();
  });

  test("fdb schedule is disabled with b9_pending run_type", () => {
    const s = (ingestionSchedules as Array<Record<string, unknown>>).find(
      (s) => s["source"] === "fdb",
    );
    expect(s).toBeDefined();
    expect(s!["enabled"]).toBe(false);
    expect(s!["run_type"]).toBe("b9_pending");
  });

  test("source keys are unique (no duplicates)", () => {
    const sources = (ingestionSchedules as Array<Record<string, unknown>>).map(
      (s) => s["source"],
    );
    const unique = new Set(sources);
    expect(unique.size).toBe(sources.length);
  });
});
