import { rngInt, rngPick, money, isoDate, makeUUID, PRIMARY_TENANT } from "./prng";
import type {
  LiveMetrics,
  DrugTrendPoint,
  GenericBrandBreakdown,
  PharmacyScorecard,
  NetworkAdequacySummary,
  MemberAdherence,
  FinancialMetrics,
  DataQualityScore,
  HighCostMember,
} from "@shared/types/analytics";
import type { ActivityEvent, ServiceHealth } from "@shared/types/common";

// 90-day drug spend trend
export const DRUG_SPEND_TREND: DrugTrendPoint[] = Array.from({ length: 90 }, (_, i) => {
  const spend = rngInt(180000, 480000);
  const brandSpend = rngInt(90000, 280000);
  const genericSpend = spend - brandSpend;
  return {
    date: isoDate(-(89 - i)).substring(0, 10),
    spend: money(spend),
    claim_count: rngInt(800, 3200),
    brand_spend: money(brandSpend),
    generic_spend: money(genericSpend),
  };
});

export const BRAND_GENERIC: GenericBrandBreakdown = {
  brand_spend: "4823451.20",
  generic_spend: "9147230.80",
  brand_pct: 34.5,
  generic_pct: 65.5,
  glp1_spend: "1843210.00",
  biosimilar_spend: "423150.75",
};

export const TOP_BY_SPEND = [
  { ndc: "00169-4700-12", drug_name: "Ozempic 0.5mg", ytd_spend: money(1843210), claim_count: 842, avg_cost: money(2188), rank: 1 },
  { ndc: "00169-4701-12", drug_name: "Wegovy 2.4mg", ytd_spend: money(1521340), claim_count: 487, avg_cost: money(3123), rank: 2 },
  { ndc: "00002-7669-80", drug_name: "Mounjaro 5mg", ytd_spend: money(1342890), claim_count: 398, avg_cost: money(3373), rank: 3 },
  { ndc: "00074-9374-02", drug_name: "Humira 40mg", ytd_spend: money(1187650), claim_count: 312, avg_cost: money(3806), rank: 4 },
  { ndc: "66582-0501-02", drug_name: "Dupixent 300mg", ytd_spend: money(987430), claim_count: 245, avg_cost: money(4030), rank: 5 },
  { ndc: "57894-0402-01", drug_name: "Stelara 45mg", ytd_spend: money(876250), claim_count: 198, avg_cost: money(4425), rank: 6 },
  { ndc: "55513-0730-01", drug_name: "Repatha 140mg", ytd_spend: money(743180), claim_count: 523, avg_cost: money(1421), rank: 7 },
  { ndc: "00069-4280-30", drug_name: "Eliquis 5mg", ytd_spend: money(623450), claim_count: 1842, avg_cost: money(339), rank: 8 },
  { ndc: "50458-0579-30", drug_name: "Xarelto 20mg", ytd_spend: money(542310), claim_count: 1523, avg_cost: money(356), rank: 9 },
  { ndc: "00169-4760-51", drug_name: "Jardiance 10mg", ytd_spend: money(487620), claim_count: 1287, avg_cost: money(379), rank: 10 },
  { ndc: "00002-1433-80", drug_name: "Trulicity 1.5mg", ytd_spend: money(423150), claim_count: 1143, avg_cost: money(370), rank: 11 },
  { ndc: "00093-7239-56", drug_name: "Atorvastatin 40mg", ytd_spend: money(87340), claim_count: 8421, avg_cost: money(10), rank: 12 },
  { ndc: "00378-4610-05", drug_name: "Metformin 500mg", ytd_spend: money(34210), claim_count: 6823, avg_cost: money(5), rank: 13 },
  { ndc: "57844-0144-30", drug_name: "Adderall XR 20mg", ytd_spend: money(189750), claim_count: 642, avg_cost: money(296), rank: 14 },
  { ndc: "59148-0011-71", drug_name: "Vyvanse 30mg", ytd_spend: money(201430), claim_count: 521, avg_cost: money(387), rank: 15 },
];

export const PHARMACY_SCORECARDS: PharmacyScorecard[] = Array.from({ length: 15 }, (_, i) => ({
  pharmacy_id: makeUUID(20000 + i),
  pharmacy_name: [
    "CVS Pharmacy #1047",
    "Walgreens #3821",
    "Rite Aid #0542",
    "Walmart Pharmacy #412",
    "Costco Pharmacy #88",
    "Kroger Pharmacy",
    "Hometown Pharmacy",
    "MedPlus Specialty Rx",
    "Express Scripts Mail",
    "CVS Caremark Mail",
    "OptimRx Specialty",
    "BioPlus Pharmacy",
    "Summit Pharmacy",
    "City Drug Store",
    "Central Rx",
  ][i],
  npi: `${String(8084000001 + i)}`,
  claim_volume: rngInt(500, 12000),
  avg_cost_per_claim: money(rngInt(15, 250)),
  reject_rate: (rngInt(1, 12)) / 100,
  mac_ratio: (rngInt(85, 105)) / 100,
  generic_dispense_rate: (rngInt(72, 95)) / 100,
  network_tier: i < 5 ? "preferred" : i < 12 ? "standard" : "non-preferred",
}));

export const NETWORK_ADEQUACY: NetworkAdequacySummary = {
  total_members: 142500,
  members_within_5mi: 128250,
  members_within_10mi: 138750,
  coverage_pct_5mi: 90.0,
  coverage_pct_10mi: 97.4,
  gap_counties: ["Harney County, OR", "Loving County, TX", "Slope County, ND", "Esmeralda County, NV"],
};

export const MEMBER_ADHERENCE: MemberAdherence[] = [
  {
    drug_class: "Statins",
    pdc_score: 0.84,
    cms_threshold: 0.80,
    member_count: 8421,
    adherent_count: 7075,
    star_rating_impact: "positive",
  },
  {
    drug_class: "RAS Antagonists",
    pdc_score: 0.78,
    cms_threshold: 0.80,
    member_count: 6234,
    adherent_count: 4863,
    star_rating_impact: "negative",
  },
  {
    drug_class: "Diabetes (Oral)",
    pdc_score: 0.82,
    cms_threshold: 0.80,
    member_count: 5187,
    adherent_count: 4254,
    star_rating_impact: "positive",
  },
  {
    drug_class: "Beta Blockers Post-MI",
    pdc_score: 0.91,
    cms_threshold: 0.80,
    member_count: 1842,
    adherent_count: 1676,
    star_rating_impact: "positive",
  },
  {
    drug_class: "COPD",
    pdc_score: 0.71,
    cms_threshold: 0.80,
    member_count: 2341,
    adherent_count: 1662,
    star_rating_impact: "negative",
  },
];

const PMPM_TREND = Array.from({ length: 24 }, (_, i) => {
  const month = new Date("2024-05-01T00:00:00Z");
  month.setMonth(month.getMonth() + i);
  const pmpm = 185 + i * 3 + rngInt(-5, 10);
  const priorYearPmpm = 172 + i * 2.5 + rngInt(-4, 8);
  return {
    month: `${month.getUTCFullYear()}-${String(month.getUTCMonth() + 1).padStart(2, "0")}`,
    pmpm: money(pmpm),
    prior_year_pmpm: money(priorYearPmpm),
  };
});

export const FINANCIAL_METRICS: FinancialMetrics = {
  pmpm: "247.83",
  pmpm_prior_year: "229.44",
  pmpm_change_pct: 8.02,
  cost_driver_breakdown: [
    { category: "Specialty Drugs", amount: "8423150.00", pct_of_total: 38.2 },
    { category: "GLP-1 / Anti-Obesity", amount: "4708440.00", pct_of_total: 21.3 },
    { category: "Brand Retail", amount: "3523100.00", pct_of_total: 16.0 },
    { category: "Generic Retail", amount: "3124500.00", pct_of_total: 14.2 },
    { category: "Mail Order", amount: "1523400.00", pct_of_total: 6.9 },
    { category: "Other", amount: "763200.00", pct_of_total: 3.4 },
  ],
  pmpm_trend: PMPM_TREND,
  spread_analysis: {
    total_billed: "24782300.00",
    total_paid: "22065790.00",
    spread: "2716510.00",
    spread_pct: 10.96,
  },
};

export const DATA_QUALITY: DataQualityScore = {
  overall_score: 87,
  accuracy_score: 91,
  completeness_score: 84,
  timeliness_score: 89,
  consistency_score: 83,
  trend_90d: Array.from({ length: 90 }, (_, i) => ({
    date: isoDate(-(89 - i)).substring(0, 10),
    score: Math.min(100, Math.max(75, 85 + (i % 7) - 3)),
  })),
  component_issues: [
    { component: "Member DOB", issue: "2.3% of records have ambiguous date format", severity: "medium", record_count: 847 },
    { component: "Pharmacy NPI", issue: "0.4% of NPIs fail Luhn check", severity: "high", record_count: 156 },
    { component: "Drug NDC", issue: "1.1% of NDCs not found in reference database", severity: "medium", record_count: 403 },
    { component: "Claim Amount", issue: "0.1% of claims have zero billed amount", severity: "high", record_count: 37 },
  ],
};

export const LIVE_METRICS: LiveMetrics = {
  claims_per_hour: 2847,
  dollars_flowing: "1423891.20",
  flags_per_day: 34,
  claims_per_hour_delta: 127,
  as_of: isoDate(0),
};

export const HIGH_COST_MEMBERS: HighCostMember[] = Array.from({ length: 10 }, (_, i) => ({
  member_id: makeUUID(23000 + i),
  masked_name: `M*** ${["S", "J", "R", "D", "C", "L", "P", "A", "T", "B"][i]}***`,
  ytd_spend: money(rngInt(50000, 800000)),
  primary_condition: rngPick(["Rheumatoid Arthritis", "Crohn's Disease", "Psoriasis", "Obesity", "Type 2 Diabetes", "Atrial Fibrillation"]),
  specialty_drug_count: rngInt(1, 4),
}));

const MODULE_NAMES = [
  "billing", "payments", "reclaimrx", "edi", "reporting",
  "directories", "medical-claims", "analytics", "admin",
];

const SEVERITIES = ["info", "info", "info", "medium", "high", "critical"] as const;

const ACTION_TEMPLATES = [
  { action: "billing_cycle_approved", module: "billing", description: "Billing cycle approved for Acme Health Partners — $2,847,200 AP" },
  { action: "payment_batch_transmitted", module: "payments", description: "NACHA batch #PB-2026-0142 transmitted — 847 payments, $1,423,891.20" },
  { action: "fwa_flag_created", module: "reclaimrx", description: "High-severity FWA flag created for QuickScript Pharmacy" },
  { action: "edi_transaction_rejected", module: "edi", description: "835 file from BlueCross rejected — invalid sender ID" },
  { action: "report_generated", module: "reporting", description: "Monthly Billing Summary report ready for download" },
  { action: "user_role_changed", module: "admin", description: "User role elevated to billing_operator" },
  { action: "investigation_assigned", module: "reclaimrx", description: "Investigation INV-2026-0018 assigned to Priya Nair" },
  { action: "claim_status_updated", module: "billing", description: "47 claims bulk-approved in cycle CYC-2026-0008" },
  { action: "cert_expiry_warning", module: "edi", description: "Aetna trading partner certificate expires in 7 days" },
  { action: "login", module: "admin", description: "Admin user authenticated via TOTP MFA" },
  { action: "phi_access", module: "directories", description: "Member record accessed — audit entry created" },
  { action: "invoice_sent", module: "billing", description: "Invoice INV-2026-01048 sent to BlueStar Benefits Group" },
];

export const ACTIVITY_EVENTS: ActivityEvent[] = Array.from({ length: 30 }, (_, i) => {
  const template = ACTION_TEMPLATES[i % ACTION_TEMPLATES.length];
  const hoursAgo = i * 0.8;
  const ts = new Date(Date.parse("2026-04-14T12:00:00Z") - hoursAgo * 3600000).toISOString();

  return {
    id: makeUUID(50000 + i),
    tenant_id: PRIMARY_TENANT,
    user_id: makeUUID(60000 + (i % 5)),
    user_name: ["Sarah Chen", "Marcus Rivera", "Priya Nair", "James Okafor", "Elena Vasquez"][i % 5],
    module: template.module,
    action: template.action,
    description: template.description,
    severity: SEVERITIES[i % SEVERITIES.length],
    entity_type: template.module,
    entity_id: makeUUID(70000 + i),
    entity_link: `/${template.module}`,
    occurred_at: ts,
    amount: ["billing_cycle_approved", "payment_batch_transmitted"].includes(template.action)
      ? money(rngInt(100000, 3000000))
      : undefined,
  };
});

// ─── Manufacturer analytics seed data (ICP Portal Phase 1B) ──────────────────

// 16 months of claim summary data (Jan 2025 – Apr 2026)
export const CLAIM_SUMMARY_MONTHLY = Array.from({ length: 16 }, (_, i) => {
  const base = new Date("2025-01-01T00:00:00Z");
  base.setUTCMonth(base.getUTCMonth() + i);
  const label = `${base.getUTCFullYear()}-${String(base.getUTCMonth() + 1).padStart(2, "0")}`;
  const netClaims = rngInt(6800, 14200);
  const reversals = rngInt(120, 480);
  const paid = rngInt(5800, 12000);
  const benefitSpend = rngInt(1200000, 3800000);
  const copaySpend = rngInt(480000, 1600000);
  const abandonmentRate = (rngInt(8, 22)) / 100;
  return {
    period: label,
    net_claim_count: netClaims,
    reversals,
    paid_claims: paid,
    new_enrollments: rngInt(280, 950),
    ingredient_cost: money(rngInt(900000, 2800000)),
    sales_tax: money(rngInt(12000, 48000)),
    patient_paid: money(rngInt(80000, 320000)),
    dispensing_fee: money(rngInt(45000, 180000)),
    benefit_spend: money(benefitSpend),
    copay_assistance: money(copaySpend),
    transaction_fee: money(rngInt(24000, 96000)),
    avg_benefit: money(Math.round(benefitSpend / netClaims)),
    abandonment_rate: abandonmentRate,
    total_pharmacies: rngInt(180, 480),
  };
});

// Claim status distribution (stacked bar)
export const CLAIM_STATUS_BY_PERIOD = CLAIM_SUMMARY_MONTHLY.map((m) => ({
  period: m.period,
  paid: m.paid_claims,
  reversed: m.reversals,
  pending: rngInt(80, 320),
  rejected: rngInt(40, 180),
}));

// OCC (Other Coverage Code) distribution
export const CLAIM_OCC_DISTRIBUTION = [
  { occ: "00 – Not Specified", count: rngInt(4200, 9800), pct: 0 },
  { occ: "01 – No Other Coverage", count: rngInt(1200, 3400), pct: 0 },
  { occ: "03 – Medicare Supplement", count: rngInt(480, 1200), pct: 0 },
  { occ: "04 – Medicaid", count: rngInt(280, 840), pct: 0 },
  { occ: "07 – Other Liability", count: rngInt(120, 480), pct: 0 },
  { occ: "08 – Other Health Plan", count: rngInt(80, 320), pct: 0 },
].map((row, _, arr) => {
  const total = arr.reduce((s, r) => s + r.count, 0);
  return { ...row, pct: parseFloat((row.count / total * 100).toFixed(1)) };
});

// Reject codes distribution
export const REJECT_CODES_DISTRIBUTION = [
  { code: "70 – Product/Service Not Covered", count: rngInt(180, 520), pct: 0 },
  { code: "75 – Prior Auth Required", count: rngInt(120, 380), pct: 0 },
  { code: "76 – Plan Limitations Exceeded", count: rngInt(80, 260), pct: 0 },
  { code: "25 – Missing/Invalid Info", count: rngInt(60, 200), pct: 0 },
  { code: "88 – DUR Reject Error", count: rngInt(40, 140), pct: 0 },
  { code: "27 – Unmatched Cardholder ID", count: rngInt(30, 120), pct: 0 },
].map((row, _, arr) => {
  const total = arr.reduce((s, r) => s + r.count, 0);
  return { ...row, pct: parseFloat((row.count / total * 100).toFixed(1)) };
});

// Fill performance by drug and month
const DRUG_NAMES = [
  { name: "Cardavix 10mg", ndc: "12345-0010-30", company: "Apex Biosciences" },
  { name: "Lumivex 25mg", ndc: "12345-0025-30", company: "Apex Biosciences" },
  { name: "Nexovir 100mg", ndc: "67890-0100-28", company: "Stellar Pharma" },
  { name: "Trelova 5mg", ndc: "67890-0005-30", company: "Stellar Pharma" },
  { name: "Renavar 50mg", ndc: "54321-0050-30", company: "Pinnacle Therapeutics" },
];

export const FILL_SUMMARY_MONTHLY = Array.from({ length: 16 }, (_, i) => {
  const base = new Date("2025-01-01T00:00:00Z");
  base.setUTCMonth(base.getUTCMonth() + i);
  const label = `${base.getUTCFullYear()}-${String(base.getUTCMonth() + 1).padStart(2, "0")}`;
  const newFills = rngInt(1200, 3800);
  const refills = rngInt(3200, 8400);
  return {
    period: label,
    total_fills: newFills + refills,
    new_starts: newFills,
    refills,
    avg_fills_per_patient: parseFloat((rngInt(28, 52) / 10).toFixed(1)),
    avg_days_supply: rngInt(28, 34),
  };
});

export const FILL_BY_DRUG = DRUG_NAMES.map((d) => ({
  drug_name: d.name,
  ndc: d.ndc,
  company_name: d.company,
  net_fills: rngInt(1800, 9400),
  new_starts: rngInt(320, 1800),
  refills: rngInt(1200, 7200),
  avg_quantity: parseFloat((rngInt(280, 1200) / 10).toFixed(1)),
  avg_days_supply: rngInt(28, 34),
  total_spend: money(rngInt(480000, 2400000)),
}));

export const FILL_BY_PHARMACY_TYPE = [
  { type: "Retail – Chain", fills: rngInt(18000, 42000), pct: 0 },
  { type: "Retail – Independent", fills: rngInt(4200, 9800), pct: 0 },
  { type: "Mail Order", fills: rngInt(6800, 18000), pct: 0 },
  { type: "Specialty", fills: rngInt(2400, 7200), pct: 0 },
  { type: "340B", fills: rngInt(480, 1800), pct: 0 },
].map((row, _, arr) => {
  const total = arr.reduce((s, r) => s + r.fills, 0);
  return { ...row, pct: parseFloat((row.fills / total * 100).toFixed(1)) };
});

export const FILL_BY_CHAIN = [
  { chain: "InfinityChain Rx", fills: rngInt(8400, 18000) },
  { chain: "CrestMed Pharmacy", fills: rngInt(6200, 14000) },
  { chain: "NovaCare Rx", fills: rngInt(4800, 10400) },
  { chain: "Meridian Drugs", fills: rngInt(3200, 7800) },
  { chain: "Pinnacle Drug", fills: rngInt(2400, 5800) },
  { chain: "SunLife Pharmacy", fills: rngInt(1800, 4200) },
  { chain: "Gateway Rx", fills: rngInt(1200, 3200) },
  { chain: "Apex Pharmacy", fills: rngInt(900, 2400) },
  { chain: "BlueCross Rx", fills: rngInt(640, 1800) },
  { chain: "Unity Pharmacy", fills: rngInt(420, 1200) },
].sort((a, b) => b.fills - a.fills);

export const FILL_DAYS_SUPPLY = [
  { days: "30-day", fills: rngInt(18000, 38000) },
  { days: "60-day", fills: rngInt(4200, 9800) },
  { days: "90-day", fills: rngInt(8400, 18000) },
  { days: "Other", fills: rngInt(240, 840) },
];

export const NBRX_TREND = Array.from({ length: 16 }, (_, i) => {
  const base = new Date("2025-01-01T00:00:00Z");
  base.setUTCMonth(base.getUTCMonth() + i);
  const label = `${base.getUTCFullYear()}-${String(base.getUTCMonth() + 1).padStart(2, "0")}`;
  return { period: label, nbrx: rngInt(280, 980), trx: rngInt(3200, 9800) };
});

// Adherence data
export const ADHERENCE_PDC_HISTOGRAM = Array.from({ length: 10 }, (_, i) => ({
  bucket: `${i * 10}–${(i + 1) * 10}%`,
  patient_count: i < 3 ? rngInt(80, 280)
    : i < 7 ? rngInt(280, 840)
    : rngInt(1200, 3200),
  is_adherent: i >= 8,
}));

export const ADHERENCE_PERSISTENCE_CURVE = [
  { month: 0, pct_with_card: 100, pct_without_card: 100 },
  { month: 1, pct_with_card: 94, pct_without_card: 82 },
  { month: 2, pct_with_card: 90, pct_without_card: 74 },
  { month: 3, pct_with_card: 87, pct_without_card: 68 },
  { month: 4, pct_with_card: 85, pct_without_card: 63 },
  { month: 5, pct_with_card: 83, pct_without_card: 59 },
  { month: 6, pct_with_card: 82, pct_without_card: 56 },
  { month: 7, pct_with_card: 80, pct_without_card: 52 },
  { month: 8, pct_with_card: 79, pct_without_card: 49 },
  { month: 9, pct_with_card: 78, pct_without_card: 47 },
  { month: 10, pct_with_card: 77, pct_without_card: 44 },
  { month: 11, pct_with_card: 76, pct_without_card: 42 },
  { month: 12, pct_with_card: 75, pct_without_card: 40 },
];

// Copay impact comparison (with-card vs without-card cohorts) — the ROI proof chart
export const COPAY_IMPACT_COMPARISON = {
  with_card: {
    cohort_label: "With Copay Card",
    patient_count: 4284,
    avg_pdc: 0.84,
    persistence_6mo: 0.82,
    persistence_12mo: 0.75,
    avg_fills_per_patient: 9.2,
    avg_copay_paid: money(12),
    avg_program_spend_per_patient: money(2840),
    adherent_pct: 0.84,
  },
  without_card: {
    cohort_label: "Without Copay Card",
    patient_count: 1847,
    avg_pdc: 0.62,
    persistence_6mo: 0.56,
    persistence_12mo: 0.40,
    avg_fills_per_patient: 5.4,
    avg_copay_paid: money(148),
    avg_program_spend_per_patient: money(0),
    adherent_pct: 0.62,
  },
  pdc_lift: 0.22,
  persistence_lift_6mo: 0.26,
  persistence_lift_12mo: 0.35,
  incremental_fills: 3.8,
  roi_per_dollar_spent: "4.20",
};

export const ADHERENCE_BY_PHARMACY = [
  { pharmacy_name: "SunLife Specialty Rx", npi: "8084000021", avg_pdc: 0.91, patient_count: 284 },
  { pharmacy_name: "NovaCare Specialty", npi: "8084000022", avg_pdc: 0.88, patient_count: 412 },
  { pharmacy_name: "InfinityChain Rx #12", npi: "8084000023", avg_pdc: 0.86, patient_count: 1240 },
  { pharmacy_name: "Meridian Drugs #04", npi: "8084000024", avg_pdc: 0.84, patient_count: 820 },
  { pharmacy_name: "CrestMed Pharmacy", npi: "8084000025", avg_pdc: 0.82, patient_count: 564 },
  { pharmacy_name: "Gateway Rx #09", npi: "8084000026", avg_pdc: 0.79, patient_count: 390 },
  { pharmacy_name: "Apex Pharmacy #03", npi: "8084000027", avg_pdc: 0.74, patient_count: 218 },
  { pharmacy_name: "BlueCross Rx Center", npi: "8084000028", avg_pdc: 0.69, patient_count: 176 },
  { pharmacy_name: "Unity Pharmacy #07", npi: "8084000029", avg_pdc: 0.64, patient_count: 144 },
  { pharmacy_name: "Discount Drug Mart", npi: "8084000030", avg_pdc: 0.58, patient_count: 98 },
];

export const PATIENT_ADHERENCE_TABLE = Array.from({ length: 30 }, (_, i) => {
  const pdc = (rngInt(40, 97)) / 100;
  return {
    patient_id: `PAT-${String(10000 + i).padStart(6, "0")}`,
    drug_name: rngPick(DRUG_NAMES).name,
    pdc: parseFloat(pdc.toFixed(2)),
    fills: rngInt(3, 12),
    first_fill: isoDate(-(rngInt(90, 365))).slice(0, 10),
    last_fill: isoDate(-(rngInt(0, 30))).slice(0, 10),
    status: pdc >= 0.80 ? "Adherent" : pdc >= 0.50 ? "Non-Adherent" : "Discontinued",
    has_copay_card: rngInt(0, 1) === 1,
  };
});

// State-level geographic data (all 50 states + DC)
const STATE_ABBRS = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC",
];

const STATE_NAMES: Record<string, string> = {
  AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",
  CO:"Colorado",CT:"Connecticut",DE:"Delaware",FL:"Florida",GA:"Georgia",
  HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",
  KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",
  MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",
  MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",
  NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",
  OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",
  SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",
  VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming",
  DC:"District of Columbia",
};

export const STATE_ANALYTICS = STATE_ABBRS.map((abbr) => {
  const claimCount = rngInt(80, 8400);
  const spend = rngInt(40000, 4200000);
  return {
    state_abbr: abbr,
    state_name: STATE_NAMES[abbr] ?? abbr,
    claim_count: claimCount,
    spend: money(spend),
    pharmacy_count: rngInt(4, 280),
    avg_benefit: money(Math.round(spend / claimCount)),
    abandonment_rate: parseFloat((rngInt(8, 22) / 100).toFixed(2)),
  };
});

// Top 20 pharmacies for pharmacy insights bar chart
export const TOP_PHARMACIES_BY_VOLUME = Array.from({ length: 20 }, (_, i) => ({
  pharmacy_name: [
    "InfinityChain Rx #1047",
    "CrestMed Pharmacy #3821",
    "NovaCare Rx #0542",
    "Meridian Drugs #412",
    "Pinnacle Drug Store",
    "SunLife Pharmacy #88",
    "Gateway Rx Corp",
    "Hometown Pharmacy",
    "MedPlus Specialty Rx",
    "ExpressMail Rx",
    "CrestMed Mail",
    "OptimRx Specialty",
    "BioPlus Pharmacy",
    "Summit Pharmacy",
    "City Drug Store",
    "Central Rx",
    "Alliance Drug",
    "Metro Pharmacy",
    "Regional Rx #22",
    "Valley Drug Store",
  ][i],
  npi: `${String(8084000041 + i)}`,
  ncpdp: `${String(4100000 + i)}`,
  state: rngPick(["TX","CA","FL","NY","IL","PA","OH","GA","NC","MI"] as const),
  net_claims: rngInt(480, 6800),
  pct_covered: parseFloat(((rngInt(82, 98)) / 100).toFixed(2)),
  total_spend: money(rngInt(120000, 3200000)),
  avg_benefit: money(rngInt(180, 480)),
  abandonment_rate: parseFloat((rngInt(6, 22) / 100).toFixed(2)),
  risk_score: rngInt(12, 78),
  pharmacy_type: rngPick(["Retail – Chain","Retail – Independent","Mail Order","Specialty"] as const),
})).sort((a, b) => b.net_claims - a.net_claims);

// Pharmacy type distribution for pie chart
export const PHARMACY_TYPE_DISTRIBUTION = [
  { type: "Retail – Chain", count: rngInt(180, 340), claim_share: 0 },
  { type: "Retail – Independent", count: rngInt(80, 160), claim_share: 0 },
  { type: "Mail Order", count: rngInt(12, 28), claim_share: 0 },
  { type: "Specialty", count: rngInt(24, 56), claim_share: 0 },
  { type: "340B", count: rngInt(4, 16), claim_share: 0 },
].map((row, _, arr) => {
  const total = arr.reduce((s, r) => s + r.count, 0);
  return { ...row, claim_share: parseFloat((row.count / total * 100).toFixed(1)) };
});

// Trend analysis — YoY spend comparison
export const TREND_YOY_SPEND = Array.from({ length: 24 }, (_, i) => {
  const base2024 = new Date("2024-05-01T00:00:00Z");
  base2024.setUTCMonth(base2024.getUTCMonth() + (i % 12));
  const label = `${base2024.getUTCFullYear() + Math.floor(i / 12)}-${String(base2024.getUTCMonth() + 1).padStart(2, "0")}`;
  const isCurrentYear = i >= 12;
  const baseSpend = 1200000 + i * 28000;
  return {
    period: label,
    year: isCurrentYear ? 2026 : 2025,
    spend: money(baseSpend + rngInt(-80000, 120000)),
    is_current_year: isCurrentYear,
  };
});

// Trend decomposition waterfall
export const TREND_DECOMPOSITION = {
  period_label: "Q1 2026 vs Q1 2025",
  starting_spend: money(8420000),
  utilization_change: money(640000),
  unit_cost_change: money(380000),
  mix_change: money(-120000),
  ending_spend: money(9320000),
  total_change: money(900000),
  total_change_pct: 10.7,
  components: [
    { label: "Starting Spend (Q1 2025)", value: money(8420000), is_total: true, is_start: true },
    { label: "Utilization Change", value: money(640000), is_positive: true, is_total: false },
    { label: "Unit Cost Change", value: money(380000), is_positive: true, is_total: false },
    { label: "Mix Change", value: money(-120000), is_positive: false, is_total: false },
    { label: "Ending Spend (Q1 2026)", value: money(9320000), is_total: true, is_end: true },
  ],
};

// Top movers tables
export const TREND_TOP_MOVERS_INCREASE = DRUG_NAMES.slice(0, 5).map((d, i) => ({
  drug_name: d.name,
  ndc: d.ndc,
  company_name: d.company,
  prior_spend: money(rngInt(280000, 1200000)),
  current_spend: money(rngInt(480000, 1800000)),
  dollar_change: money(rngInt(80000, 480000)),
  pct_change: parseFloat((rngInt(12, 68)).toFixed(1)),
  driver: rngPick(["Volume increase", "Unit cost increase", "Mix shift", "New NDC added"] as const),
})).sort((a, b) => parseFloat(b.dollar_change) - parseFloat(a.dollar_change));

export const TREND_TOP_MOVERS_DECREASE = DRUG_NAMES.slice(0, 5).map((d, i) => ({
  drug_name: `${d.name} (generic)`,
  ndc: d.ndc.replace("0", "9"),
  company_name: d.company,
  prior_spend: money(rngInt(480000, 1800000)),
  current_spend: money(rngInt(180000, 680000)),
  dollar_change: money(rngInt(-680000, -80000)),
  pct_change: parseFloat((-rngInt(8, 48)).toFixed(1)),
  driver: rngPick(["Generic entry", "Volume decline", "Coverage change", "Program modification"] as const),
})).sort((a, b) => parseFloat(a.dollar_change) - parseFloat(b.dollar_change));

export const SERVICE_HEALTH: ServiceHealth[] = [
  { service: "Core Platform", status: "healthy", latency_ms: 42, last_checked: isoDate(0), error: undefined },
  { service: "Billing", status: "healthy", latency_ms: 78, last_checked: isoDate(0), error: undefined },
  { service: "Payments", status: "healthy", latency_ms: 65, last_checked: isoDate(0), error: undefined },
  { service: "ReclaimRx", status: "healthy", latency_ms: 95, last_checked: isoDate(0), error: undefined },
  { service: "Reporting", status: "degraded", latency_ms: 1840, last_checked: isoDate(0), error: "High query latency on reporting_db replica" },
  { service: "EDI", status: "healthy", latency_ms: 55, last_checked: isoDate(0), error: undefined },
  { service: "Medical Claims", status: "healthy", latency_ms: 88, last_checked: isoDate(0), error: undefined },
  { service: "DataIQ", status: "healthy", latency_ms: 112, last_checked: isoDate(0), error: undefined },
  { service: "Pharmacy Directory", status: "healthy", latency_ms: 38, last_checked: isoDate(0), error: undefined },
  { service: "Prescriber Directory", status: "healthy", latency_ms: 44, last_checked: isoDate(0), error: undefined },
  { service: "Drug Database", status: "healthy", latency_ms: 31, last_checked: isoDate(0), error: undefined },
  { service: "Member Management", status: "healthy", latency_ms: 67, last_checked: isoDate(0), error: undefined },
  { service: "Redis Cache", status: "healthy", latency_ms: 2, last_checked: isoDate(0), error: undefined },
  { service: "RabbitMQ", status: "healthy", latency_ms: 8, last_checked: isoDate(0), error: undefined },
  { service: "PostgreSQL Primary", status: "healthy", latency_ms: 15, last_checked: isoDate(0), error: undefined },
];
