import { rngInt, rngPick, money, isoDate, makeUUID, PRIMARY_TENANT } from "./prng";
import type {
  MedicalClaim,
  HCPCSNDCMapping,
  UnifiedDrugSpend,
  ThreeFourtyBSummary,
  SiteOfCareAnalysis,
} from "@shared/types/medical-claims";

const HCPCS_DRUGS = [
  { hcpcs: "J3490", name: "Unclassified Drug", ndc: "00074-9374-02", strength: "40mg/0.8mL" },
  { hcpcs: "J9355", name: "Ado-Trastuzumab Emtansine", ndc: "50242-0087-01", strength: "100mg" },
  { hcpcs: "J0897", name: "Denosumab", ndc: "55513-0710-01", strength: "60mg/mL" },
  { hcpcs: "J0696", name: "Ceftriaxone Sodium", ndc: "00143-9506-10", strength: "1g" },
  { hcpcs: "J1745", name: "Infliximab", ndc: "57894-0030-01", strength: "100mg" },
  { hcpcs: "J1300", name: "Amifostine", ndc: "63323-0271-01", strength: "500mg" },
  { hcpcs: "J9045", name: "Carboplatin", ndc: "00703-4756-11", strength: "50mg/5mL" },
  { hcpcs: "J9190", name: "Fluorouracil", ndc: "00703-5638-11", strength: "500mg/10mL" },
  { hcpcs: "J7030", name: "Normal Saline Solution", ndc: "00264-7800-00", strength: "1000mL" },
  { hcpcs: "J0129", name: "Abatacept", ndc: "00003-2187-10", strength: "250mg" },
  { hcpcs: "J0717", name: "Certolizumab Pegol", ndc: "50474-0710-01", strength: "200mg/mL" },
  { hcpcs: "J0878", name: "Darbepoetin Alfa", ndc: "55513-0148-01", strength: "25mcg/mL" },
  { hcpcs: "J3060", name: "Taliglucerase Alfa", ndc: "99207-0443-11", strength: "200 units" },
  { hcpcs: "J2353", name: "Octreotide Acetate", ndc: "00054-3557-25", strength: "100mcg/mL" },
  { hcpcs: "J0585", name: "OnabotulinumtoxinA", ndc: "00023-1145-01", strength: "100 units" },
] as const;

const PROVIDER_NAMES = [
  "Memorial Cancer Center",
  "Regional Infusion Clinic",
  "Oncology Associates",
  "University Medical Group",
  "Advanced Specialty Care",
  "Riverside Rheumatology",
  "City Neurology Group",
  "Harbor Oncology Practice",
];

const CLAIM_STATUSES: MedicalClaim["status"][] = [
  "approved",
  "approved",
  "approved",
  "approved",
  "pending",
  "pending",
  "denied",
  "adjusted",
  "void",
];

const POS_CODES: MedicalClaim["place_of_service"][] = ["11", "22", "23", "24", "21", "31"];

export const MEDICAL_CLAIMS: MedicalClaim[] = Array.from({ length: 35 }, (_, i) => {
  const drug = HCPCS_DRUGS[i % HCPCS_DRUGS.length];
  const status = CLAIM_STATUSES[i % CLAIM_STATUSES.length];
  const billedAmount = money(rngInt(200, 50000));
  const allowedAmount = money(Number(billedAmount) * rngInt(75, 95) / 100);
  const paidAmount = money(Number(allowedAmount) * rngInt(70, 90) / 100);
  const patientResp = money(Number(allowedAmount) - Number(paidAmount));
  const is340b = i % 5 === 0;

  return {
    id: makeUUID(90000 + i),
    tenant_id: PRIMARY_TENANT,
    claim_number: `MC-2026-${String(10000 + i).padStart(6, "0")}`,
    hcpcs_code: drug.hcpcs,
    hcpcs_description: drug.name,
    ndc: drug.ndc,
    drug_name: drug.name,
    provider_npi: `${String(1900100001 + i)}`.substring(0, 10),
    provider_name: PROVIDER_NAMES[i % PROVIDER_NAMES.length],
    member_id: makeUUID(23000 + (i % 30)),
    masked_member_name: `${["A", "B", "C", "D", "E"][i % 5]}*** ${["S", "J", "R", "D", "C"][i % 5]}***`,
    date_of_service: isoDate(-(i * 3)).substring(0, 10),
    place_of_service: POS_CODES[i % POS_CODES.length],
    billed_amount: billedAmount,
    allowed_amount: allowedAmount,
    paid_amount: status === "approved" || status === "adjusted" ? paidAmount : "0.00",
    patient_responsibility: patientResp,
    status,
    is_340b: is340b,
    units_billed: rngInt(1, 10),
    units_administered: rngInt(1, 10),
    waste_units: rngInt(0, 2),
    waste_amount: money(rngInt(0, 500)),
    asp_unit_price: money(rngInt(100, 5000)),
    asp_total: money(rngInt(100, 15000)),
    hcpcs_ndc_mapping: {
      hcpcs: drug.hcpcs,
      ndc: drug.ndc,
      drug_name: drug.name,
      strength: drug.strength,
      units_per_claim: rngInt(1, 5),
      confidence_score: (rngInt(80, 99)) / 100,
      mapping_source: rngPick(["cms", "manual", "ml"] as const),
      effective_date: isoDate(-90).substring(0, 10),
    },
    created_at: isoDate(-(i * 3) - 1),
    updated_at: isoDate(-(i * 3)),
  };
});

export const HCPCS_CROSSWALK: HCPCSNDCMapping[] = HCPCS_DRUGS.slice(0, 20).map((d, i) => ({
  hcpcs: d.hcpcs,
  ndc: d.ndc,
  drug_name: d.name,
  strength: d.strength,
  units_per_claim: rngInt(1, 5),
  confidence_score: (rngInt(82, 99)) / 100,
  mapping_source: rngPick(["cms", "manual", "ml"] as const),
  effective_date: isoDate(-90).substring(0, 10),
}));

export const UNIFIED_SPEND: UnifiedDrugSpend[] = Array.from({ length: 15 }, (_, i) => {
  const member = makeUUID(23000 + i);
  const drugName = HCPCS_DRUGS[i % HCPCS_DRUGS.length].name;
  const months = ["2026-01", "2026-02", "2026-03"];
  const totalPharmacy = money(rngInt(5000, 80000));
  const totalMedical = money(rngInt(5000, 80000));

  return {
    member_id: member,
    drug_name: drugName,
    ndc: HCPCS_DRUGS[i % HCPCS_DRUGS.length].ndc,
    period_months: months.map((month) => {
      const pharm = money(rngInt(1000, 25000));
      const med = money(rngInt(1000, 25000));
      return {
        month,
        pharmacy_spend: pharm,
        medical_spend: med,
        total_spend: money(Number(pharm) + Number(med)),
      };
    }),
    total_pharmacy: totalPharmacy,
    total_medical: totalMedical,
    total_combined: money(Number(totalPharmacy) + Number(totalMedical)),
  };
});

export const THREESIXTYFOURTY_SUMMARY: ThreeFourtyBSummary = {
  flagged_count: 42,
  entity_match_count: 38,
  total_program_amount: "1842300.00",
  potential_savings: "437850.00",
  recent_claims: MEDICAL_CLAIMS.filter((c) => c.is_340b).slice(0, 5),
};

export const SITE_OF_CARE: SiteOfCareAnalysis[] = [
  { place_of_service: "11", pos_description: "Physician Office", claim_count: 1842, total_billed: "3842100.00", total_paid: "2891200.00", avg_paid: "1569.60" },
  { place_of_service: "22", pos_description: "Outpatient Hospital", claim_count: 923, total_billed: "8423100.00", total_paid: "6140250.00", avg_paid: "6653.03" },
  { place_of_service: "23", pos_description: "Emergency Room", claim_count: 287, total_billed: "1842000.00", total_paid: "1250410.00", avg_paid: "4357.18" },
  { place_of_service: "24", pos_description: "Ambulatory Surgical Center", claim_count: 412, total_billed: "2341500.00", total_paid: "1748200.00", avg_paid: "4243.69" },
  { place_of_service: "21", pos_description: "Inpatient Hospital", claim_count: 134, total_billed: "4823100.00", total_paid: "3541200.00", avg_paid: "26427.61" },
];
