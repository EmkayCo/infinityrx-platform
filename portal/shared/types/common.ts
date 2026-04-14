/**
 * Money is always serialized as a string from the backend (Decimal serialized)
 * and must be treated as such throughout the frontend.
 * Never use number for money amounts.
 */
export type Money = string;

export type UUID = string;

export type ISODateString = string;

export type ISODateTimeString = string;

export interface TimeRange {
  start: ISODateTimeString;
  end: ISODateTimeString;
}

export type Nullable<T> = T | null;

export type Optional<T> = T | undefined;

export interface NamedEntity {
  id: UUID;
  name: string;
}

export interface AuditFields {
  created_at: ISODateTimeString;
  updated_at: ISODateTimeString;
  created_by: UUID;
  updated_by: UUID;
  version: number;
}

export type Status = "active" | "inactive" | "pending" | "error" | "processing";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface Notification {
  id: UUID;
  type: string;
  severity: Severity;
  title: string;
  message: string;
  read: boolean;
  created_at: ISODateTimeString;
  entity_type?: string;
  entity_id?: UUID;
  link?: string;
}

export interface ActivityEvent {
  id: UUID;
  tenant_id: UUID;
  user_id: UUID;
  user_name: string;
  module: string;
  action: string;
  description: string;
  severity: Severity;
  entity_type?: string;
  entity_id?: UUID;
  entity_link?: string;
  occurred_at: ISODateTimeString;
  amount?: Money;
}

export interface ServiceHealth {
  service: string;
  status: "healthy" | "degraded" | "unhealthy";
  latency_ms?: number;
  last_checked: ISODateTimeString;
  error?: string;
}
