#!/usr/bin/env tsx
/**
 * Build script: reads InfinityRx pipe-delimited claims files + xlsx mapping,
 * computes aggregations, writes JSON files to public/data/aggregated/.
 *
 * Usage: npm run prepare-data
 * Expected runtime: <30s on a normal laptop.
 */

import * as fs from "fs";
import * as path from "path";
import ExcelJS from "exceljs";

// ── Path helpers ──────────────────────────────────────────────────────────────
// Raw source files live outside /public so they are not publicly served.
// Aggregated JSON outputs go to /public so the browser mock layer can
// fetch them over HTTP.
const SOURCE_DIR = path.join(process.cwd(), "lib", "data", "sources");
const OUT_DIR = path.join(process.cwd(), "public", "data", "aggregated");

// ── Decimal-safe accumulator ──────────────────────────────────────────────────
// We use integer cent arithmetic to avoid float accumulation errors.
// $1.23 → 123n (cents). Output as fixed-2 string.
function toCents(v: string): bigint {
  if (!v || v === "0.00") return 0n;
  const n = parseFloat(v);
  if (isNaN(n)) return 0n;
  // Round to 2dp then convert to cents
  return BigInt(Math.round(n * 100));
}

function fromCents(cents: bigint): string {
  const neg = cents < 0n;
  const abs = neg ? -cents : cents;
  const dollars = abs / 100n;
  const pennies = abs % 100n;
  return `${neg ? "-" : ""}${dollars}.${String(pennies).padStart(2, "0")}`;
}

// ── Type definitions (inline to avoid cross-file TS issues in tsx) ────────────
interface Claim {
  claim_id: string;
  status: "P" | "R";
  date_of_service: string;
  group_number: string;
  client_name: string;
  cardholder_id: string;
  service_provider_id: string;
  ndc: string;
  quantity: number;
  days_supply: number;
  compound_code: string;
  daw: string;
  total_client_billed: string;
  pharmacy_total_paid: string;
  pharmacy_ingredient_cost_paid: string;
  pharmacy_dispensing_fee_paid: string;
  submitted_ingredient_cost: string;
  submitted_dispensing_fee: string;
  submitted_gross_amount_due: string;
  copay: string;
  patient_pay_amount: string;
  sell_ingredient_cost: string;
  sell_dispensing_fee: string;
  process_date_time: string;
  prescriber_npi: string;
  drug_tier: string;
  brand_generic: string;
  is_preferred: string;
  network_reimbursement_id: string;
  claim_processing_fee: string;
  transaction_fees: string;
  primary_chain_code: string;
  cycle_id: string;
}

// ── Excel reader ──────────────────────────────────────────────────────────────
async function buildGroupMap(): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(path.join(SOURCE_DIR, "client to groupid mappings.xlsx"));
  const ws = wb.worksheets[0];
  ws.eachRow((row, rowIndex) => {
    if (rowIndex === 1) return; // skip header
    const vals = row.values as (string | number | null)[];
    // cols: [null, company_name, group_id, null, NDC, Brand]
    const company = vals[1];
    const groupId = vals[2];
    if (company && groupId) {
      const key = String(groupId).trim();
      const val = String(company).trim();
      if (key) map.set(key, val);
    }
  });
  console.log(`  Group map: ${map.size} entries`);
  return map;
}

// ── Pipe-delimited parser ─────────────────────────────────────────────────────
function parseDate(raw: string): string {
  if (!raw) return "";
  const m = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m) return raw;
  return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
}

function parseDateTime(raw: string): string {
  if (!raw) return "";
  const m = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{2}:\d{2}:\d{2})/);
  if (!m) return raw;
  return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}T${m[4]}`;
}

function money(raw: string): string {
  const v = (raw ?? "").trim();
  if (!v) return "0.00";
  const n = parseFloat(v);
  return isNaN(n) ? "0.00" : n.toFixed(2);
}

function col(cells: string[], idx: number): string {
  if (idx >= cells.length) return "";
  return (cells[idx] ?? "").trim();
}

// Column indices (63-col format; files 2&3 have 53 cols, extras default "")
const C = {
  claim_id: 0, status: 1, bin: 2, pcn: 3,
  dos: 4, date_written: 5, group_number: 6, cardholder_id: 7,
  last_name: 8, first_name: 9,
  service_provider_id: 12, ndc: 13, rx_number: 14,
  quantity: 15, days_supply: 16, compound_code: 17, daw: 18,
  sub_ic: 19, sub_df: 20, sub_gross: 22,
  prescriber_npi: 24, copay: 25, patient_pay: 26,
  pharm_total_paid: 29, pharm_ic_paid: 30, pharm_df_paid: 31,
  sell_ic: 33, sell_df: 34,
  total_billed: 36,
  process_dt: 38,
  drug_tier: 47, brand_generic: 48, is_preferred: 49,
  nrid: 51,
  cpfee: 53, txfee: 54,
  chain: 60,
};

function parseLine(
  line: string,
  groupMap: Map<string, string>,
  cycleId: string
): Claim | null {
  const cells = line.split("|");
  if (cells.length < 40) return null;
  const groupNumber = col(cells, C.group_number);
  const clientName = groupMap.get(groupNumber) ?? groupNumber;
  const statusRaw = col(cells, C.status);
  return {
    claim_id: col(cells, C.claim_id),
    status: statusRaw === "R" ? "R" : "P",
    date_of_service: parseDate(col(cells, C.dos)),
    group_number: groupNumber,
    client_name: clientName,
    cardholder_id: col(cells, C.cardholder_id),
    service_provider_id: col(cells, C.service_provider_id),
    ndc: col(cells, C.ndc),
    quantity: parseFloat(col(cells, C.quantity)) || 0,
    days_supply: parseInt(col(cells, C.days_supply), 10) || 0,
    compound_code: col(cells, C.compound_code),
    daw: col(cells, C.daw),
    total_client_billed: money(col(cells, C.total_billed)),
    pharmacy_total_paid: money(col(cells, C.pharm_total_paid)),
    pharmacy_ingredient_cost_paid: money(col(cells, C.pharm_ic_paid)),
    pharmacy_dispensing_fee_paid: money(col(cells, C.pharm_df_paid)),
    submitted_ingredient_cost: money(col(cells, C.sub_ic)),
    submitted_dispensing_fee: money(col(cells, C.sub_df)),
    submitted_gross_amount_due: money(col(cells, C.sub_gross)),
    copay: money(col(cells, C.copay)),
    patient_pay_amount: money(col(cells, C.patient_pay)),
    sell_ingredient_cost: money(col(cells, C.sell_ic)),
    sell_dispensing_fee: money(col(cells, C.sell_df)),
    process_date_time: parseDateTime(col(cells, C.process_dt)),
    prescriber_npi: col(cells, C.prescriber_npi),
    drug_tier: col(cells, C.drug_tier),
    brand_generic: col(cells, C.brand_generic),
    is_preferred: col(cells, C.is_preferred),
    network_reimbursement_id: col(cells, C.nrid),
    claim_processing_fee: money(col(cells, C.cpfee)),
    transaction_fees: money(col(cells, C.txfee)),
    primary_chain_code: col(cells, C.chain),
    cycle_id: cycleId,
  };
}

function parseFileText(
  text: string,
  hasHeader: boolean,
  groupMap: Map<string, string>,
  cycleId: string
): Claim[] {
  const lines = text.split("\n");
  const results: Claim[] = [];
  const start = hasHeader ? 1 : 0;
  for (let i = start; i < lines.length; i++) {
    const line = lines[i].replace(/\r$/, "").trim();
    if (!line) continue;
    const c = parseLine(line, groupMap, cycleId);
    if (c) results.push(c);
  }
  return results;
}

// ── Vendor mapping ────────────────────────────────────────────────────────────
const NRID_VENDOR: Record<string, string> = {
  INFINITY: "Echo Health",
  IFXMANUAL: "CheckIssuing",
  PHXCOM30: "Phoenix PBM",
  PHXCOM90: "Phoenix PBM",
  COMM30: "Phoenix PBM",
  COMM90: "Phoenix PBM",
};

function vendorName(nrid: string): string {
  return NRID_VENDOR[nrid] ?? nrid;
}

// ── Aggregation helpers ───────────────────────────────────────────────────────
function pct(num: number, denom: number): string {
  if (denom === 0) return "0.0000";
  return (num / denom).toFixed(4);
}

function avgCents(totalCents: bigint, count: number): string {
  if (count === 0) return "0.00";
  return fromCents(totalCents / BigInt(count));
}

// ── Main ──────────────────────────────────────────────────────────────────────
async function main() {
  console.log("InfinityRx Data Builder — starting");
  const t0 = Date.now();

  // 1. Group map
  process.stdout.write("Loading group map… ");
  const groupMap = await buildGroupMap();

  // 2. Read + parse all 3 files
  const FILES = [
    {
      name: "InfinityRX_20260401_1618.txt",
      cycleId: "BC-2026-SM-08",
      status: "in_progress" as const,
      hasHeader: true,
    },
    {
      name: "InfinityRX_20260401_0815.txt",
      cycleId: "BC-2026-SM-07",
      status: "completed" as const,
      hasHeader: false,
    },
    {
      name: "InfinityRX_20260316_0815.txt",
      cycleId: "BC-2026-SM-06",
      status: "completed" as const,
      hasHeader: false,
    },
  ];

  const allClaims: Claim[] = [];
  const cycleStats: {
    cycleId: string;
    fileName: string;
    status: "completed" | "in_progress";
    claims: Claim[];
  }[] = [];

  for (const f of FILES) {
    process.stdout.write(`Parsing ${f.name}… `);
    const text = fs.readFileSync(path.join(SOURCE_DIR, f.name), "utf-8");
    const claims = parseFileText(text, f.hasHeader, groupMap, f.cycleId);
    allClaims.push(...claims);
    cycleStats.push({ cycleId: f.cycleId, fileName: f.name, status: f.status, claims });
    console.log(`${claims.length} claims`);
  }
  console.log(`Total claims parsed: ${allClaims.length}`);

  // 3. Ensure output dir
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  // ── Overview ────────────────────────────────────────────────────────────────
  process.stdout.write("Computing overview… ");
  let totalBilled = 0n;
  let totalPaid = 0n;
  let totalCPFee = 0n;
  let totalTxFee = 0n;
  let paidCount = 0;
  let revCount = 0;

  for (const c of allClaims) {
    totalBilled += toCents(c.total_client_billed);
    totalPaid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    totalCPFee += toCents(c.claim_processing_fee);
    totalTxFee += toCents(c.transaction_fees);
    if (c.status === "R") revCount++; else paidCount++;
  }

  const overview = {
    total_claims: allClaims.length,
    paid_claims: paidCount,
    reversal_claims: revCount,
    total_client_billed: fromCents(totalBilled),
    total_pharmacy_paid: fromCents(totalPaid),
    total_processing_fees: fromCents(totalCPFee),
    total_transaction_fees: fromCents(totalTxFee),
    reversal_rate: pct(revCount, allClaims.length),
  };
  fs.writeFileSync(path.join(OUT_DIR, "overview.json"), JSON.stringify(overview, null, 2));
  console.log("done");

  // ── Cycles ──────────────────────────────────────────────────────────────────
  process.stdout.write("Computing cycles… ");
  const cycles = cycleStats.map(({ cycleId, fileName, status, claims }) => {
    let billed = 0n;
    let paid = 0n;
    let cPaid = 0;
    let cRev = 0;
    let dosMin = "9999-12-31";
    let dosMax = "0000-01-01";
    for (const c of claims) {
      billed += toCents(c.total_client_billed);
      paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
      if (c.status === "R") cRev++; else cPaid++;
      if (c.date_of_service && c.date_of_service < dosMin) dosMin = c.date_of_service;
      if (c.date_of_service && c.date_of_service > dosMax) dosMax = c.date_of_service;
    }
    return {
      cycle_id: cycleId,
      file_name: fileName,
      status,
      total_claims: claims.length,
      paid_claims: cPaid,
      reversal_claims: cRev,
      total_client_billed: fromCents(billed),
      total_pharmacy_paid: fromCents(paid),
      reversal_rate: pct(cRev, claims.length),
      dos_min: dosMin,
      dos_max: dosMax,
    };
  });
  fs.writeFileSync(path.join(OUT_DIR, "cycles.json"), JSON.stringify(cycles, null, 2));
  console.log("done");

  // ── By-client ───────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-client… ");
  const clientMap = new Map<string, { client_name: string; billed: bigint; paid: bigint; paid_c: number; rev_c: number }>();
  for (const c of allClaims) {
    const key = c.group_number || c.client_name;
    if (!clientMap.has(key)) {
      clientMap.set(key, { client_name: c.client_name, billed: 0n, paid: 0n, paid_c: 0, rev_c: 0 });
    }
    const e = clientMap.get(key)!;
    e.billed += toCents(c.total_client_billed);
    e.paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    if (c.status === "R") e.rev_c++; else e.paid_c++;
  }

  const byClient = Array.from(clientMap.entries())
    .map(([group_number, e]) => ({
      group_number,
      client_name: e.client_name,
      total_claims: e.paid_c + e.rev_c,
      paid_claims: e.paid_c,
      reversal_claims: e.rev_c,
      total_client_billed: fromCents(e.billed),
      total_pharmacy_paid: fromCents(e.paid),
      reversal_rate: pct(e.rev_c, e.paid_c + e.rev_c),
    }))
    .sort((a, b) => Number(toCents(b.total_client_billed) - toCents(a.total_client_billed)));

  fs.writeFileSync(path.join(OUT_DIR, "by-client.json"), JSON.stringify(byClient, null, 2));
  const topClients = byClient.slice(0, 50);
  fs.writeFileSync(path.join(OUT_DIR, "top-clients.json"), JSON.stringify(topClients, null, 2));
  console.log(`${byClient.length} clients`);

  // ── By-NRID ─────────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-nrid… ");
  const nridMap = new Map<string, { billed: bigint; paid: bigint; paid_c: number; rev_c: number }>();
  for (const c of allClaims) {
    const k = c.network_reimbursement_id || "UNKNOWN";
    if (!nridMap.has(k)) nridMap.set(k, { billed: 0n, paid: 0n, paid_c: 0, rev_c: 0 });
    const e = nridMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    if (c.status === "R") e.rev_c++; else e.paid_c++;
  }
  const byNrid = Array.from(nridMap.entries()).map(([nrid, e]) => ({
    nrid,
    vendor_name: vendorName(nrid),
    total_claims: e.paid_c + e.rev_c,
    paid_claims: e.paid_c,
    reversal_claims: e.rev_c,
    total_client_billed: fromCents(e.billed),
    total_pharmacy_paid: fromCents(e.paid),
  }));
  fs.writeFileSync(path.join(OUT_DIR, "by-nrid.json"), JSON.stringify(byNrid, null, 2));

  const nridTotal = allClaims.length;
  const nridDist = byNrid.map((n) => ({
    nrid: n.nrid,
    vendor_name: n.vendor_name,
    claim_count: n.total_claims,
    pct_of_total: pct(n.total_claims, nridTotal),
  }));
  fs.writeFileSync(path.join(OUT_DIR, "nrid-distribution.json"), JSON.stringify(nridDist, null, 2));
  console.log("done");

  // ── By-chain ─────────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-chain… ");
  const chainMap = new Map<string, { billed: bigint; paid: bigint; count: number }>();
  for (const c of allClaims) {
    const k = c.primary_chain_code || "UNKNOWN";
    if (!chainMap.has(k)) chainMap.set(k, { billed: 0n, paid: 0n, count: 0 });
    const e = chainMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    e.count++;
  }
  const byChain = Array.from(chainMap.entries())
    .map(([chain, e]) => ({
      primary_chain_code: chain,
      total_claims: e.count,
      total_client_billed: fromCents(e.billed),
      total_pharmacy_paid: fromCents(e.paid),
    }))
    .sort((a, b) => b.total_claims - a.total_claims);
  fs.writeFileSync(path.join(OUT_DIR, "by-chain.json"), JSON.stringify(byChain, null, 2));
  console.log(`${byChain.length} chains`);

  // ── By-pharmacy ──────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-pharmacy… ");
  const pharmMap = new Map<string, { billed: bigint; paid: bigint; paid_c: number; rev_c: number; chain: string }>();
  for (const c of allClaims) {
    const k = c.service_provider_id || "UNKNOWN";
    if (!pharmMap.has(k)) pharmMap.set(k, { billed: 0n, paid: 0n, paid_c: 0, rev_c: 0, chain: c.primary_chain_code });
    const e = pharmMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    if (c.status === "R") e.rev_c++; else e.paid_c++;
  }
  const byPharmacy = Array.from(pharmMap.entries())
    .map(([spi, e]) => {
      const total = e.paid_c + e.rev_c;
      return {
        service_provider_id: spi,
        total_claims: total,
        paid_claims: e.paid_c,
        reversal_claims: e.rev_c,
        total_client_billed: fromCents(e.billed),
        total_pharmacy_paid: fromCents(e.paid),
        avg_claim_billed: avgCents(e.billed, total),
        reversal_rate: pct(e.rev_c, total),
        primary_chain_code: e.chain,
      };
    })
    .sort((a, b) => b.total_claims - a.total_claims);
  fs.writeFileSync(path.join(OUT_DIR, "by-pharmacy.json"), JSON.stringify(byPharmacy, null, 2));
  const topPharmacies = byPharmacy.slice(0, 50);
  fs.writeFileSync(path.join(OUT_DIR, "top-pharmacies.json"), JSON.stringify(topPharmacies, null, 2));
  console.log(`${byPharmacy.length} pharmacies`);

  // ── By-NDC ───────────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-ndc… ");
  const ndcMap = new Map<string, { billed: bigint; paid: bigint; count: number; tier: string; bg: string }>();
  for (const c of allClaims) {
    const k = c.ndc || "UNKNOWN";
    if (!ndcMap.has(k)) ndcMap.set(k, { billed: 0n, paid: 0n, count: 0, tier: c.drug_tier, bg: c.brand_generic });
    const e = ndcMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
    e.count++;
  }
  const byNdc = Array.from(ndcMap.entries())
    .map(([ndc, e]) => ({
      ndc,
      drug_tier: e.tier,
      brand_generic: e.bg,
      total_claims: e.count,
      total_client_billed: fromCents(e.billed),
      total_pharmacy_paid: fromCents(e.paid),
      avg_claim_billed: avgCents(e.billed, e.count),
    }))
    .sort((a, b) => Number(toCents(b.total_client_billed) - toCents(a.total_client_billed)));
  fs.writeFileSync(path.join(OUT_DIR, "by-ndc.json"), JSON.stringify(byNdc, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, "top-ndcs.json"), JSON.stringify(byNdc.slice(0, 50), null, 2));
  console.log(`${byNdc.length} NDCs`);

  // ── By-prescriber ────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-prescriber… ");
  const rxMap = new Map<string, { billed: bigint; count: number; patients: Set<string>; ndcs: Set<string> }>();
  for (const c of allClaims) {
    const k = c.prescriber_npi || "UNKNOWN";
    if (!rxMap.has(k)) rxMap.set(k, { billed: 0n, count: 0, patients: new Set(), ndcs: new Set() });
    const e = rxMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.count++;
    e.patients.add(c.cardholder_id);
    e.ndcs.add(c.ndc);
  }
  const byPrescriber = Array.from(rxMap.entries())
    .map(([npi, e]) => ({
      prescriber_npi: npi,
      total_claims: e.count,
      total_client_billed: fromCents(e.billed),
      unique_patients: e.patients.size,
      unique_ndcs: e.ndcs.size,
    }))
    .sort((a, b) => b.total_claims - a.total_claims);
  fs.writeFileSync(path.join(OUT_DIR, "by-prescriber.json"), JSON.stringify(byPrescriber, null, 2));
  console.log(`${byPrescriber.length} prescribers`);

  // ── By-member ─────────────────────────────────────────────────────────────────
  process.stdout.write("Computing by-member… ");
  const memberMap = new Map<string, { client_name: string; billed: bigint; count: number; ndcs: Set<string> }>();
  for (const c of allClaims) {
    const k = c.cardholder_id || "UNKNOWN";
    if (!memberMap.has(k)) memberMap.set(k, { client_name: c.client_name, billed: 0n, count: 0, ndcs: new Set() });
    const e = memberMap.get(k)!;
    e.billed += toCents(c.total_client_billed);
    e.count++;
    e.ndcs.add(c.ndc);
  }
  const byMember = Array.from(memberMap.entries())
    .map(([cid, e]) => ({
      cardholder_id: cid,
      client_name: e.client_name,
      total_claims: e.count,
      total_client_billed: fromCents(e.billed),
      unique_ndcs: e.ndcs.size,
    }))
    .sort((a, b) => b.total_claims - a.total_claims);
  fs.writeFileSync(path.join(OUT_DIR, "by-member.json"), JSON.stringify(byMember, null, 2));
  console.log(`${byMember.length} members`);

  // ── Daily volume ──────────────────────────────────────────────────────────────
  process.stdout.write("Computing daily-volume… ");
  const dayMap = new Map<string, { total: number; paid: number; rev: number; billed: bigint }>();
  for (const c of allClaims) {
    const k = c.date_of_service || "UNKNOWN";
    if (!dayMap.has(k)) dayMap.set(k, { total: 0, paid: 0, rev: 0, billed: 0n });
    const e = dayMap.get(k)!;
    e.total++;
    if (c.status === "R") e.rev++; else e.paid++;
    e.billed += toCents(c.total_client_billed);
  }
  const dailyVolume = Array.from(dayMap.entries())
    .map(([date, e]) => ({
      date,
      total_claims: e.total,
      paid_claims: e.paid,
      reversal_claims: e.rev,
      total_client_billed: fromCents(e.billed),
    }))
    .sort((a, b) => a.date.localeCompare(b.date));
  fs.writeFileSync(path.join(OUT_DIR, "daily-volume.json"), JSON.stringify(dailyVolume, null, 2));
  console.log(`${dailyVolume.length} days`);

  // ── Reversal rate ─────────────────────────────────────────────────────────────
  process.stdout.write("Computing reversal-rate… ");
  const reversalRate = {
    overall_rate: pct(revCount, allClaims.length),
    by_client: byClient.map((c) => ({
      client_name: c.client_name,
      group_number: c.group_number,
      total_claims: c.total_claims,
      reversal_count: c.reversal_claims,
      reversal_rate: c.reversal_rate,
    })),
  };
  fs.writeFileSync(path.join(OUT_DIR, "reversal-rate.json"), JSON.stringify(reversalRate, null, 2));
  console.log("done");

  // ── Activity feed (30 synthetic events from real data) ─────────────────────
  process.stdout.write("Building activity-feed… ");
  const latestClaim = allClaims.reduce((best, c) =>
    c.process_date_time > best.process_date_time ? c : best, allClaims[0]);

  const echoTotal = byNrid.find((n) => n.nrid === "INFINITY");
  const phxTotal = byNrid.filter((n) => n.nrid.startsWith("PHX") || n.nrid.startsWith("COMM"))
    .reduce((s, n) => s + Number(toCents(n.total_client_billed)), 0);
  const phxCount = byNrid.filter((n) => n.nrid.startsWith("PHX") || n.nrid.startsWith("COMM"))
    .reduce((s, n) => s + n.total_claims, 0);

  // Get top 5 reversals
  const reversals = allClaims.filter((c) => c.status === "R").slice(0, 5);
  // Top 5 pharmacies with most claims
  const topPharm5 = topPharmacies.slice(0, 5);

  // Cycle totals for events
  const cycleMap: Record<string, (typeof cycles)[0]> = {};
  for (const cy of cycles) cycleMap[cy.cycle_id] = cy;

  function makeId(n: number): string {
    return `ev-${String(n).padStart(4, "0")}`;
  }
  function offsetTs(base: string, offsetMin: number): string {
    if (!base) return new Date().toISOString();
    const d = new Date(base);
    d.setMinutes(d.getMinutes() + offsetMin);
    return d.toISOString();
  }

  const feed = [
    {
      id: makeId(1),
      timestamp: latestClaim.process_date_time || new Date().toISOString(),
      type: "cycle_approved",
      title: `Billing Cycle BC-2026-SM-08 approved`,
      description: `Mike K approved Billing Cycle BC-2026-SM-08 ($${cycleMap["BC-2026-SM-08"]?.total_client_billed ?? "23,868,600.79"}) — ${cycleMap["BC-2026-SM-08"]?.total_claims ?? 89231} claims processed`,
      severity: "success",
      amount: cycleMap["BC-2026-SM-08"]?.total_client_billed,
      client_name: "InfinityRx",
    },
    {
      id: makeId(2),
      timestamp: offsetTs(latestClaim.process_date_time, -5),
      type: "batch_transmitted",
      title: "Echo Health batch transmitted",
      description: `Echo Health batch — ${echoTotal?.total_claims ?? 0} claims, $${echoTotal?.total_client_billed ?? "0.00"} total`,
      severity: "info",
      amount: echoTotal?.total_client_billed,
      client_name: "Echo Health",
    },
    {
      id: makeId(3),
      timestamp: offsetTs(latestClaim.process_date_time, -12),
      type: "batch_transmitted",
      title: "Phoenix PBM batch transmitted",
      description: `Phoenix PBM combined batch — ${phxCount} claims, $${fromCents(BigInt(Math.round(phxTotal)))} total`,
      severity: "info",
      amount: fromCents(BigInt(Math.round(phxTotal))),
      client_name: "Phoenix PBM",
    },
    {
      id: makeId(4),
      timestamp: offsetTs(latestClaim.process_date_time, -20),
      type: "cycle_approved",
      title: "Billing Cycle BC-2026-SM-07 completed",
      description: `Cycle BC-2026-SM-07 closed — ${cycleMap["BC-2026-SM-07"]?.total_claims ?? 0} claims, $${cycleMap["BC-2026-SM-07"]?.total_client_billed ?? "0.00"}`,
      severity: "success",
      amount: cycleMap["BC-2026-SM-07"]?.total_client_billed,
      client_name: "InfinityRx",
    },
    {
      id: makeId(5),
      timestamp: offsetTs(latestClaim.process_date_time, -35),
      type: "cycle_approved",
      title: "Billing Cycle BC-2026-SM-06 completed",
      description: `Cycle BC-2026-SM-06 closed — ${cycleMap["BC-2026-SM-06"]?.total_claims ?? 0} claims, $${cycleMap["BC-2026-SM-06"]?.total_client_billed ?? "0.00"}`,
      severity: "success",
      amount: cycleMap["BC-2026-SM-06"]?.total_client_billed,
      client_name: "InfinityRx",
    },
    ...reversals.map((r, i) => ({
      id: makeId(6 + i),
      timestamp: r.process_date_time || offsetTs(latestClaim.process_date_time, -(50 + i * 10)),
      type: "reversal",
      title: `Reversal logged — ${r.client_name}`,
      description: `Claim ${r.claim_id} reversed for ${r.client_name} — $${r.total_client_billed} | NPI ${r.service_provider_id}`,
      severity: "warning" as const,
      amount: r.total_client_billed,
      client_name: r.client_name,
    })),
    ...topPharm5.map((p, i) => ({
      id: makeId(11 + i),
      timestamp: offsetTs(latestClaim.process_date_time, -(100 + i * 15)),
      type: "pharmacy_batch",
      title: `New claims batch from pharmacy ${p.service_provider_id}`,
      description: `Pharmacy NPI ${p.service_provider_id} — ${p.total_claims} claims processed, $${p.total_client_billed} billed`,
      severity: "info" as const,
      amount: p.total_client_billed,
      client_name: p.primary_chain_code || "Unknown Chain",
    })),
    ...topClients.slice(0, 10).map((c, i) => ({
      id: makeId(16 + i),
      timestamp: offsetTs(latestClaim.process_date_time, -(200 + i * 8)),
      type: "client_invoice",
      title: `Invoice generated for ${c.client_name}`,
      description: `Client ${c.client_name} (${c.group_number}) — ${c.total_claims} claims, $${c.total_client_billed} billed`,
      severity: "info" as const,
      amount: c.total_client_billed,
      client_name: c.client_name,
    })),
  ].slice(0, 30);

  fs.writeFileSync(path.join(OUT_DIR, "activity-feed.json"), JSON.stringify(feed, null, 2));
  console.log(`${feed.length} events`);

  // ── Investigations (10 anomaly-derived cards) ─────────────────────────────
  process.stdout.write("Building investigations… ");

  // Top 3 highest reversal rates (≥10 claims)
  const highRevPharm = byPharmacy
    .filter((p) => p.total_claims >= 10 && Number(p.reversal_rate) > 0)
    .sort((a, b) => Number(b.reversal_rate) - Number(a.reversal_rate))
    .slice(0, 3);

  // Top 3 highest avg claim amount
  const highAvgPharm = byPharmacy
    .sort((a, b) => Number(toCents(b.avg_claim_billed)) - Number(toCents(a.avg_claim_billed)))
    .slice(0, 3);

  // Top 2 clients by volume change between cycle 06 and 08
  const cycle06Claims = cycleStats.find((s) => s.cycleId === "BC-2026-SM-06")?.claims ?? [];
  const cycle08Claims = cycleStats.find((s) => s.cycleId === "BC-2026-SM-08")?.claims ?? [];
  const clientVol06 = new Map<string, number>();
  const clientVol08 = new Map<string, number>();
  for (const c of cycle06Claims) clientVol06.set(c.client_name, (clientVol06.get(c.client_name) ?? 0) + 1);
  for (const c of cycle08Claims) clientVol08.set(c.client_name, (clientVol08.get(c.client_name) ?? 0) + 1);
  const volumeChanges: { client: string; delta: number }[] = [];
  for (const [client, v08] of clientVol08.entries()) {
    const v06 = clientVol06.get(client) ?? 0;
    if (v06 > 0) volumeChanges.push({ client, delta: Math.abs(v08 - v06) });
  }
  const topVolumeChange = volumeChanges.sort((a, b) => b.delta - a.delta).slice(0, 2);

  const investigations = [
    ...highRevPharm.map((p, i) => ({
      id: `inv-rev-${i + 1}`,
      status: (["new", "new", "assigned"] as const)[i],
      flag: {
        severity: (["critical", "high", "high"] as const)[i],
        flag_type: "high_reversal_rate",
        entity_name: `Pharmacy NPI ${p.service_provider_id}`,
        entity_id: p.service_provider_id,
      },
      client_name: "Multiple",
      days_open: [7, 3, 1][i],
      estimated_recovery: fromCents(toCents(p.total_client_billed) / 10n),
      assigned_to_name: i === 2 ? "Sarah M." : undefined,
      notes: `Reversal rate ${(Number(p.reversal_rate) * 100).toFixed(1)}% — ${p.reversal_claims} reversals out of ${p.total_claims} claims`,
    })),
    ...highAvgPharm.map((p, i) => ({
      id: `inv-avg-${i + 1}`,
      status: (["assigned", "evidence", "new"] as const)[i],
      flag: {
        severity: (["high", "medium", "low"] as const)[i],
        flag_type: "high_avg_claim_amount",
        entity_name: `Pharmacy NPI ${p.service_provider_id}`,
        entity_id: p.service_provider_id,
      },
      client_name: "Multiple",
      days_open: [5, 12, 2][i],
      estimated_recovery: fromCents(toCents(p.avg_claim_billed) * 5n),
      assigned_to_name: i === 0 ? "James K." : i === 1 ? "Ana R." : undefined,
      notes: `Average claim $${p.avg_claim_billed} — ${p.total_claims} claims, chain ${p.primary_chain_code || "INDEPENDENT"}`,
    })),
    ...topVolumeChange.map((v, i) => ({
      id: `inv-vol-${i + 1}`,
      status: (["demand", "evidence"] as const)[i],
      flag: {
        severity: (["high", "medium"] as const)[i],
        flag_type: "volume_spike",
        entity_name: v.client,
        entity_id: v.client,
      },
      client_name: v.client,
      days_open: [14, 9][i],
      estimated_recovery: fromCents(BigInt(v.delta * 1500)),
      assigned_to_name: ["Chris T.", "Maria L."][i],
      notes: `Volume changed by ${v.delta} claims between cycle SM-06 and SM-08`,
    })),
    {
      id: "inv-sample-1",
      status: "resolved" as const,
      flag: {
        severity: "medium" as const,
        flag_type: "duplicate_claim",
        entity_name: allClaims[0]?.service_provider_id ? `Pharmacy NPI ${allClaims[0].service_provider_id}` : "Pharmacy",
        entity_id: allClaims[0]?.service_provider_id ?? "UNKNOWN",
      },
      client_name: allClaims[0]?.client_name ?? "Unknown",
      days_open: 0,
      estimated_recovery: "0.00",
      assigned_to_name: "Peter V.",
      notes: "Duplicate claim pattern confirmed and resolved — pharmacy corrected submission",
    },
    {
      id: "inv-sample-2",
      status: "new" as const,
      flag: {
        severity: "low" as const,
        flag_type: "daw_mismatch",
        entity_name: byNdc[0]?.ndc ? `NDC ${byNdc[0].ndc}` : "Drug",
        entity_id: byNdc[0]?.ndc ?? "UNKNOWN",
      },
      client_name: byClient[0]?.client_name ?? "Unknown",
      days_open: 1,
      estimated_recovery: fromCents(toCents(byNdc[0]?.avg_claim_billed ?? "0.00") * 3n),
      assigned_to_name: undefined,
      notes: `DAW code mismatch on ${byNdc[0]?.ndc ?? "NDC"} — ${byNdc[0]?.total_claims ?? 0} claims flagged for review`,
    },
  ].slice(0, 10);

  fs.writeFileSync(path.join(OUT_DIR, "investigations.json"), JSON.stringify(investigations, null, 2));
  console.log(`${investigations.length} investigations`);

  // ── Manifest ──────────────────────────────────────────────────────────────
  process.stdout.write("Writing manifest… ");
  const manifest = {
    generated_at: new Date().toISOString(),
    files: cycleStats.map(({ cycleId, fileName, status, claims }) => {
      let billed = 0n;
      let paid = 0n;
      let paidC = 0;
      let revC = 0;
      for (const c of claims) {
        billed += toCents(c.total_client_billed);
        paid += toCents(c.pharmacy_total_paid) + toCents(c.pharmacy_ingredient_cost_paid);
        if (c.status === "R") revC++; else paidC++;
      }
      return {
        name: fileName,
        cycle_id: cycleId,
        status,
        rows: claims.length,
        total_billed: fromCents(billed),
        total_paid: fromCents(paid),
        paid_count: paidC,
        reversal_count: revC,
      };
    }),
    totals: overview,
  };
  fs.writeFileSync(path.join(OUT_DIR, "manifest.json"), JSON.stringify(manifest, null, 2));
  console.log("done");

  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`\nDone in ${elapsed}s — ${allClaims.length} total claims across ${cycleStats.length} cycles`);
  console.log(`Output: ${OUT_DIR}`);
  console.log(`Files written:`);
  for (const f of fs.readdirSync(OUT_DIR)) {
    const size = fs.statSync(path.join(OUT_DIR, f)).size;
    console.log(`  ${f.padEnd(35)} ${(size / 1024).toFixed(1)} KB`);
  }
}

main().catch((e) => {
  console.error("Build failed:", e);
  process.exit(1);
});
