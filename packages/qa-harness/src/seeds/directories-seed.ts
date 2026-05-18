// packages/qa-harness/src/seeds/directories-seed.ts
// QA harness seed helper for the SP-2 directories module.
//
// Exports fixture data and FactoryBindings-compatible seed descriptors
// for use in dev/staging environments. NEVER imported in production builds.
//
// Fixture data mirrors packages/modules/directories/fixtures/ exactly.
// All NPI values are Luhn-valid with prefix 80840.
// No real PHI — all data is synthetic.
//
// Usage: import { DIRECTORIES_SEED_BINDINGS, seedDirectories } from
//   "@infinityrx/qa-harness/seeds/directories";
// Then pass to FactoryBindings.seed callback.

import type { SeedBinding } from "../factory-bindings.js";

// ── Fixture prescribers (10 Luhn-valid NPIs, prefix 80840) ────────────────────

export const SEED_PRESCRIBERS = [
  {
    npi: "8084000008",
    display_name: "Dr. Jane Smith DO",
    primary_specialty: "Internal Medicine",
    dea_status: "active",
    status: "active",
    state: "IL",
    _fixture: true,
  },
  {
    npi: "8084001006",
    display_name: "Dr. Robert Chen MD",
    primary_specialty: "Cardiology",
    dea_status: "active",
    status: "active",
    state: "CA",
    _fixture: true,
  },
  {
    npi: "8084002004",
    display_name: "Dr. Maria Lopez MD",
    primary_specialty: "Oncology",
    dea_status: "active",
    status: "active",
    state: "TX",
    _fixture: true,
  },
  {
    npi: "8084003002",
    display_name: "Dr. David Kim MD",
    primary_specialty: "Psychiatry",
    dea_status: "active",
    status: "active",
    state: "NY",
    _fixture: true,
  },
  {
    npi: "8084004000",
    display_name: "Dr. Sarah Patel MD",
    primary_specialty: "Pediatrics",
    dea_status: "active",
    status: "active",
    state: "FL",
    _fixture: true,
  },
  {
    npi: "8084005007",
    display_name: "Dr. James Nguyen DO",
    primary_specialty: "Family Medicine",
    dea_status: "active",
    status: "active",
    state: "WA",
    _fixture: true,
  },
  {
    npi: "8084006005",
    display_name: "Dr. Emily Torres MD",
    primary_specialty: "Rheumatology",
    dea_status: "active",
    status: "active",
    state: "CO",
    _fixture: true,
  },
  {
    npi: "8084007003",
    display_name: "Dr. William Park MD",
    primary_specialty: "Neurology",
    dea_status: "active",
    status: "active",
    state: "GA",
    _fixture: true,
  },
  {
    npi: "8084008001",
    display_name: "Dr. Ashley Martin MD",
    primary_specialty: "Endocrinology",
    dea_status: "active",
    status: "active",
    state: "OH",
    _fixture: true,
  },
  {
    npi: "8084009009",
    display_name: "Dr. Thomas Anderson MD",
    primary_specialty: "Family Medicine",
    dea_status: "active",
    status: "active",
    state: "MI",
    _note: "NPI also present in exclusions-sam fixture for cross-link E2E test",
    _fixture: true,
  },
] as const;

// ── Fixture pharmacies (NCPDP-shaped) ─────────────────────────────────────────

export const SEED_PHARMACIES = [
  {
    nabp_id: "1234567",
    npi: "9999000001",
    store_name: "Sunrise Community Pharmacy",
    chain_code: "IND",
    city: "Chicago",
    state: "IL",
    zip: "60601",
    status: "active",
    dispensing_class: "retail",
    _fixture: true,
  },
  {
    nabp_id: "1234568",
    npi: "9999000002",
    store_name: "Northside Rx",
    chain_code: "IND",
    city: "Chicago",
    state: "IL",
    zip: "60614",
    status: "active",
    dispensing_class: "retail",
    _fixture: true,
  },
] as const;

// ── Fixture drugs (FDA NDC — key fixture for search E2E) ──────────────────────

export const SEED_DRUGS_FDA_NDC = [
  {
    ndc11: "00071015523",
    brand_name: "Lipitor",
    generic_name: "Atorvastatin Calcium",
    strength: "20 mg",
    dosage_form: "Tablet",
    route: "Oral",
    labeler: "Parke-Davis",
    marketing_status: "prescription",
    source_date: "2026-05-10",
    _fixture: true,
  },
] as const;

// ── Fixture SAM exclusions (cross-link: SAM-GUID-00001 → NPI 8084009009) ─────

export const SEED_EXCLUSIONS_SAM = [
  {
    sam_guid: "SAM-GUID-00001",
    exclusion_type: "INELIGIBLE",
    entity_name: "ABC MEDICAL SUPPLY CO",
    entity_npi: "8084009009",
    exclusion_date: "2023-06-01",
    reinstatement_date: null,
    ctcode: "Z4",
    agency: "HHS-OIG",
    _note: "entity_npi matches fixture prescriber NPI 8084009009 (Thomas Anderson) for cross-link E2E test",
    _fixture: true,
  },
] as const;

// ── Fixture ingestion runs ─────────────────────────────────────────────────────

export const SEED_INGESTION_RUNS = [
  {
    id: "aaaaaaaa-0001-0001-0001-000000000001",
    source: "nppes",
    run_type: "full",
    status: "completed",
    records_processed: 9494438,
    records_inserted: 9494438,
    records_updated: 0,
    records_skipped: 0,
    records_errored: 0,
    started_at: "2026-05-10T03:00:00Z",
    completed_at: "2026-05-10T04:22:11Z",
    duration_seconds: 4931,
    error_message: null,
    _fixture: true,
  },
  {
    id: "aaaaaaaa-0002-0002-0002-000000000002",
    source: "fda_ndc",
    run_type: "full",
    status: "failed",
    records_processed: 142000,
    records_inserted: 0,
    records_updated: 0,
    records_skipped: 0,
    records_errored: 3,
    started_at: "2026-05-16T02:01:00Z",
    completed_at: "2026-05-16T02:03:44Z",
    duration_seconds: 164,
    error_message: "Connection reset by peer on download.fda.gov",
    _fixture: true,
  },
] as const;

// ── FactoryBindings-compatible seed descriptors ────────────────────────────────

/**
 * Seed binding descriptors for FactoryBindings component.
 * Pass as the `bindings` prop; wire `seedDirectories` as the `seed` callback.
 */
export const DIRECTORIES_SEED_BINDINGS: SeedBinding[] = [
  {
    kind: "directories:prescribers",
    label: "Seed 10 fixture prescribers (Luhn-valid NPIs)",
  },
  {
    kind: "directories:pharmacies",
    label: "Seed fixture pharmacies (NCPDP-shaped)",
  },
  {
    kind: "directories:drugs-fda-ndc",
    label: "Seed fixture FDA NDC drugs (incl. Atorvastatin/Lipitor)",
  },
  {
    kind: "directories:exclusions-sam",
    label: "Seed SAM exclusions (incl. cross-link to NPI 8084009009)",
  },
  {
    kind: "directories:ingestion-runs",
    label: "Seed ingestion run history (completed + failed + running)",
  },
  {
    kind: "directories:all",
    label: "Seed all directories fixtures (full suite)",
  },
];

// ── Seed kind type ─────────────────────────────────────────────────────────────

export type DirectoriesSeedKind =
  | "directories:prescribers"
  | "directories:pharmacies"
  | "directories:drugs-fda-ndc"
  | "directories:exclusions-sam"
  | "directories:ingestion-runs"
  | "directories:all";

/**
 * Returns the fixture data array for a given seed kind.
 * The caller is responsible for POSTing/inserting this data into the dev backend.
 *
 * Usage pattern:
 *   const data = getDirectoriesSeedData(kind);
 *   await fetch(`${BACKEND_URL}/api/v1/qa/seed`, {
 *     method: "POST",
 *     body: JSON.stringify({ kind, records: data }),
 *   });
 */
export function getDirectoriesSeedData(kind: DirectoriesSeedKind): readonly object[] {
  switch (kind) {
    case "directories:prescribers":
      return SEED_PRESCRIBERS;
    case "directories:pharmacies":
      return SEED_PHARMACIES;
    case "directories:drugs-fda-ndc":
      return SEED_DRUGS_FDA_NDC;
    case "directories:exclusions-sam":
      return SEED_EXCLUSIONS_SAM;
    case "directories:ingestion-runs":
      return SEED_INGESTION_RUNS;
    case "directories:all":
      return [
        ...SEED_PRESCRIBERS,
        ...SEED_PHARMACIES,
        ...SEED_DRUGS_FDA_NDC,
        ...SEED_EXCLUSIONS_SAM,
        ...SEED_INGESTION_RUNS,
      ];
  }
}

/**
 * FactoryBindings-compatible seed callback.
 * Wires to a QA seed API endpoint (dev/staging only).
 *
 * @param kind - One of DirectoriesSeedKind values
 * @param seedApiUrl - Base URL of the QA seed API (e.g. "http://localhost:8010")
 */
export async function seedDirectories(
  kind: string,
  seedApiUrl: string = "http://localhost:8010",
): Promise<void> {
  if (!isDirectoriesSeedKind(kind)) {
    throw new Error(`Unknown directories seed kind: '${kind}'`);
  }
  const records = getDirectoriesSeedData(kind);
  const resp = await fetch(`${seedApiUrl}/api/v1/qa/seed`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ kind, records }),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Seed request failed (${resp.status}): ${text}`);
  }
}

function isDirectoriesSeedKind(kind: string): kind is DirectoriesSeedKind {
  return [
    "directories:prescribers",
    "directories:pharmacies",
    "directories:drugs-fda-ndc",
    "directories:exclusions-sam",
    "directories:ingestion-runs",
    "directories:all",
  ].includes(kind);
}
