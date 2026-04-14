import { rngInt, rngPick, money, isoDate, makeUUID, PRIMARY_TENANT } from "./prng";
import type { PaymentBatch, NachaFile, Vendor, Submission, AchReturn } from "@shared/types/payments";

const BATCH_STATUSES: PaymentBatch["status"][] = [
  "pending_approval",
  "pending_approval",
  "pending_approval",
  "approved",
  "approved",
  "transmitted",
  "transmitted",
  "transmitted",
  "acknowledged",
  "settled",
  "settled",
  "settled",
  "failed",
  "voided",
  "generating",
  "generated",
  "transmitting",
  "draft",
  "settled",
  "settled",
];

const VENDORS: Array<PaymentBatch["vendor"]> = ["nacha", "echo", "check_issuing"];
const VENDOR_NAMES: Record<PaymentBatch["vendor"], string> = {
  nacha: "NACHA ACH",
  echo: "Echo Health Payments",
  check_issuing: "CheckIssuing",
  wire: "Wire Transfer",
};

const CLIENT_NAMES = [
  "Acme Health Partners",
  "BlueStar Benefits Group",
  "ClearPath Managed Care",
  "Delta Pharmacy Solutions",
  "Emerald Coast PBM",
  "Frontier Health Advisors",
];

export const PAYMENT_BATCHES: PaymentBatch[] = Array.from({ length: 20 }, (_, i) => {
  const status = BATCH_STATUSES[i % BATCH_STATUSES.length];
  const vendor = VENDORS[i % VENDORS.length];
  const paymentCount = rngInt(50, 1500);
  const totalAmount = money(rngInt(10000, 500000));
  const createdAt = isoDate(-(i * 5));
  const approvedAt =
    status !== "draft" && status !== "pending_approval"
      ? isoDate(-(i * 5) + 1)
      : null;
  const transmittedAt =
    status === "transmitted" || status === "acknowledged" || status === "settled"
      ? isoDate(-(i * 5) + 2)
      : null;

  return {
    id: makeUUID(7000 + i),
    tenant_id: PRIMARY_TENANT,
    status,
    vendor,
    vendor_name: VENDOR_NAMES[vendor],
    payment_count: paymentCount,
    total_amount: totalAmount,
    created_at: createdAt,
    approved_at: approvedAt,
    approved_by: approvedAt ? "Marcus Rivera" : null,
    transmitted_at: transmittedAt,
    ack_status: transmittedAt ? (i % 3 === 0 ? "rejected" : "acknowledged") : null,
    ack_received_at: transmittedAt ? isoDate(-(i * 5) + 3) : null,
    nacha_file_id: vendor === "nacha" ? makeUUID(8000 + i) : null,
    routing: CLIENT_NAMES.slice(0, rngInt(1, 4)).map((clientName, ci) => ({
      vendor,
      vendor_name: VENDOR_NAMES[vendor],
      client_id: makeUUID(100 + ci),
      client_name: clientName,
      payment_count: Math.floor(paymentCount / (ci + 2)),
      total_amount: money(Number(totalAmount) / (ci + 2)),
    })),
  };
});

export const NACHA_FILES: NachaFile[] = Array.from({ length: 10 }, (_, i) => {
  const batchIdx = i % PAYMENT_BATCHES.length;
  const batch = PAYMENT_BATCHES[batchIdx];
  const dateStr = new Date(Date.parse("2026-04-14T00:00:00Z") - i * 2 * 86400000)
    .toISOString()
    .substring(0, 10)
    .replace(/-/g, "");
  const entryCount = rngInt(50, 800);
  const totalDebit = money(rngInt(5000, 250000));
  const totalCredit = money(Number(totalDebit) * 0.98);

  return {
    id: makeUUID(8000 + i),
    tenant_id: PRIMARY_TENANT,
    batch_id: batch.id,
    filename: `NACHA_${dateStr}_${String(i + 1).padStart(4, "0")}.txt`,
    entry_count: entryCount,
    total_debit: totalDebit,
    total_credit: totalCredit,
    effective_date: isoDate(-i * 2).substring(0, 10),
    created_at: isoDate(-i * 2 - 1),
    transmitted_at: i < 7 ? isoDate(-i * 2) : null,
    ack_status: i < 7 ? (i % 4 === 0 ? "rejected" : "acknowledged") : null,
    humanized_preview: [
      {
        line_type: "file_header",
        description: "File Header — Priority Code 01, Immediate Destination: 021000089",
        amount: null,
        routing_number: "021000089",
        account_number: null,
        individual_name: null,
        trace_number: null,
      },
      {
        line_type: "batch_header",
        description: `Batch Header — Company: INFINITYRX PBM, SEC Code: PPD, Effective Date: ${isoDate(-i * 2).substring(0, 10)}`,
        amount: null,
        routing_number: null,
        account_number: null,
        individual_name: null,
        trace_number: null,
      },
      {
        line_type: "entry",
        description: "Credit — Pharmacy settlement payment",
        amount: money(rngInt(500, 15000)),
        routing_number: "021000089",
        account_number: "****4521",
        individual_name: "CVS PHARMACY 1047",
        trace_number: `02100008900000${i + 1}`,
      },
    ],
    download_url: "#",
  };
});

export const VENDORS_LIST: Vendor[] = [
  {
    id: makeUUID(9000),
    name: "NACHA ACH",
    type: "nacha",
    status: "active",
    last_health_check: isoDate(0),
    health_status: "healthy",
  },
  {
    id: makeUUID(9001),
    name: "Echo Health Payments",
    type: "echo",
    status: "active",
    last_health_check: isoDate(0),
    health_status: "healthy",
  },
  {
    id: makeUUID(9002),
    name: "CheckIssuing",
    type: "check_issuing",
    status: "active",
    last_health_check: isoDate(-1),
    health_status: "degraded",
  },
  {
    id: makeUUID(9003),
    name: "Wire Transfer",
    type: "wire",
    status: "inactive",
    last_health_check: isoDate(-3),
    health_status: "down",
  },
];

export const SUBMISSIONS: Submission[] = Array.from({ length: 15 }, (_, i) => ({
  id: makeUUID(9100 + i),
  batch_id: PAYMENT_BATCHES[i % PAYMENT_BATCHES.length].id,
  vendor_id: VENDORS_LIST[i % 3].id,
  vendor_name: VENDORS_LIST[i % 3].name,
  status: rngPick(["submitted", "settled", "returned", "failed"] as const),
  submitted_at: isoDate(-(i * 3)),
  settled_at: i % 3 !== 2 ? isoDate(-(i * 3) + 2) : null,
  returned_at: i % 5 === 0 ? isoDate(-(i * 3) + 4) : null,
  total_amount: money(rngInt(1000, 100000)),
}));

export const ACH_RETURNS: AchReturn[] = Array.from({ length: 8 }, (_, i) => ({
  id: makeUUID(9200 + i),
  submission_id: SUBMISSIONS[i % SUBMISSIONS.length].id,
  return_code: rngPick(["R01", "R02", "R03", "R04", "R08", "R10", "R16", "R29"]),
  return_reason: rngPick([
    "Insufficient Funds",
    "Account Closed",
    "No Account/Unable to Locate Account",
    "Invalid Account Number",
    "Payment Stopped",
    "Customer Advises Not Authorized",
    "Account Frozen",
    "Corporate Customer Advises Not Authorized",
  ]),
  original_amount: money(rngInt(500, 15000)),
  returned_at: isoDate(-(i * 7)),
  resolved: i % 3 === 0,
}));
