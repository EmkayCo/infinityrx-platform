/**
 * Mock seed data for Programs and Client Management modules.
 * Money values are stored as Decimal-safe strings (never floats).
 */
import { isoDate, makeUUID, money, rngInt, PRIMARY_TENANT } from "./prng";

// ─── Programs ─────────────────────────────────────────────────────────────────

export interface ProgramRow {
  id: string;
  tenant_id: string;
  name: string;
  manufacturer: string;
  manufacturer_id: string;
  drugs: { ndc: string; name: string }[];
  bin: string;
  pcn: string;
  group_code: string;
  status: "active" | "paused" | "ended";
  active_enrollments: number;
  total_claims_ytd: number;
  total_spend_ytd: string;
  gtn_ratio: string;
  budget_annual: string;
  budget_remaining: string;
  budget_spent: string;
  max_benefit_per_patient: string;
  max_fills_per_patient: number;
  effective_date: string;
  term_date: string | null;
  cost_per_fill: string;
  cost_per_patient: string;
  projected_annual: string;
  active_alerts: number;
  created_at: string;
  updated_at: string;
}

export interface EnrollmentRow {
  id: string;
  program_id: string;
  program_name: string;
  member_id: string;
  enrollment_date: string;
  first_fill_date: string | null;
  fills_to_date: number;
  spend_to_date: string;
  status: "active" | "inactive" | "expired";
  source: string;
}

export interface BudgetMonthRow {
  month: string;
  budget: string;
  actual: string;
  program_id: string;
}

export const PROGRAMS: ProgramRow[] = [
  {
    id: makeUUID(70001),
    tenant_id: PRIMARY_TENANT,
    name: "CardioGuard Copay Program",
    manufacturer: "Helix Biopharma",
    manufacturer_id: makeUUID(71001),
    drugs: [
      { ndc: "12345678901", name: "CardioGuard 10mg Tablet" },
      { ndc: "12345678902", name: "CardioGuard 20mg Tablet" },
    ],
    bin: "610014",
    pcn: "IFX01",
    group_code: "CG2026",
    status: "active",
    active_enrollments: 4821,
    total_claims_ytd: 18340,
    total_spend_ytd: money(2_841_500),
    gtn_ratio: "82.40",
    budget_annual: money(5_000_000),
    budget_remaining: money(2_158_500),
    budget_spent: money(2_841_500),
    max_benefit_per_patient: money(6_000),
    max_fills_per_patient: 12,
    effective_date: "2026-01-01",
    term_date: "2026-12-31",
    cost_per_fill: money(154.94),
    cost_per_patient: money(589.19),
    projected_annual: money(4_898_000),
    active_alerts: 3,
    created_at: isoDate(-120),
    updated_at: isoDate(-1),
  },
  {
    id: makeUUID(70002),
    tenant_id: PRIMARY_TENANT,
    name: "NeuroClear Patient Support",
    manufacturer: "Vantage Therapeutics",
    manufacturer_id: makeUUID(71002),
    drugs: [
      { ndc: "98765432101", name: "NeuroClear 50mg Capsule" },
    ],
    bin: "610014",
    pcn: "IFX02",
    group_code: "NC2026",
    status: "active",
    active_enrollments: 2104,
    total_claims_ytd: 7920,
    total_spend_ytd: money(1_584_000),
    gtn_ratio: "78.20",
    budget_annual: money(3_200_000),
    budget_remaining: money(1_616_000),
    budget_spent: money(1_584_000),
    max_benefit_per_patient: money(10_000),
    max_fills_per_patient: 12,
    effective_date: "2026-01-01",
    term_date: "2026-12-31",
    cost_per_fill: money(200.00),
    cost_per_patient: money(753.00),
    projected_annual: money(3_024_000),
    active_alerts: 7,
    created_at: isoDate(-180),
    updated_at: isoDate(-2),
  },
  {
    id: makeUUID(70003),
    tenant_id: PRIMARY_TENANT,
    name: "OncoBridge Savings Card",
    manufacturer: "Meridian Oncology",
    manufacturer_id: makeUUID(71003),
    drugs: [
      { ndc: "55443322101", name: "OncoBridge 100mg Injection" },
      { ndc: "55443322102", name: "OncoBridge 200mg Injection" },
    ],
    bin: "610014",
    pcn: "IFX03",
    group_code: "OB2026",
    status: "active",
    active_enrollments: 892,
    total_claims_ytd: 3120,
    total_spend_ytd: money(4_212_000),
    gtn_ratio: "71.80",
    budget_annual: money(8_000_000),
    budget_remaining: money(3_788_000),
    budget_spent: money(4_212_000),
    max_benefit_per_patient: money(25_000),
    max_fills_per_patient: 12,
    effective_date: "2026-01-01",
    term_date: "2026-12-31",
    cost_per_fill: money(1350.00),
    cost_per_patient: money(4722.00),
    projected_annual: money(7_680_000),
    active_alerts: 12,
    created_at: isoDate(-90),
    updated_at: isoDate(-1),
  },
  {
    id: makeUUID(70004),
    tenant_id: PRIMARY_TENANT,
    name: "GlucoAssist Copay Card",
    manufacturer: "Stellar Endocrinology",
    manufacturer_id: makeUUID(71004),
    drugs: [
      { ndc: "77665544301", name: "GlucoAssist 5mg Tablet" },
      { ndc: "77665544302", name: "GlucoAssist 10mg Tablet" },
      { ndc: "77665544303", name: "GlucoAssist Pen 300units/mL" },
    ],
    bin: "610014",
    pcn: "IFX04",
    group_code: "GA2026",
    status: "active",
    active_enrollments: 6304,
    total_claims_ytd: 24110,
    total_spend_ytd: money(1_927_700),
    gtn_ratio: "86.50",
    budget_annual: money(4_200_000),
    budget_remaining: money(2_272_300),
    budget_spent: money(1_927_700),
    max_benefit_per_patient: money(4_000),
    max_fills_per_patient: 12,
    effective_date: "2026-01-01",
    term_date: "2026-12-31",
    cost_per_fill: money(79.95),
    cost_per_patient: money(305.78),
    projected_annual: money(3_840_000),
    active_alerts: 1,
    created_at: isoDate(-200),
    updated_at: isoDate(-3),
  },
  {
    id: makeUUID(70005),
    tenant_id: PRIMARY_TENANT,
    name: "RheumaFlex Patient Assistance",
    manufacturer: "Cascade Immunology",
    manufacturer_id: makeUUID(71005),
    drugs: [
      { ndc: "44332211501", name: "RheumaFlex 25mg Tablet" },
    ],
    bin: "610014",
    pcn: "IFX05",
    group_code: "RF2026",
    status: "paused",
    active_enrollments: 1240,
    total_claims_ytd: 2810,
    total_spend_ytd: money(673_200),
    gtn_ratio: "74.30",
    budget_annual: money(2_000_000),
    budget_remaining: money(1_326_800),
    budget_spent: money(673_200),
    max_benefit_per_patient: money(5_000),
    max_fills_per_patient: 12,
    effective_date: "2026-01-01",
    term_date: "2026-12-31",
    cost_per_fill: money(239.57),
    cost_per_patient: money(543.00),
    projected_annual: money(1_346_400),
    active_alerts: 0,
    created_at: isoDate(-250),
    updated_at: isoDate(-10),
  },
];

// ─── Program enrollments (synthetic, per program) ─────────────────────────────

const ENROLLMENT_SOURCES = ["ePA", "Hub Intake", "Patient Portal", "Provider Fax", "Phone"];
const ENROLL_STATUSES: EnrollmentRow["status"][] = ["active", "active", "active", "inactive", "expired"];

export const PROGRAM_ENROLLMENTS: EnrollmentRow[] = Array.from({ length: 60 }, (_, i) => {
  const prog = PROGRAMS[i % PROGRAMS.length];
  const daysSinceEnroll = 10 + (i * 7) % 280;
  const hasFills = i % 5 !== 0;
  return {
    id: makeUUID(72000 + i),
    program_id: prog.id,
    program_name: prog.name,
    member_id: `MBR-2026-${String(i + 1).padStart(4, "0")}`,
    enrollment_date: isoDate(-daysSinceEnroll).slice(0, 10),
    first_fill_date: hasFills ? isoDate(-daysSinceEnroll + 3).slice(0, 10) : null,
    fills_to_date: hasFills ? 1 + (i % 11) : 0,
    spend_to_date: money((1 + (i % 11)) * parseFloat(prog.cost_per_fill)),
    status: ENROLL_STATUSES[i % ENROLL_STATUSES.length],
    source: ENROLLMENT_SOURCES[i % ENROLLMENT_SOURCES.length],
  };
});

// ─── Budget vs. actual (monthly, per program) ────────────────────────────────

export const BUDGET_MONTHLY: BudgetMonthRow[] = (() => {
  const months = ["Jan", "Feb", "Mar", "Apr"];
  const rows: BudgetMonthRow[] = [];
  for (const prog of PROGRAMS) {
    const monthlyBudget = parseFloat(prog.budget_annual) / 12;
    const totalSpent = parseFloat(prog.budget_spent);
    const spentPerMonth = totalSpent / months.length;
    months.forEach((m, idx) => {
      rows.push({
        month: m,
        budget: money(monthlyBudget),
        actual: money(spentPerMonth * (0.85 + 0.05 * idx)),
        program_id: prog.id,
      });
    });
  }
  return rows;
})();

// ─── Dashboard KPI summary ────────────────────────────────────────────────────

export const DASHBOARD_KPI = {
  active_programs: PROGRAMS.filter((p) => p.status === "active").length,
  total_claims_ytd: PROGRAMS.reduce((s, p) => s + p.total_claims_ytd, 0),
  total_copay_spend_ytd: money(
    PROGRAMS.reduce((s, p) => s + parseFloat(p.total_spend_ytd), 0)
  ),
  gtn_ratio: "80.84",
  active_investigations: 23,
  pending_payments: 4,
};

// ─── Activity feed events ─────────────────────────────────────────────────────

export interface DashboardActivityEvent {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  entity_type: "program" | "investigation" | "billing_cycle" | "payment_batch" | "claim";
  entity_id: string;
  entity_href: string;
  severity?: "info" | "warning" | "error";
}

export const DASHBOARD_ACTIVITY: DashboardActivityEvent[] = [
  {
    id: makeUUID(73001),
    type: "investigation_opened",
    title: "New investigation opened",
    description: "OncoBridge: Rx Wellness Pharmacy flagged for accumulator pattern — $12,400 estimated leakage",
    timestamp: isoDate(-0),
    entity_type: "investigation",
    entity_id: makeUUID(40001),
    entity_href: "/reclaimrx/investigations",
    severity: "warning",
  },
  {
    id: makeUUID(73002),
    type: "billing_cycle_completed",
    title: "Billing cycle settled",
    description: "March 2026 billing cycle for CardioGuard — 4,210 claims, $892,400 paid",
    timestamp: isoDate(-1),
    entity_type: "billing_cycle",
    entity_id: makeUUID(20001),
    entity_href: "/accounting/cycles",
    severity: "info",
  },
  {
    id: makeUUID(73003),
    type: "payment_batch_transmitted",
    title: "ACH batch transmitted",
    description: "Batch #2026-0412 — 127 pharmacies, $328,900 transmitted",
    timestamp: isoDate(-1),
    entity_type: "payment_batch",
    entity_id: makeUUID(30001),
    entity_href: "/accounting/payments",
    severity: "info",
  },
  {
    id: makeUUID(73004),
    type: "claim_flagged",
    title: "High-value claim flagged",
    description: "GlucoAssist: Claim CLM-2026-8841 flagged — patient benefit near annual cap",
    timestamp: isoDate(-2),
    entity_type: "claim",
    entity_id: "CLM-2026-8841",
    entity_href: "/claims",
    severity: "warning",
  },
  {
    id: makeUUID(73005),
    type: "investigation_resolved",
    title: "Investigation closed",
    description: "NeuroClear: INV-2026-0094 closed — $8,200 recovered from Alliance RX",
    timestamp: isoDate(-2),
    entity_type: "investigation",
    entity_id: makeUUID(40002),
    entity_href: "/reclaimrx/investigations",
    severity: "info",
  },
  {
    id: makeUUID(73006),
    type: "program_enrollment_spike",
    title: "Enrollment spike detected",
    description: "GlucoAssist: 148 new enrollments in last 24 hours — 4× typical daily rate",
    timestamp: isoDate(-2),
    entity_type: "program",
    entity_id: makeUUID(70004),
    entity_href: `/programs/${makeUUID(70004)}`,
    severity: "warning",
  },
  {
    id: makeUUID(73007),
    type: "payment_batch_transmitted",
    title: "Check run completed",
    description: "Batch #2026-0411 — 8 special handling pharmacies, $42,100 checks printed",
    timestamp: isoDate(-3),
    entity_type: "payment_batch",
    entity_id: makeUUID(30002),
    entity_href: "/accounting/payments",
    severity: "info",
  },
  {
    id: makeUUID(73008),
    type: "claim_flagged",
    title: "Duplicate claim detected",
    description: "OncoBridge: CLM-2026-8203 — possible duplicate with CLM-2026-8198 (same Rx, same date)",
    timestamp: isoDate(-3),
    entity_type: "claim",
    entity_id: "CLM-2026-8203",
    entity_href: "/claims",
    severity: "error",
  },
];

// ─── Dashboard alerts (items requiring operator attention) ─────────────────────

export interface DashboardAlert {
  id: string;
  type: "billing_cycle" | "investigation" | "payment_batch" | "program";
  title: string;
  description: string;
  href: string;
  severity: "info" | "warning" | "error";
  created_at: string;
}

export const DASHBOARD_ALERTS: DashboardAlert[] = [
  {
    id: makeUUID(74001),
    type: "billing_cycle",
    title: "April 1–14 billing cycle awaiting approval",
    description: "29,840 claims, $4.2M pending — requires manager sign-off",
    href: "/accounting/cycles",
    severity: "warning",
    created_at: isoDate(-1),
  },
  {
    id: makeUUID(74002),
    type: "payment_batch",
    title: "3 ACH batches pending transmission",
    description: "$1.1M total — ACH cutoff in 4 hours",
    href: "/accounting/payments",
    severity: "error",
    created_at: isoDate(0),
  },
  {
    id: makeUUID(74003),
    type: "investigation",
    title: "12 investigations unassigned",
    description: "OncoBridge and NeuroClear programs — 5 high severity",
    href: "/reclaimrx/investigations",
    severity: "warning",
    created_at: isoDate(-2),
  },
  {
    id: makeUUID(74004),
    type: "program",
    title: "RheumaFlex program paused — action required",
    description: "Program paused 10 days ago, 1,240 active patients affected",
    href: `/programs/${makeUUID(70005)}`,
    severity: "info",
    created_at: isoDate(-10),
  },
];

// ─── Program health cards (per manufacturer on dashboard) ─────────────────────

export const PROGRAM_HEALTH_CARDS = PROGRAMS.filter((p) => p.status === "active").map((p) => ({
  program_id: p.id,
  program_name: p.name,
  manufacturer: p.manufacturer,
  claims_period: p.total_claims_ytd,
  spend_period: p.total_spend_ytd,
  gtn_percent: p.gtn_ratio,
  active_alerts: p.active_alerts,
  href: `/programs/${p.id}`,
}));

// ─── Client companies ─────────────────────────────────────────────────────────

export interface ClientRow {
  id: string;
  tenant_id: string;
  company_name: string;
  bin: string;
  federal_id: string;
  city: string;
  state: string;
  status: "enabled" | "disabled";
  programs_count: number;
  address_line1: string;
  address_line2?: string;
  zip: string;
  phone: string;
  email: string;
  contact_name: string;
  created_at: string;
  updated_at: string;
}

export interface ClientFeeConfig {
  client_id: string;
  ibl_setup_fee: string;
  icp_setup_fee: string;
  pharmacy_trans_fee: string;
  claim_processing_fee: string;
  pharmacy_disp_fee: string;
  minimum_balance: string;
  opening_balance: string;
  icp_service_fee_monthly: string;
  ibl_service_fee_monthly: string;
  ibl_service_fee_start: string;
  ibl_service_fee_end: string | null;
  updated_at: string;
}

export const CLIENTS: ClientRow[] = [
  {
    id: makeUUID(71001),
    tenant_id: PRIMARY_TENANT,
    company_name: "Helix Biopharma",
    bin: "610014",
    federal_id: "47-1234567",
    city: "San Francisco",
    state: "CA",
    status: "enabled",
    programs_count: 1,
    address_line1: "1 Market Street",
    address_line2: "Suite 800",
    zip: "94105",
    phone: "(415) 555-0100",
    email: "ops@helixbiopharma.com",
    contact_name: "Jennifer Walsh",
    created_at: isoDate(-400),
    updated_at: isoDate(-1),
  },
  {
    id: makeUUID(71002),
    tenant_id: PRIMARY_TENANT,
    company_name: "Vantage Therapeutics",
    bin: "610014",
    federal_id: "82-7654321",
    city: "Boston",
    state: "MA",
    status: "enabled",
    programs_count: 1,
    address_line1: "200 Clarendon Street",
    address_line2: "Floor 15",
    zip: "02116",
    phone: "(617) 555-0200",
    email: "programs@vantagetx.com",
    contact_name: "Daniel Osei",
    created_at: isoDate(-350),
    updated_at: isoDate(-2),
  },
  {
    id: makeUUID(71003),
    tenant_id: PRIMARY_TENANT,
    company_name: "Meridian Oncology",
    bin: "610014",
    federal_id: "91-2345678",
    city: "Houston",
    state: "TX",
    status: "enabled",
    programs_count: 1,
    address_line1: "1000 Main Street",
    zip: "77002",
    phone: "(713) 555-0300",
    email: "copay@meridianoncology.com",
    contact_name: "Sandra Reyes",
    created_at: isoDate(-300),
    updated_at: isoDate(-1),
  },
  {
    id: makeUUID(71004),
    tenant_id: PRIMARY_TENANT,
    company_name: "Stellar Endocrinology",
    bin: "610014",
    federal_id: "35-8901234",
    city: "Chicago",
    state: "IL",
    status: "enabled",
    programs_count: 3,
    address_line1: "233 South Wacker Drive",
    address_line2: "Suite 4500",
    zip: "60606",
    phone: "(312) 555-0400",
    email: "patient-support@stellarendo.com",
    contact_name: "Marcus Webb",
    created_at: isoDate(-500),
    updated_at: isoDate(-3),
  },
  {
    id: makeUUID(71005),
    tenant_id: PRIMARY_TENANT,
    company_name: "Cascade Immunology",
    bin: "610014",
    federal_id: "26-5678901",
    city: "Seattle",
    state: "WA",
    status: "disabled",
    programs_count: 1,
    address_line1: "1301 2nd Avenue",
    zip: "98101",
    phone: "(206) 555-0500",
    email: "programs@cascadeimm.com",
    contact_name: "Amy Tanaka",
    created_at: isoDate(-600),
    updated_at: isoDate(-10),
  },
  {
    id: makeUUID(71006),
    tenant_id: PRIMARY_TENANT,
    company_name: "Apex Rare Disease",
    bin: "610015",
    federal_id: "57-3456789",
    city: "New York",
    state: "NY",
    status: "enabled",
    programs_count: 2,
    address_line1: "767 Fifth Avenue",
    address_line2: "14th Floor",
    zip: "10153",
    phone: "(212) 555-0600",
    email: "copay@apexraredisease.com",
    contact_name: "Patrick Nguyen",
    created_at: isoDate(-250),
    updated_at: isoDate(-5),
  },
];

// ─── Client fee configurations ─────────────────────────────────────────────────

export const CLIENT_FEES: ClientFeeConfig[] = CLIENTS.map((c, i) => ({
  client_id: c.id,
  ibl_setup_fee: money(1500 + i * 250),
  icp_setup_fee: money(2000 + i * 200),
  pharmacy_trans_fee: money(0.35 + i * 0.05),
  claim_processing_fee: money(0.15 + i * 0.02),
  pharmacy_disp_fee: money(1.50 + i * 0.25),
  minimum_balance: money(10000),
  opening_balance: money(50000 + i * 5000),
  icp_service_fee_monthly: money(2500 + i * 250),
  ibl_service_fee_monthly: money(1200 + i * 100),
  ibl_service_fee_start: isoDate(-365).slice(0, 10),
  ibl_service_fee_end: null,
  updated_at: isoDate(-Math.floor(i * 7)),
}));

// ─── Master fee schedule ──────────────────────────────────────────────────────

export interface MasterFeeRow {
  id: string;
  fee_type: string;
  description: string;
  default_rate: string;
  unit: "per_claim" | "per_transaction" | "monthly" | "one_time";
  effective_date: string;
  active: boolean;
}

export const MASTER_FEE_SCHEDULE: MasterFeeRow[] = [
  {
    id: makeUUID(75001),
    fee_type: "ibl_setup",
    description: "IBL (In-House Benefit Liaison) setup fee",
    default_rate: money(1500),
    unit: "one_time",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75002),
    fee_type: "icp_setup",
    description: "ICP (InfinityRx Claims Processor) setup fee",
    default_rate: money(2000),
    unit: "one_time",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75003),
    fee_type: "pharmacy_transaction",
    description: "Pharmacy transaction fee per adjudicated claim",
    default_rate: money(0.35),
    unit: "per_transaction",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75004),
    fee_type: "claim_processing",
    description: "Claim processing fee per paid claim",
    default_rate: money(0.15),
    unit: "per_claim",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75005),
    fee_type: "pharmacy_dispensing",
    description: "Pharmacy dispensing support fee",
    default_rate: money(1.50),
    unit: "per_claim",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75006),
    fee_type: "icp_service_monthly",
    description: "Monthly ICP service fee",
    default_rate: money(2500),
    unit: "monthly",
    effective_date: "2026-01-01",
    active: true,
  },
  {
    id: makeUUID(75007),
    fee_type: "ibl_service_monthly",
    description: "Monthly IBL service fee",
    default_rate: money(1200),
    unit: "monthly",
    effective_date: "2026-01-01",
    active: true,
  },
];

// ─── Client statement providers ───────────────────────────────────────────────

export interface StatementProviderRow {
  id: string;
  client_id: string;
  provider_name: string;
  npi: string;
  ncpdp: string;
  status: "active" | "inactive";
}

export const STATEMENT_PROVIDERS: StatementProviderRow[] = CLIENTS.flatMap((c, ci) =>
  Array.from({ length: 2 + (ci % 3) }, (_, i) => ({
    id: makeUUID(76000 + ci * 10 + i),
    client_id: c.id,
    provider_name: `Provider ${ci * 10 + i + 1} Pharmacy`,
    npi: `${1012345678 + ci * 100 + i}`,
    ncpdp: `${4012345 + ci * 100 + i}`,
    status: (i === 0 ? "active" : i === 1 ? "active" : "inactive") as "active" | "inactive",
  }))
);

// ─── Blocked providers ────────────────────────────────────────────────────────

export interface BlockedProviderRow {
  id: string;
  client_id: string;
  provider_name: string;
  npi: string;
  reason: string;
  blocked_at: string;
}

export const BLOCKED_PROVIDERS: BlockedProviderRow[] = [
  {
    id: makeUUID(77001),
    client_id: makeUUID(71001),
    provider_name: "Apex Discount Pharmacy",
    npi: "1987654321",
    reason: "Confirmed fraud investigation — accumulator scheme",
    blocked_at: isoDate(-45).slice(0, 10),
  },
  {
    id: makeUUID(77002),
    client_id: makeUUID(71003),
    provider_name: "Rx Wellness Center",
    npi: "1876543210",
    reason: "Duplicate claim pattern, unresolved after demand letter",
    blocked_at: isoDate(-30).slice(0, 10),
  },
  {
    id: makeUUID(77003),
    client_id: makeUUID(71004),
    provider_name: "Discount Med Supply",
    npi: "1765432109",
    reason: "340B overlap — not eligible for copay assistance",
    blocked_at: isoDate(-20).slice(0, 10),
  },
];

