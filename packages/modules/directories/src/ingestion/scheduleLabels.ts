// src/ingestion/scheduleLabels.ts
// Cron-to-human-readable label mapping for ingestion schedules.
//
// Labels are verified against shared/data_ingestion/scheduler.py DEFAULT_SCHEDULES.
// Only known cron patterns from that dict are mapped — no arbitrary cron parsing.
// Unknown expressions fall back to the raw cron string.

/**
 * Maps cron expressions from DEFAULT_SCHEDULES to human-readable descriptions.
 * Verified against shared/data_ingestion/scheduler.py:27-52 at HEAD.
 */
export const SCHEDULE_LABELS: Readonly<Record<string, string>> = {
  "0 2 * * *": "Daily 2:00 AM",
  "0 3 * * 1": "Weekly Mon 3:00 AM",
  "0 4 1 * *": "Monthly 1st 4:00 AM",
  "0 3 * * 2": "Weekly Tue 3:00 AM",
  "0 4 15 * *": "Monthly 15th 4:00 AM",
  "0 5 15 * *": "Monthly 15th 5:00 AM",
  "0 4 1 1,4,7,10 *": "Quarterly 1st 4:00 AM",
  "0 1 1-7 * 1": "First Mon of month 1:00 AM",
  "0 5 * * 3": "Weekly Wed 5:00 AM",
  "0 6 * * *": "Daily 6:00 AM",
  "0 2 20 * *": "Monthly 20th 2:00 AM",
  "0 6 1 * *": "Monthly 1st 6:00 AM",
  "0 3 20 * *": "Monthly 20th 3:00 AM",
  "0 2 15 4,10 *": "Apr/Oct 15th 2:00 AM",
  "0 3 15 1,4,7,10 *": "Quarterly 15th 3:00 AM",
};

/**
 * Returns a human-readable schedule description.
 * - null cron → "Manual only"
 * - known cron → label from SCHEDULE_LABELS
 * - unknown cron → raw expression (graceful fallback)
 */
export function formatScheduleLabel(cronExpression: string | null): string {
  if (cronExpression === null) return "Manual only";
  return SCHEDULE_LABELS[cronExpression] ?? cronExpression;
}

/** Cluster assignment for each source key. Used in IngestionConsolePage table. */
export const SOURCE_CLUSTER: Readonly<Record<string, string>> = {
  nppes: "Prescribers",
  nppes_monthly: "Prescribers",
  nppes_deactivation: "Prescribers",
  ncpdp: "Pharmacies",
  fda_ndc: "Drugs",
  fda_orange_book: "Drugs",
  fda_purple_book: "Drugs",
  fda_drug_shortages: "Drugs",
  fda_rems: "Drugs",
  rxnorm: "Drugs",
  hcpcs: "Codes",
  icd10_cm: "Codes",
  cms_asp: "Pricing",
  cms_nadac: "Pricing",
  state_medicaid_bins: "Pricing",
  cms_opt_out: "Exclusions",
  ofac_sdn: "Exclusions",
  sam_exclusions: "Exclusions",
  oig_leie: "Exclusions",
  dea_registrations: "Prescribers",
  // Non-loader sources (display-only rows)
  bpg: "Pricing",
  fdb: "Drugs",
};
