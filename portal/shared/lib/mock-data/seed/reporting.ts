import { rngInt, rngPick, isoDate, isoDateTime, makeUUID, PRIMARY_TENANT } from "./prng";
import type { ReportTemplate, GeneratedReport, ScheduledReport } from "@shared/types/reporting";

const FINANCIAL_REPORTS = [
  "Monthly Billing Summary",
  "AP/AR Aging Report",
  "Claims Financial Reconciliation",
  "Invoice Status Dashboard",
  "Payment Batch Summary",
  "NACHA Transmission Report",
  "Revenue Cycle Analysis",
  "Client Fee Schedule Report",
  "Drug Spend by Therapeutic Class",
  "PMPM Trend Analysis",
];

const CLINICAL_REPORTS = [
  "Medication Adherence (PDC)",
  "Generic Dispense Rate by Prescriber",
  "High-Cost Member Report",
  "Star Ratings Drug Categories",
  "Drug Utilization Review",
  "Opioid Monitoring Report",
  "GLP-1 Utilization Trend",
  "Specialty Drug Pipeline",
];

const OPERATIONAL_REPORTS = [
  "Claims Processing SLA",
  "EDI Transaction Volume",
  "Pharmacy Network Performance",
  "Prior Authorization Turnaround",
  "Member Eligibility Audit",
  "Data Quality Scorecard",
  "System Health Summary",
];

const REGULATORY_REPORTS = [
  "HIPAA Audit Log Export",
  "340B Compliance Summary",
  "CMS Part D Attestation",
  "State Medicaid Encounter Report",
  "FWA Detection Summary",
];

const ALL_TEMPLATES = [
  ...FINANCIAL_REPORTS.map((n) => ({ name: n, category: "financial" as const })),
  ...CLINICAL_REPORTS.map((n) => ({ name: n, category: "clinical" as const })),
  ...OPERATIONAL_REPORTS.map((n) => ({ name: n, category: "operational" as const })),
  ...REGULATORY_REPORTS.map((n) => ({ name: n, category: "regulatory" as const })),
];

export const REPORT_TEMPLATES: ReportTemplate[] = ALL_TEMPLATES.slice(0, 30).map((t, i) => ({
  id: makeUUID(40000 + i),
  tenant_id: PRIMARY_TENANT,
  name: t.name,
  description: `Standard ${t.category} report — ${t.name}. Covers all active programs and clients within the selected date range.`,
  category: t.category,
  parameters: [
    {
      key: "date_range",
      label: "Date Range",
      type: "date_range" as const,
      required: true,
      default_value: { start: isoDate(-30).substring(0, 10), end: isoDate(0).substring(0, 10) },
    },
    {
      key: "client",
      label: "Client",
      type: "select" as const,
      required: false,
      options: [
        { value: "all", label: "All Clients" },
        { value: "acme", label: "Acme Health Partners" },
        { value: "bluestar", label: "BlueStar Benefits Group" },
        { value: "clearpath", label: "ClearPath Managed Care" },
      ],
      default_value: "all",
    },
    {
      key: "program",
      label: "Program",
      type: "select" as const,
      required: false,
      options: [
        { value: "all", label: "All Programs" },
        { value: "commercial", label: "Commercial PPO" },
        { value: "medicare", label: "Medicare Part D" },
        { value: "medicaid", label: "Medicaid MCO" },
      ],
      default_value: "all",
    },
    ...(t.category === "clinical"
      ? [
          {
            key: "drug",
            label: "Drug / Class",
            type: "select" as const,
            required: false,
            options: [
              { value: "all", label: "All" },
              { value: "statins", label: "Statins" },
              { value: "glp1", label: "GLP-1 Agonists" },
              { value: "biologics", label: "Biologics" },
            ],
            default_value: "all",
          },
        ]
      : []),
  ],
  available_formats: ["pdf", "excel", "csv"],
  estimated_duration_seconds: rngInt(5, 120),
  is_favorite: i % 5 === 0,
  last_generated: i % 3 !== 0 ? isoDate(-(rngInt(1, 14))) : undefined,
  tags: [t.category, ...(i % 4 === 0 ? ["scheduled"] : []), ...(i % 7 === 0 ? ["favorite"] : [])],
}));

export const GENERATED_REPORTS: GeneratedReport[] = Array.from({ length: 15 }, (_, i) => {
  const template = REPORT_TEMPLATES[i % REPORT_TEMPLATES.length];
  const status = rngPick(["ready", "ready", "ready", "generating", "failed"] as const);
  const createdAt = isoDate(-(i * 3));

  return {
    id: makeUUID(41000 + i),
    tenant_id: PRIMARY_TENANT,
    template_id: template.id,
    template_name: template.name,
    status,
    format: rngPick(["pdf", "excel", "csv"] as const),
    parameters: { date_range: { start: isoDate(-30).substring(0, 10), end: isoDate(0).substring(0, 10) }, client: "all" },
    download_url: status === "ready" ? "#" : undefined,
    share_url: status === "ready" ? "#" : undefined,
    expires_at: status === "ready" ? isoDate(7) : undefined,
    file_size_bytes: status === "ready" ? rngInt(50000, 5000000) : undefined,
    generated_at: status === "ready" ? isoDate(-(i * 3) + 1) : undefined,
    created_at: createdAt,
    created_by_name: rngPick(["Sarah Chen", "Marcus Rivera", "Priya Nair", "James Okafor"]),
  };
});

export const SCHEDULED_REPORTS: ScheduledReport[] = Array.from({ length: 12 }, (_, i) => {
  const template = REPORT_TEMPLATES[i % REPORT_TEMPLATES.length];
  const frequency = rngPick(["daily", "weekly", "monthly"] as const);
  const isActive = i % 4 !== 0;

  return {
    id: makeUUID(42000 + i),
    tenant_id: PRIMARY_TENANT,
    template_id: template.id,
    template_name: template.name,
    frequency,
    day_of_week: frequency === "weekly" ? rngInt(1, 5) : undefined,
    day_of_month: frequency === "monthly" ? rngInt(1, 28) : undefined,
    hour: rngInt(6, 9),
    minute: rngPick([0, 15, 30, 45]),
    format: rngPick(["pdf", "excel"] as const),
    recipients: [
      `exec${i}@clientdomain.com`,
      "finance@clientdomain.com",
      ...(i % 3 === 0 ? ["compliance@clientdomain.com"] : []),
    ],
    parameters: { date_range: "last_30_days", client: "all" },
    is_active: isActive,
    last_run: isActive ? isoDate(-(rngInt(1, 7))) : undefined,
    next_run: isActive ? isoDate(rngInt(1, 7)) : undefined,
    last_status: isActive ? (i % 8 === 0 ? "failed" : "success") : undefined,
    created_at: isoDate(-(60 + i * 5)),
  };
});

export const BUILDER_METRICS = [
  { key: "total_claims", label: "Total Claims", type: "count", category: "billing" },
  { key: "total_ap_amount", label: "Total AP Amount", type: "money", category: "billing" },
  { key: "total_ar_amount", label: "Total AR Amount", type: "money", category: "billing" },
  { key: "generic_dispense_rate", label: "Generic Dispense Rate", type: "percent", category: "clinical" },
  { key: "pdc_score", label: "PDC Score", type: "percent", category: "clinical" },
  { key: "pmpm", label: "PMPM", type: "money", category: "financial" },
  { key: "flags_count", label: "FWA Flags", type: "count", category: "fwa" },
  { key: "recovery_amount", label: "Recovery Amount", type: "money", category: "fwa" },
];

export const BUILDER_DIMENSIONS = [
  { key: "client", label: "Client", type: "dimension" },
  { key: "program", label: "Program", type: "dimension" },
  { key: "drug_class", label: "Drug Class", type: "dimension" },
  { key: "pharmacy_type", label: "Pharmacy Type", type: "dimension" },
  { key: "prescriber_specialty", label: "Prescriber Specialty", type: "dimension" },
  { key: "state", label: "State", type: "dimension" },
  { key: "month", label: "Month", type: "time" },
  { key: "quarter", label: "Quarter", type: "time" },
];
