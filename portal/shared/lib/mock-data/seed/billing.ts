import { rngInt, rngPick, money, isoDate, isoDateTime, makeUUID, PRIMARY_TENANT } from "./prng";
import type { BillingCycle, Claim, Invoice, MappingTemplate } from "@shared/types/billing";

const CLIENT_NAMES = [
  "Acme Health Partners",
  "BlueStar Benefits Group",
  "ClearPath Managed Care",
  "Delta Pharmacy Solutions",
  "Emerald Coast PBM",
  "Frontier Health Advisors",
  "GlobalRx Management",
  "Harbor Benefit Consultants",
] as const;

const PROGRAM_NAMES = [
  "Commercial PPO",
  "Medicare Part D",
  "Medicaid Managed Care",
  "Self-Funded Employer",
  "Exchange Plan",
  "Specialty Tier Program",
] as const;

const CYCLE_STATUSES: BillingCycle["status"][] = [
  "completed",
  "completed",
  "completed",
  "completed",
  "approved",
  "pending_approval",
  "pending_approval",
  "generating",
  "validating",
  "draft",
];

const DRUG_NAMES = [
  "Atorvastatin 40mg",
  "Lisinopril 10mg",
  "Metformin 500mg",
  "Levothyroxine 50mcg",
  "Amlodipine 5mg",
  "Omeprazole 20mg",
  "Albuterol 90mcg Inhaler",
  "Gabapentin 300mg",
  "Hydrochlorothiazide 25mg",
  "Sertraline 50mg",
  "Losartan 50mg",
  "Simvastatin 20mg",
  "Furosemide 40mg",
  "Pantoprazole 40mg",
  "Fluoxetine 20mg",
  "Tamsulosin 0.4mg",
  "Trazodone 50mg",
  "Carvedilol 6.25mg",
  "Meloxicam 15mg",
  "Pravastatin 40mg",
  "Bupropion XL 150mg",
  "Citalopram 20mg",
  "Cyclobenzaprine 10mg",
  "Tramadol 50mg",
  "Ibuprofen 600mg",
  "Acetaminophen 500mg",
  "Hydrocodone/APAP 5-325mg",
  "Adderall XR 20mg",
  "Vyvanse 30mg",
  "Humira 40mg/0.8mL Pen",
  "Eliquis 5mg",
  "Xarelto 20mg",
  "Jardiance 10mg",
  "Trulicity 1.5mg/0.5mL",
  "Ozempic 0.5mg/dose",
  "Wegovy 2.4mg/dose",
  "Mounjaro 5mg/dose",
  "Repatha 140mg/mL",
  "Dupixent 300mg/2mL",
  "Stelara 45mg/0.5mL",
] as const;

const NDC_POOL = [
  "00093-7239-56",
  "00071-0222-24",
  "00378-4610-05",
  "00074-4582-11",
  "00069-0260-68",
  "00186-0800-31",
  "59310-0579-22",
  "00071-1015-24",
  "00364-2495-01",
  "00093-7230-56",
  "00054-0129-25",
  "54868-4521-00",
  "00093-0041-01",
  "00071-3035-23",
  "00093-0075-01",
  "00045-0065-30",
  "00093-0039-56",
  "00591-2590-21",
  "00093-5498-56",
  "00378-3410-93",
  "65862-0143-90",
  "00093-0714-56",
  "60505-2636-03",
  "00093-0129-56",
  "00603-5747-58",
  "00904-6338-51",
  "00406-0510-01",
  "57844-0144-30",
  "59148-0011-71",
  "00074-9374-02",
  "00069-4280-30",
  "50458-0579-30",
  "00169-4760-51",
  "00002-1433-80",
  "00169-4700-12",
  "00169-4701-12",
  "00002-7669-80",
  "55513-0730-01",
  "66582-0501-02",
  "57894-0402-01",
];

const PHARMACY_NPIS = [
  "1234567890",
  "2345678901",
  "3456789012",
  "4567890123",
  "5678901234",
  "6789012345",
  "7890123456",
  "8901234567",
  "9012345678",
  "1357924680",
];

const PHARMACY_NAMES = [
  "CVS Pharmacy #1047",
  "Walgreens #3821",
  "Rite Aid #0542",
  "Walmart Pharmacy",
  "Costco Pharmacy",
  "Kroger Pharmacy",
  "Hometown Pharmacy",
  "MedPlus Specialty Rx",
  "Express Scripts Mail",
  "CVS Caremark Mail",
];

const CLAIM_STATUSES: Claim["status"][] = [
  "approved",
  "approved",
  "approved",
  "approved",
  "pending",
  "pending",
  "warning",
  "rejected",
  "flagged",
  "error",
];

export const BILLING_CYCLES: BillingCycle[] = Array.from({ length: 24 }, (_, i) => {
  const clientName = CLIENT_NAMES[i % CLIENT_NAMES.length];
  const programName = PROGRAM_NAMES[i % PROGRAM_NAMES.length];
  const status = CYCLE_STATUSES[i % CYCLE_STATUSES.length];
  const claimCount = rngInt(800, 15000);
  const apAmount = money(rngInt(50000, 18000000));
  const arAmount = money(Number(apAmount) * 0.92);
  const feeAmount = money(Number(apAmount) * 0.04);
  const monthOffset = -(i % 12);
  const cycleMonth = new Date("2026-04-01T00:00:00Z");
  cycleMonth.setMonth(cycleMonth.getMonth() + monthOffset);
  const cyclePeriod = `${cycleMonth.getUTCFullYear()}-${String(cycleMonth.getUTCMonth() + 1).padStart(2, "0")}`;
  const createdAt = isoDate(-(i * 28));
  const approvedAt = status === "completed" || status === "approved" ? isoDate(-(i * 28) + 5) : null;

  return {
    id: makeUUID(1000 + i),
    tenant_id: PRIMARY_TENANT,
    client_id: makeUUID(100 + (i % 8)),
    client_name: clientName,
    program_id: makeUUID(200 + (i % 6)),
    program_name: programName,
    cycle_period: cyclePeriod,
    status,
    total_claims: claimCount,
    total_ap_amount: apAmount,
    total_ar_amount: money(Number(arAmount)),
    total_fee_amount: money(Number(feeAmount)),
    created_at: createdAt,
    updated_at: isoDate(-(i * 28) + 2),
    approved_at: approvedAt,
    approved_by: approvedAt ? "Sarah Chen" : null,
    generated_at: status === "completed" ? isoDate(-(i * 28) + 7) : null,
    artifacts:
      status === "completed"
        ? [
            {
              id: makeUUID(2000 + i),
              type: "835",
              filename: `835_${cyclePeriod}_${clientName.replace(/\s+/g, "_")}.x12`,
              download_url: "#",
              generated_at: isoDate(-(i * 28) + 7),
              transmitted_at: isoDate(-(i * 28) + 8),
              ack_status: "acknowledged",
            },
            {
              id: makeUUID(2100 + i),
              type: "nacha",
              filename: `NACHA_${cyclePeriod}_${clientName.replace(/\s+/g, "_")}.txt`,
              download_url: "#",
              generated_at: isoDate(-(i * 28) + 7),
              transmitted_at: isoDate(-(i * 28) + 9),
              ack_status: "acknowledged",
            },
          ]
        : [],
    comparison:
      i > 0
        ? {
            prev_cycle_period: `${cycleMonth.getUTCFullYear()}-${String(((cycleMonth.getUTCMonth()) % 12) || 12).padStart(2, "0")}`,
            prev_total_claims: claimCount - rngInt(-200, 500),
            prev_total_ap_amount: money(Number(apAmount) * 0.97),
            claims_delta: rngInt(-200, 500),
            claims_delta_pct: money(rngInt(-5, 8)),
            ap_amount_delta: money(rngInt(-50000, 200000)),
            ap_amount_delta_pct: money(rngInt(-3, 12)),
          }
        : undefined,
    anomaly_flags:
      i % 7 === 0
        ? [
            {
              severity: "warning",
              message: "Claim count 8.3% above 3-month rolling average — verify client data submission",
            },
          ]
        : [],
  };
});

export const CLAIMS: Claim[] = Array.from({ length: 50 }, (_, i) => {
  const drugIdx = i % DRUG_NAMES.length;
  const pharmacyIdx = i % PHARMACY_NPIS.length;
  const cycleIdx = i % BILLING_CYCLES.length;
  const status = CLAIM_STATUSES[i % CLAIM_STATUSES.length];
  const ingredientCost = money(rngInt(5, 50000));
  const dispensingFee = money(rngInt(1, 12));
  const copay = money(rngInt(0, 100));
  const planPaid = money(Math.max(0, Number(ingredientCost) + Number(dispensingFee) - Number(copay)));

  return {
    id: makeUUID(3000 + i),
    tenant_id: PRIMARY_TENANT,
    cycle_id: BILLING_CYCLES[cycleIdx].id,
    client_id: BILLING_CYCLES[cycleIdx].client_id,
    client_name: BILLING_CYCLES[cycleIdx].client_name,
    program_id: BILLING_CYCLES[cycleIdx].program_id,
    program_name: BILLING_CYCLES[cycleIdx].program_name,
    pharmacy_npi: PHARMACY_NPIS[pharmacyIdx],
    pharmacy_name: PHARMACY_NAMES[pharmacyIdx],
    member_id: `MBR-2026-${String(1000 + i).padStart(4, "0")}`,
    drug_ndc: NDC_POOL[drugIdx % NDC_POOL.length],
    drug_name: DRUG_NAMES[drugIdx],
    fill_date: isoDate(-(i * 3)).substring(0, 10),
    quantity: String(rngInt(1, 90)),
    days_supply: rngInt(7, 90),
    ingredient_cost: ingredientCost,
    dispensing_fee: dispensingFee,
    copay,
    plan_paid: planPaid,
    status,
    rejection_reason:
      status === "rejected" ? rngPick(["NDC not covered", "Prior auth required", "Member not eligible", "Duplicate claim"]) : null,
    created_at: isoDate(-(i * 3)),
  };
});

const INVOICE_STATUSES: Invoice["status"][] = [
  "paid",
  "paid",
  "paid",
  "sent",
  "sent",
  "generated",
  "generated",
  "overdue",
  "overdue",
  "voided",
];

export const INVOICES: Invoice[] = Array.from({ length: 30 }, (_, i) => {
  const clientIdx = i % CLIENT_NAMES.length;
  const status = INVOICE_STATUSES[i % INVOICE_STATUSES.length];
  const total = money(rngInt(10000, 500000));
  const issuedAt = isoDate(-(i * 10));
  const dueAt = isoDate(-(i * 10) + 30);
  const paidAt = status === "paid" ? isoDate(-(i * 10) + 25) : null;

  return {
    id: makeUUID(4000 + i),
    tenant_id: PRIMARY_TENANT,
    client_id: makeUUID(100 + clientIdx),
    client_name: CLIENT_NAMES[clientIdx],
    cycle_id: BILLING_CYCLES[i % BILLING_CYCLES.length].id,
    invoice_number: `INV-2026-${String(1000 + i).padStart(5, "0")}`,
    status,
    total_amount: total,
    due_date: dueAt.substring(0, 10),
    issued_at: issuedAt,
    paid_at: paidAt,
    pdf_url: status !== "generated" ? "#" : null,
    line_items: [
      {
        id: makeUUID(5000 + i),
        description: "Pharmacy dispensing fees",
        quantity: rngInt(100, 2000),
        unit_price: money(rngInt(1, 12)),
        total: money(rngInt(500, 20000)),
      },
      {
        id: makeUUID(5100 + i),
        description: "Ingredient cost rebate",
        quantity: 1,
        unit_price: total,
        total,
      },
    ],
    timeline: [
      {
        action: "generated",
        actor: "System",
        timestamp: issuedAt,
        notes: null,
      },
      ...(status !== "generated"
        ? [{ action: "sent", actor: "Sarah Chen", timestamp: isoDate(-(i * 10) + 1), notes: "Sent via email" }]
        : []),
      ...(status === "paid"
        ? [{ action: "paid", actor: "Client Portal", timestamp: paidAt!, notes: "ACH received" }]
        : []),
    ],
  };
});

// ── Claims: enriched with full fields for the Claims Explorer ────────────────
export const CLAIMS_ENRICHED = CLAIMS.map((c, i) => ({
  ...c,
  type: i % 8 === 7 ? "Reversal" : "Claim",
  rx_number: `RX-${String(7890000 + i).slice(-7)}`,
  auth_number: `AUTH-${String(20260000 + i).padStart(8, "0")}`,
  fill_number: (i % 5) + 1,
  occ: ["00", "01", "02", "03"][i % 4],
  network: ["IFX-PREFERRED", "IFX-STANDARD", "IFX-SPECIALTY"][i % 3],
  chain_code: ["CVS", "WAG", "RAD", "WMT", "IND"][i % 5],
  statement_account: `SA-${String(1000 + (i % 8)).padStart(4, "0")}`,
  prescriber_id: `PRE-${String(1000000 + i).slice(-7)}`,
  prescriber_name: ["Dr. Sarah Chen", "Dr. Mark Rivera", "Dr. Amy Park", "Dr. James O'Brien"][i % 4],
  patient_name: ["John Smith", "Maria Garcia", "Robert Johnson", "Linda Williams"][i % 4],
  gpi: `${String(20000000 + i * 111).slice(0, 8)}00`,
  therapeutic_class: ["Cardiovascular", "Endocrine", "CNS", "Respiratory", "GI"][i % 5],
  rejection_code: c.status === "rejected" ? ["70", "75", "88", "76"][i % 4] : null,
  date_of_service: c.fill_date,
  sales_tax: "0.00",
  patient_paid: c.copay,
  total_paid: money(Number(c.plan_paid) + Number(c.copay)),
  pos_adjustment: "0.00",
  debit_card_amount: "0.00",
  transaction_fee: money(rngInt(100, 300) / 100),
  incentive_fee: "0.00",
  copay_assistance_amount: c.copay,
  card_bin: "610415",
  card_pcn: "IFX001",
  card_group: BILLING_CYCLES[i % BILLING_CYCLES.length].client_name?.slice(0, 6).replace(/\s/g, "").toUpperCase() ?? "GRPCO",
  remaining_benefit: money(rngInt(0, 5000)),
  enrollment_date: isoDate(-(i * 14 + 365)).substring(0, 10),
  patient: {
    cardholder_id: `CHD-${String(10000 + i).padStart(5, "0")}`,
    first_name: ["John", "Maria", "Robert", "Linda"][i % 4],
    last_name: ["Smith", "Garcia", "Johnson", "Williams"][i % 4],
    dob: `${1960 + (i % 40)}-${String((i % 12) + 1).padStart(2, "0")}-${String((i % 28) + 1).padStart(2, "0")}`,
    sex: i % 3 === 0 ? "F" : "M",
    address: `${100 + i} Main St`,
    city: ["Austin", "Dallas", "Houston", "San Antonio"][i % 4],
    state: "TX",
    zip: `787${String(i % 100).padStart(2, "0")}`,
    phone: `512555${String(1000 + i).slice(-4)}`,
    email: `patient${i}@example.com`,
    mrn: `MRN-${String(100000 + i)}`,
  },
  billing_provider: {
    npi: PHARMACY_NPIS[i % PHARMACY_NPIS.length],
    tax_id: `${String(80 + i % 19)}-${String(1000000 + i).slice(-7)}`,
    name: PHARMACY_NAMES[i % PHARMACY_NAMES.length],
    address: `${200 + i} Commerce Blvd, ${["Austin", "Dallas", "Houston"][i % 3]}, TX`,
    phone: `512444${String(1000 + i).slice(-4)}`,
    fax: `512444${String(2000 + i).slice(-4)}`,
    email: `pharmacy${i % 10}@ifxrx.example`,
  },
  service_provider: {
    npi: PHARMACY_NPIS[(i + 1) % PHARMACY_NPIS.length],
    name: PHARMACY_NAMES[(i + 1) % PHARMACY_NAMES.length],
    address: `${300 + i} Service Blvd, ${["Austin", "Dallas", "Houston"][i % 3]}, TX`,
  },
  other_coverage_code: ["00", "01"][i % 2],
  bin: "610415",
  insurance_type: ["Commercial", "Medicare", "Medicaid", "Self-Pay"][i % 4],
  insured_id: `INS-${String(90000 + i)}`,
  policy_group: `POL-${String(1000 + (i % 12))}`,
  plan_name: BILLING_CYCLES[i % BILLING_CYCLES.length].program_name ?? "Standard PPO",
  group_id: `GRP-${String(4800 + (i % 8))}`,
  place_of_service: "01",
  emergency_indicator: false,
  cpt_code: null,
  diagnosis_codes: ["Z79.899", "E11.9"][i % 2] ? [`Z79.899`, `E11.${i % 10}`] : undefined,
  units: 1,
  investigation_id: i % 17 === 0 ? `INV-2026-${String(i).padStart(4, "0")}` : undefined,
  reversal_chain: i % 8 === 7
    ? [
        { id: makeUUID(7000 + i), type: "original", date: isoDate(-(i * 3 + 5)).substring(0, 10) },
        { id: makeUUID(7100 + i), type: "reversed", date: isoDate(-(i * 3 + 2)).substring(0, 10) },
      ]
    : [],
  attachments: i % 11 === 0
    ? [{ id: makeUUID(8000 + i), name: `claim_${i}_attachment.pdf`, uploaded_at: isoDate(-(i * 3)).substring(0, 10) }]
    : [],
}));

// ── PA Override mock data ─────────────────────────────────────────────────────
const PA_STATUSES = ["pending", "pending", "pending", "approved", "approved", "denied", "expired"] as const;
const DRUG_PAIRS = [
  { name: "Humira 40mg/0.8mL Pen", ndc: "00074-9374-02" },
  { name: "Eliquis 5mg", ndc: "00069-4280-30" },
  { name: "Dupixent 300mg/2mL", ndc: "66582-0501-02" },
  { name: "Stelara 45mg/0.5mL", ndc: "57894-0402-01" },
  { name: "Repatha 140mg/mL", ndc: "55513-0730-01" },
];

export const PA_OVERRIDES = Array.from({ length: 25 }, (_, i) => {
  const drug = DRUG_PAIRS[i % DRUG_PAIRS.length];
  const status = PA_STATUSES[i % PA_STATUSES.length];
  const requestedAt = isoDate(-(i * 2));
  return {
    id: makeUUID(9000 + i),
    claim_id: makeUUID(3000 + i),
    member_id: `MBR-2026-${String(1000 + i).padStart(4, "0")}`,
    drug_name: drug.name,
    drug_ndc: drug.ndc,
    prescriber_npi: `${String(1000000000 + i * 7).slice(0, 10)}`,
    prescriber_name: ["Dr. Sarah Chen", "Dr. Mark Rivera", "Dr. Amy Park", "Dr. James O'Brien"][i % 4],
    diagnosis_code: ["Z79.899", "E11.9", "I10", "M79.3"][i % 4],
    requested_by: ["Sarah Chen", "Mike Lopez", "Priya Nair"][i % 3],
    requested_at: requestedAt,
    status,
    denial_reason: status === "denied" ? "Drug not covered under patient's current benefit plan — patient must complete step therapy first." : undefined,
    approved_at: status === "approved" ? isoDate(-(i * 2) + 1) : undefined,
    approved_by: status === "approved" ? "Sarah Chen" : undefined,
    days_supply: [30, 60, 90][i % 3],
    quantity: [1, 2, 4][i % 3],
    program_name: BILLING_CYCLES[i % BILLING_CYCLES.length].program_name,
  };
});

// ── Journal entries mock data ─────────────────────────────────────────────────
const JE_TYPES = ["AP", "AR", "Transfer", "Fee", "Adjustment"] as const;
const ACCOUNTS_DEBIT = [
  "Accounts Payable — Pharmacy",
  "Accounts Receivable — Client",
  "Revenue — Processing Fees",
  "Clearing Account",
  "Program Liability",
];
const ACCOUNTS_CREDIT = [
  "Cash — Operating",
  "Cash — Pharmacy ACH",
  "Revenue — Transaction Fees",
  "Program Fund",
  "Adjustments",
];
const QB_CLASSES = [
  "Commercial PPO",
  "Medicare Part D",
  "Self-Funded Employer",
  "Specialty Tier",
  "Exchange Plan",
];

export const JOURNAL_ENTRIES = Array.from({ length: 40 }, (_, i) => {
  const type = JE_TYPES[i % JE_TYPES.length];
  const amount = money(rngInt(500, 150000));
  const cycle = BILLING_CYCLES[i % BILLING_CYCLES.length];
  return {
    id: makeUUID(10000 + i),
    date: isoDate(-(i * 7)).substring(0, 10),
    type,
    description: type === "AP"
      ? `Pharmacy dispensing — ${cycle.program_name}`
      : type === "AR"
        ? `Client invoice — ${cycle.client_name}`
        : type === "Fee"
          ? `Processing fee — ${cycle.cycle_period}`
          : type === "Transfer"
            ? `Settlement transfer — ${cycle.cycle_period}`
            : `Adjustment — ${cycle.program_name}`,
    debit_account: ACCOUNTS_DEBIT[i % ACCOUNTS_DEBIT.length],
    credit_account: ACCOUNTS_CREDIT[i % ACCOUNTS_CREDIT.length],
    amount,
    qb_class: QB_CLASSES[i % QB_CLASSES.length],
    cycle_id: cycle.id,
    cycle_period: cycle.cycle_period,
    status: i % 5 === 0 ? "draft" : "posted",
    reference: `JE-2026-${String(1000 + i).padStart(5, "0")}`,
    created_by: ["Sarah Chen", "Mike Lopez", "System"][i % 3],
    created_at: isoDate(-(i * 7)),
  };
});

export const MAPPING_TEMPLATES: MappingTemplate[] = Array.from({ length: 6 }, (_, i) => ({
  id: makeUUID(6000 + i),
  name: `${CLIENT_NAMES[i % CLIENT_NAMES.length]} Standard Mapping`,
  client_id: makeUUID(100 + i),
  mappings: [
    { source_column: "PHARMACY_NPI", target_field: "pharmacy_npi", confidence: 0.98 },
    { source_column: "DRUG_NDC", target_field: "drug_ndc", confidence: 0.97 },
    { source_column: "MEMBER_ID", target_field: "member_id", confidence: 0.95 },
    { source_column: "FILL_DATE", target_field: "fill_date", confidence: 0.99 },
    { source_column: "BILLED_AMOUNT", target_field: "ingredient_cost", confidence: 0.91 },
    { source_column: "COPAY_AMT", target_field: "copay", confidence: 0.93 },
    { source_column: "DAYS_SUPPLY", target_field: "days_supply", confidence: 0.96 },
    { source_column: "QTY_DISP", target_field: "quantity", confidence: 0.94 },
  ],
  created_at: isoDate(-(30 + i * 15)),
}));
