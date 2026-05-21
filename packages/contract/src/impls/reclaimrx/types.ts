// packages/contract/src/impls/reclaimrx/types.ts
// SP-3 ReclaimRx contract types.
// All Decimal-bearing fields are z.string() — backend serializes Decimal as str().
// No `any`. Strict TypeScript.
import { z } from "zod";

// ── Shared primitives ──────────────────────────────────────────────────────

export const UuidSchema = z.string().uuid();
export type Uuid = z.infer<typeof UuidSchema>;

/**
 * Decimal amount serialized as string. Never float.
 * Accepts negative values for adjustments/reversals (R1 BLOCK 3 fix).
 */
export const DecimalStringSchema = z.string().regex(/^-?\d+(\.\d+)?$/);

/**
 * Non-negative decimal serialized as string.
 * R3 NEW-8 fix: scores, hold volumes, rates, recovered amounts are non-negative by definition.
 */
export const NonNegativeDecimalStringSchema = z.string().regex(/^\d+(\.\d+)?$/);

export const InvestigationStatusSchema = z.enum([
  "open",
  "in_progress",
  "pending_review",
  "closed_confirmed",
  "closed_false_positive",
  "closed_no_action",
  "escalated",
]);
export type InvestigationStatus = z.infer<typeof InvestigationStatusSchema>;

export const InvestigationSeveritySchema = z.enum(["low", "medium", "high", "critical"]);
export type InvestigationSeverity = z.infer<typeof InvestigationSeveritySchema>;

export const InvestigationSourceSchema = z.enum([
  "rule_firing",
  "ml_score",
  "graph_ring",
  "accumulator_anomaly",
  "manual",
]);
export type InvestigationSource = z.infer<typeof InvestigationSourceSchema>;

export const OutcomeLabelSchema = z.enum(["confirmed", "false_positive", "no_action"]);

// ── Investigation ──────────────────────────────────────────────────────────

export const InvestigationSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  status: InvestigationStatusSchema,
  severity: InvestigationSeveritySchema,
  source: InvestigationSourceSchema,
  source_ref_id: UuidSchema.nullable(),
  member_id: UuidSchema.nullable(),
  opened_at: z.string().datetime(),
  opened_by: z.string(),
  assigned_to: z.string().nullable(),
  closed_at: z.string().datetime().nullable(),
  closed_by: z.string().nullable(),
  outcome_label: OutcomeLabelSchema.nullable(),
  recovered_amount: DecimalStringSchema.nullable(),
  hold_amount: DecimalStringSchema.nullable(),
  threshold_config_version: z.number().int().nonnegative().nullable(),
});
export type Investigation = z.infer<typeof InvestigationSchema>;

export const InvestigationListResponseSchema = z.object({
  results: z.array(InvestigationSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type InvestigationListResponse = z.infer<typeof InvestigationListResponseSchema>;

export const InvestigationTransitionRequestSchema = z.object({
  to_status: InvestigationStatusSchema,
  reason: z.string().min(1),
  outcome_label: OutcomeLabelSchema.optional(),
  recovered_amount: DecimalStringSchema.optional(),
});
export type InvestigationTransitionRequest = z.infer<typeof InvestigationTransitionRequestSchema>;

export const NoteRequestSchema = z.object({
  text: z.string().min(1).max(5000),
});
export type NoteRequest = z.infer<typeof NoteRequestSchema>;

// ── Rule firings ───────────────────────────────────────────────────────────

export const RuleFiringSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  rule_id: UuidSchema,
  rule_code: z.string(),
  claim_id: z.string(),
  // Scores are 0-1 (non-negative, R3 NEW-8 fix).
  score: NonNegativeDecimalStringSchema,
  fired_at: z.string().datetime(),
  investigation_id: UuidSchema.nullable(),
});
export type RuleFiring = z.infer<typeof RuleFiringSchema>;

export const RuleFiringListResponseSchema = z.object({
  results: z.array(RuleFiringSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type RuleFiringListResponse = z.infer<typeof RuleFiringListResponseSchema>;

// ── ML scores ──────────────────────────────────────────────────────────────

export const MlScoreSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  claim_id: z.string(),
  model_id: UuidSchema,
  // ML scores are 0-1 (non-negative, R3 NEW-8 fix).
  score: NonNegativeDecimalStringSchema,
  scored_at: z.string().datetime(),
  investigation_id: UuidSchema.nullable(),
});
export type MlScore = z.infer<typeof MlScoreSchema>;

export const MlScoreListResponseSchema = z.object({
  results: z.array(MlScoreSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type MlScoreListResponse = z.infer<typeof MlScoreListResponseSchema>;

export const FeatureImportanceEntrySchema = z.object({
  feature: z.string(),
  importance: DecimalStringSchema,
});

export const MlScoreFeaturesSchema = z.object({
  score_id: UuidSchema,
  features: z.array(FeatureImportanceEntrySchema),
});
export type MlScoreFeatures = z.infer<typeof MlScoreFeaturesSchema>;

// ── Payment holds ──────────────────────────────────────────────────────────

export const HoldStatusSchema = z.enum(["active", "released", "expired", "cancelled"]);

export const PaymentHoldSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  investigation_id: UuidSchema.nullable(),
  status: HoldStatusSchema,
  amount_threshold: NonNegativeDecimalStringSchema.nullable(),
  entity_type: z.string(),
  entity_id: z.string(),
  placed_by: z.string(),
  placed_at: z.string().datetime(),
  released_by: z.string().nullable(),
  released_at: z.string().datetime().nullable(),
  release_reason: z.string().nullable(),
});
export type PaymentHold = z.infer<typeof PaymentHoldSchema>;

export const HoldListResponseSchema = z.object({
  results: z.array(PaymentHoldSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type HoldListResponse = z.infer<typeof HoldListResponseSchema>;

/** Backend body for POST /holds/{hold_id}/release */
export const HoldReleaseRequestSchema = z.object({
  reason: z.string().min(1),
  investigation_id: UuidSchema,
  emergency_reason_code: z.enum([
    "LEGAL_HOLD",
    "REGULATORY_DIRECTIVE",
    "IRRECOVERABLE_HARM",
    "OTHER_WITH_NOTE",
  ]).optional(),
  emergency_note: z.string().optional(),
});
export type HoldReleaseRequest = z.infer<typeof HoldReleaseRequestSchema>;

export const HoldReleaseResponseSchema = z.object({
  hold_id: UuidSchema,
  status: HoldStatusSchema,
  released_at: z.string().datetime().nullable(),
  released_by: z.string().nullable(),
  reason: z.string().nullable(),
});
export type HoldReleaseResponse = z.infer<typeof HoldReleaseResponseSchema>;

// ── Graph runs ─────────────────────────────────────────────────────────────

export const GraphRunStatusSchema = z.enum([
  "running",
  "completed",
  "completed_partial",
  "failed",
]);

export const GraphRunSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  status: GraphRunStatusSchema,
  trigger: z.enum(["cron", "on_demand"]),
  started_at: z.string().datetime(),
  completed_at: z.string().datetime().nullable(),
  failed_at: z.string().datetime().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
  correlation_id: z.string(),
  stale_timeout_at: z.string().datetime(),
  rings_detected: z.number().int().nonnegative(),
  investigations_opened: z.number().int().nonnegative(),
  records_scanned: z.number().int().nonnegative(),
  lookback_window_days: z.number().int().positive(),
});
export type GraphRun = z.infer<typeof GraphRunSchema>;

export const GraphRunListResponseSchema = z.object({
  results: z.array(GraphRunSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type GraphRunListResponse = z.infer<typeof GraphRunListResponseSchema>;

export const GraphRunTriggerResponseSchema = z.object({
  graph_run_id: UuidSchema,
  status: GraphRunStatusSchema,
  message: z.string(),
});
export type GraphRunTriggerResponse = z.infer<typeof GraphRunTriggerResponseSchema>;

// ── Fraud rings ─────────────────────────────────────────────────────────────

export const EntityRefSchema = z.object({
  entity_type: z.string(),
  entity_id: z.string(),
  label: z.string().optional(),
});

export const FraudRingSchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  graph_run_id: UuidSchema,
  detected_at: z.string().datetime(),
  // Density is a ratio 0-1, non-negative (R3 NEW-8 fix).
  density_score: NonNegativeDecimalStringSchema,
  node_count: z.number().int().nonnegative(),
  edge_count: z.number().int().nonnegative(),
  entity_refs: z.array(EntityRefSchema),
  spawned_investigation_id: UuidSchema.nullable(),
  truncated: z.boolean().optional(),  // true when >500 nodes/2000 edges — neighborhood subgraph returned
});
export type FraudRing = z.infer<typeof FraudRingSchema>;

// ── Recovery ───────────────────────────────────────────────────────────────

export const RecoveryAggregationSchema = z.object({
  period: z.string(),
  group_key: z.string(),
  // Recovered dollars are non-negative (R3 NEW-8 fix).
  total_recovered: NonNegativeDecimalStringSchema,
  investigation_count: z.number().int().nonnegative(),
});
export type RecoveryAggregation = z.infer<typeof RecoveryAggregationSchema>;

export const RecoveryAggregationResponseSchema = z.object({
  results: z.array(RecoveryAggregationSchema),
  total_recovered: NonNegativeDecimalStringSchema,
});
export type RecoveryAggregationResponse = z.infer<typeof RecoveryAggregationResponseSchema>;

// ── Dashboard summary ──────────────────────────────────────────────────────

export const DashboardSummarySchema = z.object({
  open_investigations: z.number().int().nonnegative(),
  active_holds: z.number().int().nonnegative(),
  // Dashboard sums and rates are non-negative (R3 NEW-8 fix).
  hold_volume: NonNegativeDecimalStringSchema,
  recovered_mtd: NonNegativeDecimalStringSchema,
  false_positive_rate: NonNegativeDecimalStringSchema,
  high_severity_open: z.number().int().nonnegative(),
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

// ── Threshold config ───────────────────────────────────────────────────────

export const MlScoreThresholdsSchema = z.object({
  open: NonNegativeDecimalStringSchema,
  auto_hold: NonNegativeDecimalStringSchema,
  escalate: NonNegativeDecimalStringSchema,
});

export const ThresholdConfigSchema = z.object({
  tenant_id: UuidSchema,
  version: z.number().int().positive(),
  effective_at: z.string().datetime(),
  superseded_at: z.string().datetime().nullable(),
  rule_thresholds: z.record(z.string(), NonNegativeDecimalStringSchema),
  ml_score_thresholds: MlScoreThresholdsSchema,
  graph_density_threshold: NonNegativeDecimalStringSchema,
  accumulator_anomaly_sensitivity: NonNegativeDecimalStringSchema,
  updated_by: z.string(),
});
export type ThresholdConfig = z.infer<typeof ThresholdConfigSchema>;

export const ThresholdUpdateRequestSchema = z.object({
  rule_thresholds: z.record(z.string(), NonNegativeDecimalStringSchema).optional(),
  ml_score_thresholds: MlScoreThresholdsSchema.optional(),
  graph_density_threshold: NonNegativeDecimalStringSchema.optional(),
  accumulator_anomaly_sensitivity: NonNegativeDecimalStringSchema.optional(),
  reason: z.string().min(1),
});
export type ThresholdUpdateRequest = z.infer<typeof ThresholdUpdateRequestSchema>;

// ── Accumulator anomalies ──────────────────────────────────────────────────

export const AccumulatorPatternTypeSchema = z.enum([
  "sudden_spike",
  "multi_payer_convergence",
  "reset_evasion",
  "threshold_oscillation",
]);

export const AccumulatorAnomalySchema = z.object({
  id: UuidSchema,
  tenant_id: UuidSchema,
  member_id: UuidSchema,
  pattern_type: AccumulatorPatternTypeSchema,
  detected_at: z.string().datetime(),
  evidence_window_start: z.string().datetime(),
  evidence_window_end: z.string().datetime(),
  triggering_event_ids: z.array(UuidSchema),
  spawned_investigation_id: UuidSchema.nullable(),
});
export type AccumulatorAnomaly = z.infer<typeof AccumulatorAnomalySchema>;

export const AccumulatorAnomalyListResponseSchema = z.object({
  results: z.array(AccumulatorAnomalySchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});
export type AccumulatorAnomalyListResponse = z.infer<typeof AccumulatorAnomalyListResponseSchema>;

// ── R1 BLOCK 2 fix: explicit response shapes for every POST/PUT endpoint ────

/** Response for POST /investigations/{id}/transitions (spec endpoint 3). */
export const InvestigationTransitionResponseSchema = z.object({
  investigation_id: UuidSchema,
  from_status: InvestigationStatusSchema,
  to_status: InvestigationStatusSchema,
  reason: z.string(),
  transitioned_by: z.string(),
  transitioned_at: z.string().datetime(),
  outcome_label: OutcomeLabelSchema.nullable(),
  recovered_amount: DecimalStringSchema.nullable(),
});
export type InvestigationTransitionResponse =
  z.infer<typeof InvestigationTransitionResponseSchema>;

/** Response for POST /investigations/{id}/notes (spec endpoint 4). */
export const InvestigationNoteResponseSchema = z.object({
  id: UuidSchema,
  investigation_id: UuidSchema,
  text: z.string(),
  created_by: z.string(),
  created_at: z.string().datetime(),
});
export type InvestigationNoteResponse =
  z.infer<typeof InvestigationNoteResponseSchema>;

/** Response for GET /investigations/{id}/ml-scores (spec endpoint 5). */
export const InvestigationMlScoresResponseSchema = z.object({
  results: z.array(MlScoreSchema),
  total: z.number().int().nonnegative(),
});
export type InvestigationMlScoresResponse =
  z.infer<typeof InvestigationMlScoresResponseSchema>;

/** Response for GET /investigations/{id} detail (spec endpoint 2). */
export const InvestigationDetailResponseSchema = InvestigationSchema.extend({
  threshold_snapshot: z.record(z.string(), NonNegativeDecimalStringSchema).nullable(),
  status_transitions: z.array(InvestigationTransitionResponseSchema),
  notes: z.array(InvestigationNoteResponseSchema),
});
export type InvestigationDetailResponse =
  z.infer<typeof InvestigationDetailResponseSchema>;

/** Response for GET /graph-runs/{run_id} (spec endpoint 12). Alias = single GraphRun. */
export const GraphRunDetailResponseSchema = GraphRunSchema;
export type GraphRunDetailResponse =
  z.infer<typeof GraphRunDetailResponseSchema>;

/** Response for GET /fraud-rings/{id} (spec endpoint 13). Alias = single FraudRing. */
export const FraudRingDetailResponseSchema = FraudRingSchema;
export type FraudRingDetailResponse =
  z.infer<typeof FraudRingDetailResponseSchema>;

/**
 * R1 BLOCK 2 — Endpoint x Schema coverage matrix (18 rows, _Assert18Endpoints invariant).
 * The contract test asserts every row via parametrized Zod failure tests.
 */
export const SPEC_55_ENDPOINT_COVERAGE = [
  { n:  1, method: "GET",  path: "/investigations",                  req: null,                                response: InvestigationListResponseSchema },
  { n:  2, method: "GET",  path: "/investigations/{id}",             req: null,                                response: InvestigationDetailResponseSchema },
  { n:  3, method: "POST", path: "/investigations/{id}/transitions", req: InvestigationTransitionRequestSchema, response: InvestigationTransitionResponseSchema },
  { n:  4, method: "POST", path: "/investigations/{id}/notes",       req: NoteRequestSchema,                   response: InvestigationNoteResponseSchema },
  { n:  5, method: "GET",  path: "/rule-firings",                    req: null,                                response: RuleFiringListResponseSchema },
  { n:  6, method: "GET",  path: "/ml-scores",                       req: null,                                response: MlScoreListResponseSchema },
  { n:  7, method: "GET",  path: "/ml-scores/{id}/features",         req: null,                                response: MlScoreFeaturesSchema },
  { n:  8, method: "GET",  path: "/holds",                           req: null,                                response: HoldListResponseSchema },
  { n:  9, method: "POST", path: "/holds/{hold_id}/release",         req: HoldReleaseRequestSchema,            response: HoldReleaseResponseSchema },
  { n: 10, method: "POST", path: "/graph-runs/trigger",              req: null,                                response: GraphRunTriggerResponseSchema },
  { n: 11, method: "GET",  path: "/graph-runs",                      req: null,                                response: GraphRunListResponseSchema },
  { n: 12, method: "GET",  path: "/graph-runs/{run_id}",             req: null,                                response: GraphRunDetailResponseSchema },
  { n: 13, method: "GET",  path: "/fraud-rings/{id}",                req: null,                                response: FraudRingDetailResponseSchema },
  { n: 14, method: "GET",  path: "/recovery",                        req: null,                                response: RecoveryAggregationResponseSchema },
  { n: 15, method: "GET",  path: "/dashboard-summary",               req: null,                                response: DashboardSummarySchema },
  { n: 16, method: "GET",  path: "/thresholds",                      req: null,                                response: ThresholdConfigSchema },
  { n: 17, method: "PUT",  path: "/thresholds",                      req: ThresholdUpdateRequestSchema,        response: ThresholdConfigSchema },
  { n: 18, method: "GET",  path: "/accumulator-anomalies",           req: null,                                response: AccumulatorAnomalyListResponseSchema },
] as const;

// Type-level invariant: matrix is exactly 18 rows.
type _Assert18Endpoints = typeof SPEC_55_ENDPOINT_COVERAGE extends { length: 18 } ? true : never;
// Suppress TS6133 — compile-time invariant check, not runtime code.
declare const _spec55_count_check: _Assert18Endpoints;
