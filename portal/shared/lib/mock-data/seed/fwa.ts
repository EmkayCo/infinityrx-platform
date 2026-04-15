import { rngInt, rngPick, money, isoDate, isoDateTime, makeUUID, PRIMARY_TENANT } from "./prng";
import type {
  FWAFlag,
  Investigation,
  RecoveryRecord,
  GTNSummary,
  GTNTrendPoint,
  LeakageFlag,
  LeakageCategory,
  PharmacyRiskScore,
} from "@shared/types/reclaimrx";

const FLAG_DESCRIPTIONS = [
  "Excessive billing frequency",
  "Out-of-state pharmacy",
  "Phantom prescriber",
  "Quantity overflow",
  "Refill too soon",
  "Compound abuse",
  "Pharmacy network outlier",
  "Identity theft suspicion",
  "DME fraud pattern",
  "Duplicate claim submission",
  "Kickback arrangement suspected",
  "Opioid prescription anomaly",
] as const;

const ENTITY_NAMES_PHARMACY = [
  "QuickScript Pharmacy",
  "BestRx Express",
  "AllDay Drugs Inc",
  "Rapid Fill Pharmacy",
  "MedEase Dispensary",
  "PharmaPlus Outlet",
  "CompoundCare Rx",
  "NetworkEdge Pharmacy",
];

const ENTITY_NAMES_PRESCRIBER = [
  "Dr. James Wilson",
  "Dr. Karen O'Brien",
  "Dr. Michael Chang",
  "Dr. Sandra Liu",
  "Dr. Robert Torres",
  "Dr. Angela Davis",
  "Dr. Thomas Nguyen",
  "Dr. Patricia Moore",
];

const ENTITY_NAMES_MEMBER = [
  "M*** J*** (MBR-2026-0042)",
  "R*** S*** (MBR-2026-0118)",
  "D*** T*** (MBR-2026-0207)",
  "J*** H*** (MBR-2026-0334)",
  "C*** W*** (MBR-2026-0451)",
  "L*** G*** (MBR-2026-0503)",
];

const SEVERITIES: FWAFlag["severity"][] = ["high", "high", "medium", "medium", "medium", "low"];
const ENTITY_TYPES: FWAFlag["entity_type"][] = ["pharmacy", "pharmacy", "prescriber", "member"];
const FLAG_TYPES: FWAFlag["flag_type"][] = [
  "billing_anomaly",
  "prescribing_pattern",
  "network_leakage",
  "duplicate_claim",
  "identity_theft",
  "dme_fraud",
  "kickback",
  "other",
];

const INVESTIGATOR_NAMES = [
  "Priya Nair",
  "James Okafor",
  "Elena Vasquez",
  "Thomas Becker",
  "Michelle Park",
  "David Santos",
];

export const FWA_FLAGS: FWAFlag[] = Array.from({ length: 50 }, (_, i) => {
  const entityType = ENTITY_TYPES[i % ENTITY_TYPES.length];
  const entityNames =
    entityType === "pharmacy"
      ? ENTITY_NAMES_PHARMACY
      : entityType === "prescriber"
        ? ENTITY_NAMES_PRESCRIBER
        : ENTITY_NAMES_MEMBER;
  const severity = SEVERITIES[i % SEVERITIES.length];

  return {
    id: makeUUID(10000 + i),
    tenant_id: PRIMARY_TENANT,
    flag_type: FLAG_TYPES[i % FLAG_TYPES.length],
    severity,
    entity_type: entityType,
    entity_id: makeUUID(11000 + i),
    entity_name: entityNames[i % entityNames.length],
    estimated_recovery: money(
      severity === "high"
        ? rngInt(50000, 500000)
        : severity === "medium"
          ? rngInt(5000, 50000)
          : rngInt(500, 5000)
    ),
    anomaly_narrative: `${FLAG_DESCRIPTIONS[i % FLAG_DESCRIPTIONS.length]}: statistical analysis identified unusual pattern deviating ${rngInt(2, 8)} standard deviations from peer benchmark. Flagged for immediate review.`,
    detected_at: isoDate(-(i * 2)),
    claim_count: rngInt(3, 250),
    investigation_id: i < 25 ? makeUUID(12000 + i) : undefined,
  };
});

const INV_STATUSES: Investigation["status"][] = [
  ...Array(8).fill("new"),
  ...Array(6).fill("assigned"),
  ...Array(5).fill("evidence"),
  ...Array(4).fill("demand"),
  ...Array(2).fill("resolved"),
];

export const INVESTIGATIONS: Investigation[] = Array.from({ length: 25 }, (_, i) => {
  const flag = FWA_FLAGS[i % FWA_FLAGS.length];
  const status = INV_STATUSES[i];
  const daysOpen = rngInt(1, 90);
  const assignedTo = status !== "new" ? makeUUID(13000 + (i % 6)) : undefined;
  const assignedName = status !== "new" ? INVESTIGATOR_NAMES[i % INVESTIGATOR_NAMES.length] : undefined;

  return {
    id: makeUUID(12000 + i),
    tenant_id: PRIMARY_TENANT,
    flag_id: flag.id,
    flag,
    status,
    assigned_to: assignedTo,
    assigned_to_name: assignedName,
    days_open: daysOpen,
    estimated_recovery: flag.estimated_recovery,
    demanded_amount:
      status === "demand" || status === "resolved"
        ? money(Number(flag.estimated_recovery) * 0.85)
        : undefined,
    collected_amount:
      status === "resolved" ? money(Number(flag.estimated_recovery) * 0.72) : undefined,
    demand_letter:
      status === "demand" || status === "resolved"
        ? "Demand letter issued per 42 CFR §1001. Entity has 30 days to respond or remit payment."
        : undefined,
    corrective_action_plan:
      status === "resolved" ? "CAP accepted. Monthly monitoring for 12 months." : undefined,
    evidence_items: [
      {
        id: makeUUID(14000 + i),
        label: "Claim transaction data",
        description: "Pull all claims within 90-day window",
        required: true,
        completed: status !== "new",
        completed_at: status !== "new" ? isoDate(-daysOpen + 5) : undefined,
        completed_by: assignedName,
        file_url: status !== "new" ? "#" : undefined,
      },
      {
        id: makeUUID(14100 + i),
        label: "Provider license verification",
        description: "Verify current license status with state board",
        required: true,
        completed: ["evidence", "demand", "resolved"].includes(status),
        completed_at: ["evidence", "demand", "resolved"].includes(status)
          ? isoDate(-daysOpen + 10)
          : undefined,
        completed_by: assignedName,
        file_url: ["evidence", "demand", "resolved"].includes(status) ? "#" : undefined,
      },
      {
        id: makeUUID(14200 + i),
        label: "On-site inspection report",
        required: false,
        completed: ["demand", "resolved"].includes(status),
        completed_at: ["demand", "resolved"].includes(status) ? isoDate(-daysOpen + 20) : undefined,
        completed_by: assignedName,
        file_url: ["demand", "resolved"].includes(status) ? "#" : undefined,
      },
    ],
    actions: [
      {
        id: makeUUID(15000 + i),
        investigation_id: makeUUID(12000 + i),
        action: "Investigation opened",
        performed_by: "System",
        performed_at: isoDate(-daysOpen),
        notes: "Auto-created from FWA flag detection",
      },
      ...(assignedName
        ? [
            {
              id: makeUUID(15100 + i),
              investigation_id: makeUUID(12000 + i),
              action: "Assigned to investigator",
              performed_by: "Priya Nair",
              performed_at: isoDate(-daysOpen + 2),
              notes: `Assigned to ${assignedName}`,
            },
          ]
        : []),
    ],
    created_at: isoDate(-daysOpen),
    updated_at: isoDate(-rngInt(0, daysOpen)),
  };
});

export const RECOVERY_ROWS: RecoveryRecord[] = Array.from({ length: 20 }, (_, i) => {
  const inv = INVESTIGATIONS[i % INVESTIGATIONS.length];
  const estimated = money(rngInt(5000, 300000));
  const demanded = money(Number(estimated) * rngInt(75, 95) / 100);
  const collected = money(Number(demanded) * rngInt(60, 100) / 100);

  return {
    id: makeUUID(16000 + i),
    investigation_id: inv.id,
    entity_name: inv.flag.entity_name,
    flag_type: inv.flag.flag_type,
    estimated,
    demanded,
    collected,
    delta: money(Number(estimated) - Number(collected)),
    status: inv.status,
    updated_at: isoDate(-(i * 5)),
  };
});

export const FWA_DASHBOARD = {
  new_flags_today: 7,
  new_flags_this_week: 34,
  severity_breakdown: {
    critical: 2,
    high: 12,
    medium: 23,
    low: 13,
  },
  top_flagged_entities: FWA_FLAGS.slice(0, 5).map((f) => ({
    entity_id: f.entity_id,
    entity_name: f.entity_name,
    entity_type: f.entity_type,
    flag_count: rngInt(3, 18),
    estimated_recovery: f.estimated_recovery,
  })),
  trend_90d: Array.from({ length: 90 }, (_, i) => ({
    date: isoDate(-(89 - i)).substring(0, 10),
    count: rngInt(0, 8),
  })),
};

// ─── GTN / Leakage data ────────────────────────────────────────────────────

const PROGRAM_NAMES = [
  "Heliozar Copay Assist",
  "Nuvectra Plus",
  "OmniShield Benefits",
  "Celtrion Support",
  "TheraCure Connect",
  "BioLink Patient Aid",
];

const LEAKAGE_CATEGORIES: LeakageCategory[] = [
  "pharmacy_misuse",
  "accumulator",
  "maximizer",
  "three_forty_b_overlap",
  "alternative_funding",
  "prescriber_anomaly",
  "patient_anomaly",
];

export const GTN_TREND: GTNTrendPoint[] = Array.from({ length: 12 }, (_, i) => {
  const monthIndex = 12 - i;
  const date = new Date("2026-04-01");
  date.setMonth(date.getMonth() - monthIndex + 1);
  const yearMonth = date.toISOString().slice(0, 7);
  // GTN ratio slowly improving month over month: from ~0.74 to ~0.82
  const baseRatio = 0.74 + i * 0.007;
  const noise = (rngInt(-5, 5)) / 1000;
  return {
    month: yearMonth,
    gtn_ratio: (baseRatio + noise).toFixed(4),
    leakage_amount: money(rngInt(180000, 420000)),
  };
});

export const LEAKAGE_FLAGS: LeakageFlag[] = Array.from({ length: 40 }, (_, i) => {
  const category = LEAKAGE_CATEGORIES[i % LEAKAGE_CATEGORIES.length];
  const entityType = i % 3 === 0 ? "prescriber" : i % 5 === 0 ? "patient" : "pharmacy";
  const entityNames =
    entityType === "pharmacy"
      ? ENTITY_NAMES_PHARMACY
      : entityType === "prescriber"
        ? ENTITY_NAMES_PRESCRIBER
        : ENTITY_NAMES_MEMBER;
  const statuses = ["new", "under_investigation", "confirmed", "dismissed"] as const;
  const status = statuses[i % statuses.length];

  return {
    id: makeUUID(20000 + i),
    tenant_id: PRIMARY_TENANT,
    category,
    entity_type: entityType,
    entity_name: entityNames[i % entityNames.length],
    entity_id: makeUUID(21000 + i),
    estimated_leakage: money(rngInt(1200, 85000)),
    status,
    date_flagged: isoDate(-(i * 3)),
    investigation_id: status !== "new" ? makeUUID(12000 + (i % 25)) : undefined,
    program_name: PROGRAM_NAMES[i % PROGRAM_NAMES.length],
  };
});

const PHARMACY_NAMES_RISK = [
  ...ENTITY_NAMES_PHARMACY,
  "ClearPath Pharmacy",
  "ValueMed Dispensary",
  "PrimeCare Rx",
  "QuikDose Pharmacy",
  "HealthHub Drugs",
  "RxDirect Outlet",
  "MedPoint Specialty",
  "ScriptFill Pharmacy",
];

const RISK_FACTORS_POOL = [
  { factor: "claim_volume_anomaly", description: "Claim volume 3.2x peer benchmark" },
  { factor: "rejection_rate", description: "Payer claim rejection rate 28% (peer: 8%)" },
  { factor: "override_frequency", description: "Override code used in 41% of claims" },
  { factor: "fill_frequency", description: "Avg days between fills: 18 (expected: 30)" },
  { factor: "copay_to_cost_ratio", description: "Copay exceeds ingredient cost in 12% of claims" },
  { factor: "investigation_history", description: "2 prior confirmed investigations" },
  { factor: "chain_independent", description: "Independent pharmacy — elevated baseline risk" },
];

export const PHARMACY_RISK_SCORES: PharmacyRiskScore[] = Array.from({ length: 20 }, (_, i) => {
  const baseScore = i < 4 ? rngInt(75, 98) : i < 10 ? rngInt(45, 74) : rngInt(5, 44);
  const riskTier =
    baseScore >= 75 ? "critical" : baseScore >= 50 ? "high" : baseScore >= 25 ? "medium" : "low";
  const factorCount = rngInt(2, 5);
  const selectedFactors = RISK_FACTORS_POOL.slice(0, factorCount).map((f) => ({
    ...f,
    score: rngInt(10, 100),
  }));

  return {
    npi: `108${String(i + 1).padStart(7, "0")}`,
    pharmacy_name: PHARMACY_NAMES_RISK[i % PHARMACY_NAMES_RISK.length],
    ncpdp: `42${String(i + 1).padStart(5, "0")}`,
    chain_code: i % 4 === 0 ? "CVS" : i % 4 === 1 ? "WAL" : i % 4 === 2 ? "RIT" : "IND",
    state: ["TX", "FL", "CA", "NY", "IL", "GA", "OH", "PA"][i % 8],
    risk_score: baseScore,
    risk_tier: riskTier,
    factors: selectedFactors,
    total_claims: rngInt(120, 4200),
    total_copay_paid: money(rngInt(18000, 640000)),
    reversal_rate: (rngInt(2, 30) / 100).toFixed(4),
    active_investigations: i < 4 ? rngInt(1, 3) : 0,
    last_updated: isoDate(-rngInt(0, 14)),
  };
});

export const GTN_SUMMARY: GTNSummary = {
  total_copay_spend: money(14_820_000),
  identified_leakage: money(2_430_000),
  gtn_ratio: "0.8361",
  gtn_ratio_prev: "0.8124",
  active_investigations: INVESTIGATIONS.filter((i) => i.status !== "resolved").length,
  recovered: money(1_090_000),
  recovery_rate: "0.4486",
  leakage_by_category: LEAKAGE_CATEGORIES.map((cat) => ({
    category: cat,
    amount: money(rngInt(80000, 620000)),
    count: rngInt(3, 22),
  })),
  leakage_by_program: PROGRAM_NAMES.map((name) => ({
    program_name: name,
    amount: money(rngInt(120000, 890000)),
  })),
  top_flagged_pharmacies: PHARMACY_RISK_SCORES.slice(0, 5).map((p) => ({
    npi: p.npi,
    pharmacy_name: p.pharmacy_name,
    risk_score: p.risk_score,
    total_leakage: money(rngInt(40000, 380000)),
    active_investigations: p.active_investigations,
  })),
};
