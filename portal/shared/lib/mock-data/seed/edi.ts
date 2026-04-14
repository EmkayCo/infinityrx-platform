import { rngInt, rngPick, isoDate, makeUUID, PRIMARY_TENANT } from "./prng";
import type { TradingPartner, EDITransaction, EDIMonitorStats, CertAlert } from "@shared/types/edi";

const PARTNER_NAMES = [
  "BlueCross BlueShield National",
  "Aetna Health Plans",
  "Cigna Healthcare",
  "UnitedHealthcare EDI",
  "Humana Claims Processing",
  "CVS Caremark Exchange",
  "Express Scripts Connectivity",
  "Walgreens EDI Hub",
  "Medicare FFS Portal",
  "Medicaid State Gateway",
  "Change Healthcare Network",
  "Availity EDI Services",
] as const;

const TX_TYPES: EDITransaction["transaction_type"][] = [
  "835",
  "837",
  "270",
  "271",
  "276",
  "277",
  "278",
  "834",
  "999",
];

const TX_STATUSES: EDITransaction["status"][] = [
  "accepted",
  "accepted",
  "accepted",
  "accepted",
  "pending",
  "pending",
  "rejected",
  "acknowledged",
  "error",
];

const PARTNER_STATUSES: TradingPartner["status"][] = [
  "active",
  "active",
  "active",
  "active",
  "active",
  "active",
  "active",
  "active",
  "active",
  "test",
  "test",
  "disabled",
];

export const TRADING_PARTNERS: TradingPartner[] = Array.from({ length: 12 }, (_, i) => {
  const status = PARTNER_STATUSES[i];
  const protocol = i % 3 === 0 ? "SFTP" : "AS2";
  const certDays = [7, 12, 21, 30, 45, 60, 75, 90, 120, 180, 270, 365][i];
  const certExpiry = isoDate(certDays).substring(0, 10);

  return {
    id: makeUUID(30000 + i),
    tenant_id: PRIMARY_TENANT,
    name: PARTNER_NAMES[i],
    partner_id: `EDI-PARTNER-${String(i + 1).padStart(3, "0")}`,
    status,
    protocols: [protocol],
    as2_id: protocol === "AS2" ? `AS2-${PARTNER_NAMES[i].replace(/\s+/g, "").substring(0, 12).toUpperCase()}` : undefined,
    sftp_host: protocol === "SFTP" ? `sftp.${PARTNER_NAMES[i].toLowerCase().replace(/[^a-z]/g, "")}.com` : undefined,
    sftp_port: protocol === "SFTP" ? 22 : undefined,
    sftp_username: protocol === "SFTP" ? "infinityrx_prod" : undefined,
    cert_name: `${PARTNER_NAMES[i].split(" ")[0]}_SSL_2026.pem`,
    cert_expiry: certExpiry,
    days_until_cert_expiry: certDays,
    test_mode: status === "test",
    accepted_transaction_types: TX_TYPES.slice(0, rngInt(3, TX_TYPES.length)),
    created_at: isoDate(-(180 + i * 15)),
    updated_at: isoDate(-(i * 7)),
  };
});

export const EDI_TRANSACTIONS: EDITransaction[] = Array.from({ length: 60 }, (_, i) => {
  const partner = TRADING_PARTNERS[i % TRADING_PARTNERS.length];
  const txType = TX_TYPES[i % TX_TYPES.length];
  const status = TX_STATUSES[i % TX_STATUSES.length];
  const direction: EDITransaction["direction"] = i % 3 === 0 ? "inbound" : "outbound";
  const receivedAt = isoDate(-(i * 2));

  return {
    id: makeUUID(31000 + i),
    tenant_id: PRIMARY_TENANT,
    partner_id: partner.id,
    partner_name: partner.name,
    filename: `${txType}_${partner.partner_id}_${new Date(Date.parse(receivedAt)).toISOString().substring(0, 10).replace(/-/g, "")}_${String(i + 1).padStart(6, "0")}.x12`,
    direction,
    transaction_type: txType,
    interchange_control_number: String(rngInt(100000000, 999999999)),
    functional_group_id: String(rngInt(10000, 99999)),
    transaction_count: rngInt(1, 500),
    status,
    validation_errors:
      status === "rejected"
        ? [
            {
              segment: "ISA",
              element: "ISA06",
              error_code: "001",
              message: "Invalid interchange sender ID",
            },
          ]
        : undefined,
    raw_preview:
      "ISA*00*          *00*          *ZZ*INFINITYRX      *ZZ*BCBS           *260414*1200*^*00501*000000001*0*P*:~\nGS*FA*INFINITYRX*BCBS*20260414*120000*1*X*005010X231A1~\n...",
    received_at: receivedAt,
    processed_at: status !== "pending" ? isoDate(-(i * 2) + 1) : undefined,
    ack_sent_at:
      status === "acknowledged" || status === "accepted" ? isoDate(-(i * 2) + 1) : undefined,
  };
});

export const CERT_ALERTS: CertAlert[] = TRADING_PARTNERS.filter(
  (p) => (p.days_until_cert_expiry ?? 999) < 90
).map((p, i) => ({
  id: makeUUID(32000 + i),
  partner_id: p.id,
  partner_name: p.name,
  cert_name: p.cert_name ?? "Unknown cert",
  expires_at: (p.cert_expiry ?? isoDate(30)).toString(),
  days_until_expiry: p.days_until_cert_expiry ?? 89,
}));

export const EDI_MONITOR_STATS: EDIMonitorStats = {
  transactions_in_flight: 14,
  acceptance_rate_24h: 97.3,
  acceptance_rate_7d: 96.8,
  acceptance_rate_30d: 97.1,
  median_ack_turnaround_ms: 420,
  p95_ack_turnaround_ms: 1850,
  top_rejection_codes: [
    { code: "001", description: "Invalid interchange sender ID", count: 12 },
    { code: "022", description: "Invalid control structure", count: 7 },
    { code: "024", description: "Invalid interchange content", count: 5 },
  ],
  volume_trend_30d: Array.from({ length: 30 }, (_, i) => ({
    date: isoDate(-(29 - i)).substring(0, 10),
    inbound: rngInt(20, 120),
    outbound: rngInt(15, 90),
  })),
};
