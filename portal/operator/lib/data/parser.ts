/**
 * Pure parsing helpers for InfinityRx pipe-delimited claims files.
 * Windows CRLF is stripped. Empty lines are skipped.
 * Money values are kept as strings for Decimal-safe display.
 */

import type { ParsedClaim } from "./types";

// Column indices for the 63-column format (file 1 with header).
// Files 2 & 3 have only 53 columns (cols 0–52); missing cols default to "".
const COL = {
  claim_id: 0,
  status: 1,
  bin: 2,
  pcn: 3,
  date_of_service: 4,
  date_written: 5,
  group_number: 6,
  cardholder_id: 7,
  last_name: 8,
  first_name: 9,
  // dob: 10 — kept only for internal filtering, not exposed on ParsedClaim
  // person_code: 11
  service_provider_id: 12,
  ndc: 13,
  rx_number: 14,
  quantity: 15,
  days_supply: 16,
  compound_code: 17,
  daw: 18,
  submitted_ingredient_cost: 19,
  submitted_dispensing_fee: 20,
  // usual_and_customary: 21
  submitted_gross_amount_due: 22,
  // submitted_tax: 23
  prescriber_npi: 24,
  copay: 25,
  patient_pay_amount: 26,
  // amount_applied_to_deductible: 27
  // amount_applied_to_out_of_pocket: 28
  pharmacy_total_paid: 29,
  pharmacy_ingredient_cost_paid: 30,
  pharmacy_dispensing_fee_paid: 31,
  // pharmacy_tax_paid: 32
  sell_ingredient_cost: 33,
  sell_dispensing_fee: 34,
  // sell_tax: 35
  total_client_billed: 36,
  // other_coverage_code: 37
  process_date_time: 38,
  // price_source: 39
  // keyed_claim_indicator: 40
  // selfpay_indicator: 41
  // is_billable: 42
  // historical: 43
  // test_claim: 44
  // location_code: 45
  // script_tag: 46
  drug_tier: 47,
  brand_generic: 48,
  is_preferred: 49,
  // sender_id: 50
  network_reimbursement_id: 51,
  // amount_applied_to_benefit_cap: 52
  claim_processing_fee: 53, // only in 63-col files
  transaction_fees: 54, // only in 63-col files
  // reversal_auth_reference: 55
  // statement_flag: 56
  // bank_routing_number: 57
  // bank_account_number: 58
  // bank_account_type: 59
  primary_chain_code: 60, // only in 63-col files
  // debit_card_amount: 61
  // pos_adjustment: 62
} as const;

/** Parse MM/DD/YYYY → YYYY-MM-DD. Returns "" for blank/invalid. */
function parseDate(raw: string): string {
  if (!raw) return "";
  const m = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m) return raw;
  return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
}

/** Parse "MM/DD/YYYY HH:MM:SS" → ISO 8601. Returns "" for blank. */
function parseDateTime(raw: string): string {
  if (!raw) return "";
  const m = raw.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{2}:\d{2}:\d{2})/);
  if (!m) return raw;
  return `${m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}T${m[4]}`;
}

/** Trim and return "0" for blank money strings. */
function money(raw: string): string {
  const v = raw.trim();
  if (!v) return "0.00";
  // Normalise — strip trailing zeros beyond 2dp but keep at least 2dp
  const n = parseFloat(v);
  if (isNaN(n)) return "0.00";
  return n.toFixed(2);
}

function col(cells: string[], idx: number): string {
  if (idx >= cells.length) return "";
  return cells[idx].trim();
}

export function parseLine(
  line: string,
  _headers: string[],
  groupMap: Map<string, string>,
  cycleId: string
): ParsedClaim | null {
  const cells = line.split("|");
  if (cells.length < 40) return null; // too short — malformed

  const groupNumber = col(cells, COL.group_number);
  const clientName =
    groupMap.get(groupNumber) ??
    groupMap.get(groupNumber.toLowerCase()) ??
    groupNumber;

  const statusRaw = col(cells, COL.status);
  const status: "P" | "R" = statusRaw === "R" ? "R" : "P";

  return {
    claim_id: col(cells, COL.claim_id),
    status,
    bin: col(cells, COL.bin),
    pcn: col(cells, COL.pcn),
    date_of_service: parseDate(col(cells, COL.date_of_service)),
    date_written: parseDate(col(cells, COL.date_written)),
    group_number: groupNumber,
    client_name: clientName,
    cardholder_id: col(cells, COL.cardholder_id),
    last_name: col(cells, COL.last_name),
    first_name: col(cells, COL.first_name),
    service_provider_id: col(cells, COL.service_provider_id),
    ndc: col(cells, COL.ndc),
    rx_number: col(cells, COL.rx_number),
    quantity: parseFloat(col(cells, COL.quantity)) || 0,
    days_supply: parseInt(col(cells, COL.days_supply), 10) || 0,
    compound_code: col(cells, COL.compound_code),
    daw: col(cells, COL.daw),
    submitted_ingredient_cost: money(col(cells, COL.submitted_ingredient_cost)),
    submitted_dispensing_fee: money(col(cells, COL.submitted_dispensing_fee)),
    submitted_gross_amount_due: money(col(cells, COL.submitted_gross_amount_due)),
    copay: money(col(cells, COL.copay)),
    patient_pay_amount: money(col(cells, COL.patient_pay_amount)),
    pharmacy_total_paid: money(col(cells, COL.pharmacy_total_paid)),
    pharmacy_ingredient_cost_paid: money(col(cells, COL.pharmacy_ingredient_cost_paid)),
    pharmacy_dispensing_fee_paid: money(col(cells, COL.pharmacy_dispensing_fee_paid)),
    sell_ingredient_cost: money(col(cells, COL.sell_ingredient_cost)),
    sell_dispensing_fee: money(col(cells, COL.sell_dispensing_fee)),
    total_client_billed: money(col(cells, COL.total_client_billed)),
    process_date_time: parseDateTime(col(cells, COL.process_date_time)),
    prescriber_npi: col(cells, COL.prescriber_npi),
    drug_tier: col(cells, COL.drug_tier),
    brand_generic: col(cells, COL.brand_generic),
    is_preferred: col(cells, COL.is_preferred),
    network_reimbursement_id: col(cells, COL.network_reimbursement_id),
    claim_processing_fee: money(col(cells, COL.claim_processing_fee)),
    transaction_fees: money(col(cells, COL.transaction_fees)),
    primary_chain_code: col(cells, COL.primary_chain_code),
    cycle_id: cycleId,
  };
}

export interface ParseFileOpts {
  hasHeader: boolean;
  headers: string[];
  groupMap: Map<string, string>;
  cycleId: string;
}

export function parseFile(text: string, opts: ParseFileOpts): ParsedClaim[] {
  const lines = text.split("\n");
  const results: ParsedClaim[] = [];
  const start = opts.hasHeader ? 1 : 0;

  for (let i = start; i < lines.length; i++) {
    const line = lines[i].replace(/\r$/, "").trim();
    if (!line) continue;
    const claim = parseLine(line, opts.headers, opts.groupMap, opts.cycleId);
    if (claim) results.push(claim);
  }

  return results;
}
