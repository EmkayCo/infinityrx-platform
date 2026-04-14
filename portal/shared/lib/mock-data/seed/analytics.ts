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
