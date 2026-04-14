import type { UUID, ISODateTimeString } from "./common";

export type TransactionType =
  | "835"
  | "837"
  | "270"
  | "271"
  | "276"
  | "277"
  | "278"
  | "834"
  | "999";

export type TransactionDirection = "inbound" | "outbound";
export type TransactionStatus = "accepted" | "rejected" | "pending" | "acknowledged" | "error";
export type PartnerProtocol = "AS2" | "SFTP" | "HTTP" | "HTTPS";
export type PartnerStatus = "active" | "test" | "disabled";

export interface TradingPartner {
  id: UUID;
  tenant_id: UUID;
  name: string;
  partner_id: string;
  status: PartnerStatus;
  protocols: PartnerProtocol[];
  as2_id?: string;
  sftp_host?: string;
  sftp_port?: number;
  sftp_username?: string;
  cert_name?: string;
  cert_expiry?: string;
  days_until_cert_expiry?: number;
  test_mode: boolean;
  accepted_transaction_types: TransactionType[];
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
}

export interface EDITransaction {
  id: UUID;
  tenant_id: UUID;
  partner_id: UUID;
  partner_name: string;
  filename: string;
  direction: TransactionDirection;
  transaction_type: TransactionType;
  interchange_control_number?: string;
  functional_group_id?: string;
  transaction_count: number;
  status: TransactionStatus;
  validation_errors?: Array<{
    segment: string;
    element: string;
    error_code: string;
    message: string;
  }>;
  raw_preview?: string;
  received_at: ISODateTimeString;
  processed_at?: ISODateTimeString;
  ack_sent_at?: ISODateTimeString;
}

export interface EDIMonitorStats {
  transactions_in_flight: number;
  acceptance_rate_24h: number;
  acceptance_rate_7d: number;
  acceptance_rate_30d: number;
  median_ack_turnaround_ms: number;
  p95_ack_turnaround_ms: number;
  top_rejection_codes: Array<{
    code: string;
    description: string;
    count: number;
  }>;
  volume_trend_30d: Array<{ date: string; inbound: number; outbound: number }>;
}

export interface CertAlert {
  id: UUID;
  partner_id: UUID;
  partner_name: string;
  cert_name: string;
  expires_at: string;
  days_until_expiry: number;
}
