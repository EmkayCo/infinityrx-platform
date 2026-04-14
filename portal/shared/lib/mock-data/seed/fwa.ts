import { rngInt, rngPick, money, isoDate, isoDateTime, makeUUID, PRIMARY_TENANT } from "./prng";
import type { FWAFlag, Investigation, RecoveryRecord } from "@shared/types/reclaimrx";

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
