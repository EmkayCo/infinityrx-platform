import { rngInt, rngPick, money, isoDate, makeUUID, PRIMARY_TENANT } from "./prng";
import type { Pharmacy, Prescriber, Drug, Member } from "@shared/types/directories";

// NPI Luhn-valid generator helper (prefix 80840 for pharmacy NPIs)
function makeNPI(index: number): string {
  const base = `80840${String(index).padStart(4, "0")}`;
  // Luhn check digit
  const digits = ("80" + base).split("").map(Number);
  let sum = 0;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits[i];
    if ((digits.length - 1 - i) % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  const check = (10 - (sum % 10)) % 10;
  return base + check;
}

function makePrescriberNPI(index: number): string {
  const base = `19001${String(index).padStart(4, "0")}`;
  const digits = ("80" + base).split("").map(Number);
  let sum = 0;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits[i];
    if ((digits.length - 1 - i) % 2 === 1) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
  }
  const check = (10 - (sum % 10)) % 10;
  return base + check;
}

const PHARMACY_CHAIN_NAMES = [
  "CVS Pharmacy",
  "Walgreens",
  "Rite Aid",
  "Walmart Pharmacy",
  "Costco Pharmacy",
  "Kroger Pharmacy",
  "Hometown Pharmacy",
  "MedPlus Specialty Rx",
  "Express Scripts Mail Order",
  "CVS Caremark Mail Order",
  "OptimRx Specialty",
  "BioPlus Specialty Pharmacy",
];

const CITIES_STATES = [
  { city: "Chicago", state: "IL", zip: "60601" },
  { city: "Houston", state: "TX", zip: "77001" },
  { city: "Phoenix", state: "AZ", zip: "85001" },
  { city: "Philadelphia", state: "PA", zip: "19101" },
  { city: "San Antonio", state: "TX", zip: "78201" },
  { city: "San Diego", state: "CA", zip: "92101" },
  { city: "Dallas", state: "TX", zip: "75201" },
  { city: "San Jose", state: "CA", zip: "95101" },
  { city: "Austin", state: "TX", zip: "78701" },
  { city: "Jacksonville", state: "FL", zip: "32099" },
  { city: "Fort Worth", state: "TX", zip: "76101" },
  { city: "Columbus", state: "OH", zip: "43085" },
  { city: "Charlotte", state: "NC", zip: "28201" },
  { city: "Indianapolis", state: "IN", zip: "46201" },
  { city: "Seattle", state: "WA", zip: "98101" },
  { city: "Denver", state: "CO", zip: "80201" },
  { city: "Nashville", state: "TN", zip: "37201" },
  { city: "Oklahoma City", state: "OK", zip: "73101" },
  { city: "Louisville", state: "KY", zip: "40201" },
  { city: "Portland", state: "OR", zip: "97201" },
];

const PHARMACY_TYPES: Pharmacy["pharmacy_type"][] = [
  "retail",
  "retail",
  "retail",
  "retail",
  "mail_order",
  "specialty",
  "specialty",
  "long_term_care",
  "compound",
  "hospital",
];

const NETWORK_STATUSES: Pharmacy["network_status"][] = [
  "in_network",
  "in_network",
  "in_network",
  "preferred",
  "preferred",
  "pending",
  "terminated",
];

const CREDENTIALING_STATUSES: Pharmacy["credentialing_status"][] = [
  "credentialed",
  "credentialed",
  "credentialed",
  "pending",
  "suspended",
  "expired",
];

export const PHARMACIES: Pharmacy[] = Array.from({ length: 40 }, (_, i) => {
  const loc = CITIES_STATES[i % CITIES_STATES.length];
  const chainName = PHARMACY_CHAIN_NAMES[i % PHARMACY_CHAIN_NAMES.length];
  const number = rngInt(100, 9999);
  const isChain = i < 30;
  const name = isChain ? `${chainName} #${number}` : `${loc.city} Independent Pharmacy`;

  return {
    id: makeUUID(20000 + i),
    tenant_id: PRIMARY_TENANT,
    npi: makeNPI(i + 1),
    name,
    address_line1: `${rngInt(100, 9999)} ${rngPick(["Main", "Oak", "Elm", "Cedar", "Park", "Lake", "River", "Hill"])} ${rngPick(["St", "Ave", "Blvd", "Rd", "Dr"])}`,
    city: loc.city,
    state: loc.state,
    zip: loc.zip,
    phone: `+1${String(rngInt(2000000000, 9999999999))}`,
    fax: `+1${String(rngInt(2000000000, 9999999999))}`,
    pharmacy_type: PHARMACY_TYPES[i % PHARMACY_TYPES.length],
    network_status: NETWORK_STATUSES[i % NETWORK_STATUSES.length],
    credentialing_status: CREDENTIALING_STATUSES[i % CREDENTIALING_STATUSES.length],
    ncpdp_id: String(rngInt(1000000, 9999999)),
    dea_number: `AB${rngInt(1000000, 9999999)}`,
    nabp: String(rngInt(1000000, 9999999)),
    accepts_medicaid: i % 5 !== 0,
    accepts_medicare: i % 4 !== 0,
    hours: "Mon-Fri 8am-8pm, Sat 9am-6pm, Sun 10am-4pm",
    latitude: 30 + rngInt(0, 20) + rngInt(0, 100) / 100,
    longitude: -(80 + rngInt(0, 40) + rngInt(0, 100) / 100),
    created_at: isoDate(-(365 + i * 10)),
    updated_at: isoDate(-(i * 5)),
  };
});

const SPECIALTIES = [
  "Internal Medicine",
  "Family Medicine",
  "Cardiology",
  "Endocrinology",
  "Psychiatry",
  "Oncology",
  "Neurology",
  "Orthopedics",
  "Dermatology",
  "Pediatrics",
] as const;

const FIRST_NAMES = [
  "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda",
  "William", "Barbara", "David", "Susan", "Richard", "Jessica", "Joseph", "Sarah",
  "Thomas", "Karen", "Charles", "Nancy", "Christopher", "Lisa", "Daniel", "Margaret",
  "Matthew", "Betty", "Anthony", "Dorothy", "Mark", "Sandra",
];

const LAST_NAMES = [
  "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
  "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
  "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White",
  "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
];

const DEA_STATUSES: Prescriber["dea_status"][] = [
  "active",
  "active",
  "active",
  "active",
  "active",
  "expired",
  "none",
];

export const PRESCRIBERS: Prescriber[] = Array.from({ length: 40 }, (_, i) => {
  const firstName = FIRST_NAMES[i % FIRST_NAMES.length];
  const lastName = LAST_NAMES[i % LAST_NAMES.length];
  const specialty = SPECIALTIES[i % SPECIALTIES.length];
  const loc = CITIES_STATES[i % CITIES_STATES.length];
  const deaStatus = DEA_STATUSES[i % DEA_STATUSES.length];

  return {
    id: makeUUID(21000 + i),
    tenant_id: PRIMARY_TENANT,
    npi: makePrescriberNPI(i + 1),
    first_name: firstName,
    last_name: lastName,
    full_name: `Dr. ${firstName} ${lastName}`,
    specialty,
    subspecialty: i % 3 === 0 ? `${specialty} — Geriatric` : undefined,
    dea_number: deaStatus === "active" ? `BW${rngInt(1000000, 9999999)}` : undefined,
    dea_status: deaStatus,
    dea_expiry:
      deaStatus === "active"
        ? isoDate(180 + rngInt(0, 365)).substring(0, 10)
        : deaStatus === "expired"
          ? isoDate(-rngInt(10, 180)).substring(0, 10)
          : undefined,
    state_license_number: `${loc.state}${rngInt(10000, 99999)}`,
    state_license_status: i % 10 === 0 ? "expired" : "active",
    state_license_expiry: isoDate(180 + rngInt(0, 365)).substring(0, 10),
    address_line1: `${rngInt(100, 9999)} Medical Center Dr, Suite ${rngInt(100, 999)}`,
    city: loc.city,
    state: loc.state,
    zip: loc.zip,
    phone: `+1${String(rngInt(2000000000, 9999999999))}`,
    credential_alerts:
      deaStatus === "expired"
        ? ["DEA registration expired — controlled substance prescribing suspended"]
        : i % 10 === 0
          ? ["State license renewal pending"]
          : [],
    prescribing_summary: {
      total_claims_90d: rngInt(20, 500),
      top_drugs: [
        { ndc: "00093-7239-56", drug_name: "Atorvastatin 40mg", claim_count: rngInt(5, 80) },
        { ndc: "00071-0222-24", drug_name: "Lisinopril 10mg", claim_count: rngInt(3, 60) },
        { ndc: "00378-4610-05", drug_name: "Metformin 500mg", claim_count: rngInt(2, 40) },
      ],
      avg_days_supply: rngInt(30, 90),
    },
    created_at: isoDate(-(180 + i * 5)),
    updated_at: isoDate(-(i * 7)),
  };
});

const DRUG_LIST = [
  { brand: "Lipitor", generic: "Atorvastatin", strength: "40mg", form: "tablet", class: "Statins", ndc_suffix: "7239-56" },
  { brand: "Zestril", generic: "Lisinopril", strength: "10mg", form: "tablet", class: "ACE Inhibitors", ndc_suffix: "0222-24" },
  { brand: "Glucophage", generic: "Metformin", strength: "500mg", form: "tablet", class: "Biguanides", ndc_suffix: "4610-05" },
  { brand: "Synthroid", generic: "Levothyroxine", strength: "50mcg", form: "tablet", class: "Thyroid Agents", ndc_suffix: "4582-11" },
  { brand: "Norvasc", generic: "Amlodipine", strength: "5mg", form: "tablet", class: "Calcium Channel Blockers", ndc_suffix: "0260-68" },
  { brand: "Prilosec", generic: "Omeprazole", strength: "20mg", form: "capsule", class: "Proton Pump Inhibitors", ndc_suffix: "0800-31" },
  { brand: "ProAir HFA", generic: "Albuterol", strength: "90mcg/actuation", form: "inhaler", class: "Beta-2 Agonists", ndc_suffix: "0579-22" },
  { brand: "Neurontin", generic: "Gabapentin", strength: "300mg", form: "capsule", class: "Anticonvulsants", ndc_suffix: "1015-24" },
  { brand: "Microzide", generic: "Hydrochlorothiazide", strength: "25mg", form: "tablet", class: "Thiazide Diuretics", ndc_suffix: "2495-01" },
  { brand: "Zoloft", generic: "Sertraline", strength: "50mg", form: "tablet", class: "SSRIs", ndc_suffix: "7230-56" },
  { brand: "Cozaar", generic: "Losartan", strength: "50mg", form: "tablet", class: "ARBs", ndc_suffix: "0129-25" },
  { brand: "Zocor", generic: "Simvastatin", strength: "20mg", form: "tablet", class: "Statins", ndc_suffix: "4521-00" },
  { brand: "Lasix", generic: "Furosemide", strength: "40mg", form: "tablet", class: "Loop Diuretics", ndc_suffix: "0041-01" },
  { brand: "Protonix", generic: "Pantoprazole", strength: "40mg", form: "tablet", class: "Proton Pump Inhibitors", ndc_suffix: "3035-23" },
  { brand: "Prozac", generic: "Fluoxetine", strength: "20mg", form: "capsule", class: "SSRIs", ndc_suffix: "0075-01" },
  { brand: "Flomax", generic: "Tamsulosin", strength: "0.4mg", form: "capsule", class: "Alpha Blockers", ndc_suffix: "0065-30" },
  { brand: "Desyrel", generic: "Trazodone", strength: "50mg", form: "tablet", class: "Antidepressants", ndc_suffix: "0039-56" },
  { brand: "Coreg", generic: "Carvedilol", strength: "6.25mg", form: "tablet", class: "Beta Blockers", ndc_suffix: "2590-21" },
  { brand: "Mobic", generic: "Meloxicam", strength: "15mg", form: "tablet", class: "NSAIDs", ndc_suffix: "5498-56" },
  { brand: "Pravachol", generic: "Pravastatin", strength: "40mg", form: "tablet", class: "Statins", ndc_suffix: "3410-93" },
  { brand: "Wellbutrin XL", generic: "Bupropion XL", strength: "150mg", form: "tablet", class: "NDRIs", ndc_suffix: "0143-90" },
  { brand: "Celexa", generic: "Citalopram", strength: "20mg", form: "tablet", class: "SSRIs", ndc_suffix: "0714-56" },
  { brand: "Flexeril", generic: "Cyclobenzaprine", strength: "10mg", form: "tablet", class: "Muscle Relaxants", ndc_suffix: "2636-03" },
  { brand: "Ultram", generic: "Tramadol", strength: "50mg", form: "tablet", class: "Opioids", ndc_suffix: "0129-56" },
  { brand: "Advil", generic: "Ibuprofen", strength: "600mg", form: "tablet", class: "NSAIDs", ndc_suffix: "5747-58" },
  { brand: "Tylenol", generic: "Acetaminophen", strength: "500mg", form: "tablet", class: "Analgesics", ndc_suffix: "6338-51" },
  { brand: "Vicodin", generic: "Hydrocodone/APAP", strength: "5-325mg", form: "tablet", class: "Opioids", ndc_suffix: "0510-01" },
  { brand: "Adderall XR", generic: "Amphetamine/Dextroamphetamine", strength: "20mg", form: "capsule", class: "CNS Stimulants", ndc_suffix: "0144-30" },
  { brand: "Vyvanse", generic: "Lisdexamfetamine", strength: "30mg", form: "capsule", class: "CNS Stimulants", ndc_suffix: "0011-71" },
  { brand: "Humira", generic: "Adalimumab", strength: "40mg/0.8mL", form: "injection", class: "TNF Blockers", ndc_suffix: "9374-02" },
  { brand: "Eliquis", generic: "Apixaban", strength: "5mg", form: "tablet", class: "Anticoagulants", ndc_suffix: "4280-30" },
  { brand: "Xarelto", generic: "Rivaroxaban", strength: "20mg", form: "tablet", class: "Anticoagulants", ndc_suffix: "0579-30" },
  { brand: "Jardiance", generic: "Empagliflozin", strength: "10mg", form: "tablet", class: "SGLT2 Inhibitors", ndc_suffix: "4760-51" },
  { brand: "Trulicity", generic: "Dulaglutide", strength: "1.5mg/0.5mL", form: "injection", class: "GLP-1 Agonists", ndc_suffix: "1433-80" },
  { brand: "Ozempic", generic: "Semaglutide", strength: "0.5mg/dose", form: "injection", class: "GLP-1 Agonists", ndc_suffix: "4700-12" },
  { brand: "Wegovy", generic: "Semaglutide", strength: "2.4mg/dose", form: "injection", class: "GLP-1 Agonists (Anti-Obesity)", ndc_suffix: "4701-12" },
  { brand: "Mounjaro", generic: "Tirzepatide", strength: "5mg/dose", form: "injection", class: "GLP-1/GIP Agonists", ndc_suffix: "7669-80" },
  { brand: "Repatha", generic: "Evolocumab", strength: "140mg/mL", form: "injection", class: "PCSK9 Inhibitors", ndc_suffix: "0730-01" },
  { brand: "Dupixent", generic: "Dupilumab", strength: "300mg/2mL", form: "injection", class: "IL-4/IL-13 Blockers", ndc_suffix: "0501-02" },
  { brand: "Stelara", generic: "Ustekinumab", strength: "45mg/0.5mL", form: "injection", class: "IL-12/23 Blockers", ndc_suffix: "0402-01" },
] as const;

const MANUFACTURERS = [
  "Pfizer Inc", "Merck & Co", "AstraZeneca", "Johnson & Johnson", "Eli Lilly",
  "Bristol-Myers Squibb", "AbbVie Inc", "Amgen Inc", "Novo Nordisk", "Regeneron",
];

export const DRUGS: Drug[] = DRUG_LIST.slice(0, 40).map((d, i) => {
  const ndcPrefix = String(rngInt(10000, 99999)).substring(0, 5);
  const ndc = `${ndcPrefix}-${d.ndc_suffix}`;
  const awp = money(rngInt(10, 5000));
  const wac = money(Number(awp) * 0.85);
  const nadac = money(Number(awp) * 0.15);

  return {
    id: makeUUID(22000 + i),
    tenant_id: PRIMARY_TENANT,
    ndc: ndc.replace(/-/g, "").substring(0, 11).padEnd(11, "0"),
    brand_name: d.brand,
    generic_name: d.generic,
    manufacturer: MANUFACTURERS[i % MANUFACTURERS.length],
    strength: d.strength,
    dosage_form: d.form,
    route: d.form === "injection" ? "Subcutaneous" : d.form === "inhaler" ? "Inhalation" : "Oral",
    therapeutic_class: d.class,
    drug_category: ["Adderall XR", "Vyvanse", "Hydrocodone/APAP", "Tramadol"].includes(d.brand)
      ? "Controlled"
      : "Standard",
    is_generic: !["Humira", "Eliquis", "Xarelto", "Jardiance", "Trulicity", "Ozempic", "Wegovy", "Mounjaro", "Repatha", "Dupixent", "Stelara"].includes(d.brand),
    is_brand: ["Humira", "Eliquis", "Xarelto", "Jardiance", "Trulicity", "Ozempic", "Wegovy", "Mounjaro", "Repatha", "Dupixent", "Stelara"].includes(d.brand),
    is_controlled: ["Adderall XR", "Vyvanse", "Hydrocodone/APAP", "Tramadol"].includes(d.brand),
    schedule: ["Adderall XR", "Vyvanse"].includes(d.brand) ? "II" : ["Hydrocodone/APAP"].includes(d.brand) ? "II" : ["Tramadol"].includes(d.brand) ? "IV" : undefined,
    rems_required: ["Humira", "Dupixent", "Stelara"].includes(d.brand),
    rems_program: ["Humira", "Dupixent", "Stelara"].includes(d.brand) ? `${d.brand} REMS` : undefined,
    current_pricing: {
      awp,
      wac,
      nadac,
      effective_date: isoDate(-30).substring(0, 10),
    },
    pricing_history: [
      {
        awp: money(Number(awp) * 0.95),
        wac: money(Number(wac) * 0.95),
        nadac,
        effective_date: isoDate(-365).substring(0, 10),
        recorded_at: isoDate(-365),
      },
    ],
    interactions:
      i % 5 === 0
        ? [
            {
              interacting_ndc: "00093-7230-56",
              interacting_drug_name: "Sertraline 50mg",
              severity: "moderate",
              description: "Monitor for increased bleeding risk when combined with anticoagulants.",
            },
          ]
        : [],
    therapeutic_equivalents: [],
    updated_at: isoDate(-(i * 14)),
  };
});

const COVERAGE_STATUSES: Member["coverage_status"][] = [
  "active",
  "active",
  "active",
  "active",
  "active",
  "terminated",
  "cobra",
  "suspended",
  "pending",
];

export const MEMBERS: Member[] = Array.from({ length: 30 }, (_, i) => {
  const coverageStatus = COVERAGE_STATUSES[i % COVERAGE_STATUSES.length];
  const deductibleApplied = money(rngInt(0, 1500));
  const oopApplied = money(rngInt(0, 4000));

  return {
    id: makeUUID(23000 + i),
    tenant_id: PRIMARY_TENANT,
    member_id: `MBR-2026-${String(1000 + i).padStart(4, "0")}`,
    full_name: null, // redacted per PHI rules
    masked_name: `${rngPick(["A", "B", "C", "D", "E", "J", "K", "L", "M", "R", "S", "T"])}*** ${rngPick(["B", "C", "D", "G", "H", "J", "K", "L", "M", "N", "P", "R", "S", "T", "W"])}***`,
    date_of_birth: null,
    masked_dob: `${1945 + rngInt(0, 55)}-XX-XX`,
    gender: rngPick(["M", "F", "U"]),
    address: null,
    phone: null,
    email: null,
    coverage_status: coverageStatus,
    coverage_effective_date: isoDate(-(rngInt(90, 730))).substring(0, 10),
    coverage_term_date:
      coverageStatus === "terminated" ? isoDate(-(rngInt(1, 90))).substring(0, 10) : undefined,
    plan_id: makeUUID(24000 + (i % 5)),
    plan_name: rngPick(["Standard PPO", "HMO Gold", "Medicare Advantage", "Medicaid MCO", "High Deductible HSA"]),
    group_id: `GRP-${String(rngInt(1000, 9999))}`,
    accumulator: {
      benefit_year: 2026,
      deductible_applied: deductibleApplied,
      deductible_limit: "3000.00",
      oop_applied: oopApplied,
      oop_limit: "7500.00",
      benefit_phase:
        Number(oopApplied) > 7000
          ? "catastrophic"
          : Number(deductibleApplied) < 3000
            ? "deductible"
            : "initial_coverage",
      troop_applied: money(rngInt(0, 2000)),
      updated_at: isoDate(-rngInt(0, 30)),
    },
    created_at: isoDate(-(365 + i * 10)),
    updated_at: isoDate(-(i * 7)),
  };
});
