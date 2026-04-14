/**
 * API base URLs per module — all from environment variables with localhost defaults.
 * Never hardcode production URLs here.
 */
export const API_URLS = {
  corePlatform:
    process.env.NEXT_PUBLIC_CORE_PLATFORM_URL ?? "http://localhost:8000",
  billing: process.env.NEXT_PUBLIC_BILLING_URL ?? "http://localhost:8001",
  payments: process.env.NEXT_PUBLIC_PAYMENTS_URL ?? "http://localhost:8002",
  reclaimrx: process.env.NEXT_PUBLIC_RECLAIMRX_URL ?? "http://localhost:8003",
  reporting: process.env.NEXT_PUBLIC_REPORTING_URL ?? "http://localhost:8004",
  edi: process.env.NEXT_PUBLIC_EDI_URL ?? "http://localhost:8005",
  medicalClaims:
    process.env.NEXT_PUBLIC_MEDICAL_CLAIMS_URL ?? "http://localhost:8006",
  aiNlp: process.env.NEXT_PUBLIC_AI_NLP_URL ?? "http://localhost:8007",
  dataiq: process.env.NEXT_PUBLIC_DATAIQ_URL ?? "http://localhost:8008",
  pharmacyDirectory:
    process.env.NEXT_PUBLIC_PHARMACY_DIR_URL ?? "http://localhost:8009",
  prescriberDirectory:
    process.env.NEXT_PUBLIC_PRESCRIBER_DIR_URL ?? "http://localhost:8010",
  drugDatabase:
    process.env.NEXT_PUBLIC_DRUG_DATABASE_URL ?? "http://localhost:8011",
  memberManagement:
    process.env.NEXT_PUBLIC_MEMBER_MGMT_URL ?? "http://localhost:8012",
} as const;

export type ApiModule = keyof typeof API_URLS;

/** Feature flags keyed by env var. */
export const FEATURE_FLAGS = {
  planDesign: process.env.NEXT_PUBLIC_FF_PLAN_DESIGN === "true",
  adjudication: process.env.NEXT_PUBLIC_FF_ADJUDICATION === "true",
  priorAuth: process.env.NEXT_PUBLIC_FF_PRIOR_AUTH === "true",
  switchConnectivity: process.env.NEXT_PUBLIC_FF_SWITCH === "true",
  rebateManagement: process.env.NEXT_PUBLIC_FF_REBATE_MGMT === "true",
} as const;

export type FeatureFlag = keyof typeof FEATURE_FLAGS;

/** Session config */
export const SESSION_CONFIG = {
  idleTimeoutMs: 15 * 60 * 1000, // 15 minutes
  warningBeforeTimeoutMs: 2 * 60 * 1000, // 2 minutes warning
  maxConcurrentSessions: 5,
  refreshThresholdMs: 60 * 1000, // refresh token if expires within 1 min
} as const;

/** Approval thresholds (dollars as string — always use Decimal-safe string comparison) */
export const APPROVAL_THRESHOLDS = {
  billingCycle: "1000000.00",
  nachaTransmission: "500000.00",
  paymentBatch: "500000.00",
  clientFeeChange: "0.00", // any change
  tenantConfigChange: "0.00", // any change
  userRoleElevation: "0.00", // any change
} as const;

/** Dashboard preset keys */
export const DASHBOARD_PRESETS = ["billing_ops", "fwa_investigation", "executive", "system_admin"] as const;
export type DashboardPreset = (typeof DASHBOARD_PRESETS)[number];

/** Undo windows (ms) */
export const UNDO_WINDOWS = {
  billingCycleApproval: 30_000,
  claimStatusChange: 5 * 60_000,
  bulkAction: 30_000,
} as const;
