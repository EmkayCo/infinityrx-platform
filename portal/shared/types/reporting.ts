import type { UUID, ISODateTimeString } from "./common";

export type ReportCategory =
  | "financial"
  | "clinical"
  | "operational"
  | "regulatory";

export type ReportFormat = "pdf" | "excel" | "csv" | "html";

export type ScheduleFrequency = "daily" | "weekly" | "monthly";

export interface ReportParameter {
  key: string;
  label: string;
  type:
    | "date_range"
    | "date"
    | "text"
    | "select"
    | "multi_select"
    | "boolean"
    | "number";
  required: boolean;
  default_value?: unknown;
  options?: Array<{ value: string; label: string }>;
  placeholder?: string;
}

export interface ReportTemplate {
  id: UUID;
  tenant_id: UUID;
  name: string;
  description: string;
  category: ReportCategory;
  parameters: ReportParameter[];
  available_formats: ReportFormat[];
  estimated_duration_seconds?: number;
  is_favorite?: boolean;
  last_generated?: ISODateTimeString;
  tags?: string[];
}

export interface GeneratedReport {
  id: UUID;
  tenant_id: UUID;
  template_id: UUID;
  template_name: string;
  status: "pending" | "generating" | "ready" | "failed";
  format: ReportFormat;
  parameters: Record<string, unknown>;
  download_url?: string;
  share_url?: string;
  expires_at?: ISODateTimeString;
  file_size_bytes?: number;
  generated_at?: ISODateTimeString;
  created_at: ISODateTimeString;
  created_by_name?: string;
}

export interface ScheduledReport {
  id: UUID;
  tenant_id: UUID;
  template_id: UUID;
  template_name: string;
  frequency: ScheduleFrequency;
  day_of_week?: number;
  day_of_month?: number;
  hour: number;
  minute: number;
  format: ReportFormat;
  recipients: string[];
  parameters: Record<string, unknown>;
  is_active: boolean;
  last_run?: ISODateTimeString;
  next_run?: ISODateTimeString;
  last_status?: "success" | "failed";
  created_at: ISODateTimeString;
}
