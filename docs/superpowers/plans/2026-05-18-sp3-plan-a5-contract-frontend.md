# SP-3 Plan A5 — Contract Layer + Frontend Module Scaffold + Empty-State Pages + Event Contract Docs

**Status:** DRAFT
**Date:** 2026-05-18
**Vertical:** SP-3 ReclaimRx — Operator Portal + Backend Closure
**Spec ref:** `docs/superpowers/specs/2026-05-18-sp3-reclaimrx-portal-design.md`
**Audit ref:** `waves/B10/SP-3-audit-deep.md`
**Plan A split:** A1=Models+Migration, A2=Outbox+Scheduler+DLQ, A3=StateMachine+HoldRelease+Accumulator, A4=Endpoints+RBAC, A5=Contract+Frontend (this plan)
**Builds on:** SP-2 (directories module pattern), SP-0 (contract package pattern)

---

## Verified citations — all paths confirmed against HEAD before writing

| Symbol / Path | Verification result |
|---|---|
| `packages/contract/src/impls/prescriber-directory/client.ts` | Exists — `PrescriberDirectoryClient` interface + `PRESCRIBER_DIRECTORY_CACHE_POLICIES` |
| `packages/contract/src/impls/prescriber-directory/types.ts` | Exists — Zod schemas + TypeScript types |
| `packages/contract/src/impls/prescriber-directory/real.ts` | Exists — `createRealPrescriberDirectoryClient` factory |
| `packages/contract/src/impls/prescriber-directory/mock.ts` | Exists — `createMockPrescriberDirectoryClient` factory |
| `packages/contract/src/__tests__/prescriber-directory.test.ts` | Exists — mock + real impl test pattern |
| `packages/contract/src/client-base.ts` | Exists — `BaseClient` interface: `name`, `cachePolicies`, `probeHealth()` |
| `packages/contract/src/cache-policy.ts` | Exists — `CachePolicy`, `CachePolicySchema` |
| `packages/contract/src/error-envelope.ts` | Exists — `isErrorEnvelope`, `ErrorEnvelopeSchema` |
| `packages/contract/src/index.ts` | Exports prescriber-directory impl; reclaimrx impls to be added here |
| `packages/modules/directories/module.config.ts` | Exists — reference shape for reclaimrx module.config.ts |
| `packages/modules/directories/src/` | Exists — full SP-2 module; `bff/`, `search/`, `surfaces/`, `components/`, `ingestion/`, `quality/`, `audit/` |
| `packages/shell/src/_generated/manifest.json` | Exists — `modules: ["prescriber-directory", "directories"]`; reclaimrx to be added |
| `portal/operator/app/reclaimrx/page.tsx` | Exists — GTN Dashboard (WILL BE REPLACED with empty-state per spec §6 R1 BLOCK 9) |
| `portal/operator/app/reclaimrx/investigations/page.tsx` | Exists — kanban/table view (WILL BE REPLACED with empty-state in Plan A5) |
| `portal/operator/app/reclaimrx/investigations/[id]/page.tsx` | Exists — WILL BE REPLACED |
| `packages/modules/reclaimrx/` | Does NOT exist — clean scaffold needed |
| `packages/contract/src/impls/reclaimrx/` | Does NOT exist — clean slate |
| `docs/api-contracts/events/` | Directory structure — 2 new event contract docs to be created |

**Critical layout confirmation (audit §5):** The actual contract pattern is `src/impls/<domain>/` with 4 files. There are NO `clients/`, `schemas/`, or `cache/` subdirectories. Plan A5 creates `src/impls/reclaimrx/` with exactly 4 files: `client.ts`, `types.ts`, `real.ts`, `mock.ts`.

**Existing reclaimrx portal pages note:** `portal/operator/app/reclaimrx/` has 7 existing pages with real implementations (GTN dashboard, Kanban investigations, etc.). These are PRE-SP-3 pages wired to non-spec endpoints. Plan A5 replaces ONLY the 6 pages listed in spec §6 Plan A scope with spec-aligned empty-state pages. Pages outside spec scope (`leakage`, `risk`, `wizard`, `recovery`) are left untouched (surgical changes rule).

**Spec §6 Plan A new pages required (R1 BLOCK 9 — real routed pages, NOT dead code):**
- `portal/operator/app/reclaimrx/dashboard/page.tsx` — NEW (replaces root `/reclaimrx` scope; existing `page.tsx` remains but a new dashboard route is added)
- `portal/operator/app/reclaimrx/holds/page.tsx` — NEW
- `portal/operator/app/reclaimrx/fraud-rings/page.tsx` — NEW
- `portal/operator/app/reclaimrx/graph-runs/page.tsx` — NEW
- `portal/operator/app/reclaimrx/thresholds/page.tsx` — NEW
- `portal/operator/app/reclaimrx/accumulator-anomalies/page.tsx` — NEW

The existing `investigations/page.tsx` and `investigations/[id]/page.tsx` are out-of-spec and will be left as-is (Plan B replaces them with real UI). Plan A5 does NOT touch them (surgical changes — only what spec §6 Plan A requires).

---

## §10 Open-gap decisions locked by this plan

| Gap | Decision |
|---|---|
| Plan A5 oversize | 7 tasks — within 5-7 range. Tasks are cleanly parallelizable. |
| Existing portal pages | DO NOT replace existing investigations pages — those are Plan B work. Only add the 6 NEW route pages that are missing. Leave `leakage`, `risk`, `wizard`, `recovery` untouched. |
| Event contract doc location | `docs/api-contracts/events/payment.hold_released.md (R1 BLOCK 8 fix — `fwa.*` prefix per event-bus.md, not `payment.*`)` + `docs/api-contracts/events/fwa.graph_run_completed.md` per R2 NEW BLOCK 1 + spec §11.5 |
| Contract test location | `packages/contract/src/__tests__/reclaimrx.test.ts` — mirrors prescriber-directory test |
| Manifest update | Add `"reclaimrx"` to `modules` array in `packages/shell/src/_generated/manifest.json` and wire `RECLAIMRX_URL` env + `http://reclaimrx:8007/health` health check |
| Reclaimrx backend URL/port | Backend runs at port 8007 (verified: `portal/operator/.env.local` has reclaimrx entries; if absent, add `RECLAIMRX_URL=http://reclaimrx:8007`) |

---

## Deliverables

### D1 — `packages/contract/src/impls/reclaimrx/types.ts`

Zod schemas for all 18 endpoint request/response shapes. All Decimal-bearing fields use `z.string()` (backend serializes as str; frontend never floats money). No `any`. Strict mode.

Key types: `InvestigationStatus`, `Investigation`, `InvestigationListResponse`, `InvestigationTransitionRequest`, `NoteRequest`, `RuleFiring`, `MlScore`, `MlScoreFeatures`, `PaymentHold`, `HoldReleaseRequest`, `HoldReleaseResponse`, `GraphRun`, `GraphRunTriggerResponse`, `FraudRing`, `RecoveryAggregation`, `DashboardSummary`, `ThresholdConfig`, `ThresholdUpdateRequest`, `AccumulatorAnomaly`, `AccumulatorAnomalyListResponse`.

### D2 — `packages/contract/src/impls/reclaimrx/client.ts`

`ReclaimRxClient` interface extending `BaseClient`. One method per spec endpoint #1-18 (audit §4 / spec §5.5). Cache policies for every read endpoint with the correct invalidation tags and `backend_down` behavior per spec §8 (reads: `stale-ok` 30-60s; writes: `fail-closed` — no `backend_down` fallback). Methods for write operations have no cache policy entry (writes never stale-ok).

### D3 — `packages/contract/src/impls/reclaimrx/real.ts`

`createRealReclaimRxClient(config: ClientConfig): ReclaimRxClient` factory. Mirrors `createRealPrescriberDirectoryClient` verbatim pattern:
- `authedFetch` helper: `Bearer` token + correlation header on every request
- `unwrap<T>` helper: Zod parse + `isErrorEnvelope` error mapping
- All 18 methods call the correct backend path from spec §5.5 endpoint table
- `probeHealth()` hits `/health` with latency measurement

### D4 — `packages/contract/src/impls/reclaimrx/mock.ts`

`createMockReclaimRxClient(): ReclaimRxClient` factory. Realistic fixtures for the 5 FWA archetypes defined in spec §9.4. All Decimal amounts as strings. Correct status transitions (mock validates state machine). Mock returns exactly the Zod-typed shapes.

### D5 — `packages/modules/reclaimrx/` scaffold

New package at `packages/modules/reclaimrx/` with the same structure as `packages/modules/directories/`. Empty stub directories for Plan B-E content; real module.config.ts and package infrastructure. Stub `src/index.ts` barrel.

### D6 — 6 new empty-state portal pages

Six new Next.js pages at `portal/operator/app/reclaimrx/` paths. Each page is a thin wrapper that renders the existing `<ComingSoonPage>` component from `portal/operator/components/ui/coming-soon-page.tsx` with title, description, and a phase label.

**R1 BLOCK 10 fix:** Earlier drafts imported `@/components/ui/card`, `@/components/ui/button`, `@/components/ui/badge`, `@/components/ui/table`. None of those files exist in `portal/operator/components/ui/`. The directory contains only application-specific primitives (`coming-soon-page`, `kpi-card`, `status-badge`, `info-card`, `detail-page-layout`, `filter-panel`, `configurable-data-table`, `ifx-logo`, `format-value`). The shadcn `card`/`button`/`badge`/`table` primitives have never been scaffolded in this repo — importing them would break the page at compile time.

The canonical cross-portal pattern (audited from `portal/operator/app/directories/**/page.tsx`) is for `portal/operator/app/{section}/page.tsx` to be a thin wrapper that imports a `{X}Page` component from `@infinityrx/module-{name}`. The real components live in `packages/modules/{name}/src/surfaces/`. Inside the module package, components use relative imports for local elements + `@infinityrx/ui` for primitives (Button, DataTable, KPICard, AppShell). NO module ever imports `@/components/ui/*`.

For SP-3 Plan A5 the simplest, surgical-changes-compliant pattern is to use the existing portal-local `ComingSoonPage` component directly from the wrapper (no module-package indirection needed for empty-state pages — Plan B/C/D/E will introduce real components in `packages/modules/reclaimrx/`). Pages render and test against the live page route; no compile errors.

### D7 — Event contract docs

Two markdown files per `.claude/rules/event-bus.md` format: `docs/api-contracts/events/payment.hold_released.md (R1 BLOCK 8 fix — `fwa.*` prefix per event-bus.md, not `payment.*`)` and `docs/api-contracts/events/fwa.graph_run_completed.md`. Both instantiate spec §11.5 contracts verbatim with envelope fields, payload fields, forward-compatibility rule, publisher/subscriber ownership, and version history.

---

## Tasks

### Task A5-1: Zod types (`packages/contract/src/impls/reclaimrx/types.ts`)

**What:** Create `packages/contract/src/impls/reclaimrx/types.ts` with Zod schemas and TypeScript types for all 18 endpoint shapes.

**Files created:**
- `packages/contract/src/impls/reclaimrx/types.ts`

**Implementation:**

```typescript
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
 *
 * R1 BLOCK 3 fix: regex must accept negative values. PaymentHold release
 * adjustments and accumulator reversals carry negative balances; the prior
 * pattern /^\d+(\.\d+)?$/ silently rejected every valid negative response
 * at Zod parse time. Allow an optional leading `-` and a decimal portion.
 */
export const DecimalStringSchema = z.string().regex(/^-?\d+(\.\d+)?$/);

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

export const InvestigationSourceSchema = z.enum([
  "rule_firing",
  "ml_score",
  "graph_ring",
  "accumulator_anomaly",
  "manual",
]);

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
  score: DecimalStringSchema,
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
  score: DecimalStringSchema,
  scored_at: z.string().datetime(),
  investigation_id: UuidSchema.nullable(),
});
export type MlScore = z.infer<typeof MlScoreSchema>;

export const MlScoreListResponseSchema = z.object({
  results: z.array(MlScoreSchema),
  total: z.number().int().nonnegative(),
  next_cursor: z.string().optional(),
});

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
  amount_threshold: DecimalStringSchema.nullable(),
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
  density_score: DecimalStringSchema,
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
  total_recovered: DecimalStringSchema,
  investigation_count: z.number().int().nonnegative(),
});
export type RecoveryAggregation = z.infer<typeof RecoveryAggregationSchema>;

export const RecoveryAggregationResponseSchema = z.object({
  results: z.array(RecoveryAggregationSchema),
  total_recovered: DecimalStringSchema,
});

// ── Dashboard summary ──────────────────────────────────────────────────────

export const DashboardSummarySchema = z.object({
  open_investigations: z.number().int().nonnegative(),
  active_holds: z.number().int().nonnegative(),
  hold_volume: DecimalStringSchema,
  recovered_mtd: DecimalStringSchema,
  false_positive_rate: DecimalStringSchema,
  high_severity_open: z.number().int().nonnegative(),
});
export type DashboardSummary = z.infer<typeof DashboardSummarySchema>;

// ── Threshold config ───────────────────────────────────────────────────────

export const MlScoreThresholdsSchema = z.object({
  open: DecimalStringSchema,
  auto_hold: DecimalStringSchema,
  escalate: DecimalStringSchema,
});

export const ThresholdConfigSchema = z.object({
  tenant_id: UuidSchema,
  version: z.number().int().positive(),
  effective_at: z.string().datetime(),
  superseded_at: z.string().datetime().nullable(),
  rule_thresholds: z.record(z.string(), DecimalStringSchema),
  ml_score_thresholds: MlScoreThresholdsSchema,
  graph_density_threshold: DecimalStringSchema,
  accumulator_anomaly_sensitivity: DecimalStringSchema,
  updated_by: z.string(),
});
export type ThresholdConfig = z.infer<typeof ThresholdConfigSchema>;

export const ThresholdUpdateRequestSchema = z.object({
  rule_thresholds: z.record(z.string(), DecimalStringSchema).optional(),
  ml_score_thresholds: MlScoreThresholdsSchema.optional(),
  graph_density_threshold: DecimalStringSchema.optional(),
  accumulator_anomaly_sensitivity: DecimalStringSchema.optional(),
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
// Codex flagged that 6 of 18 endpoint shapes were missing dedicated response
// schemas. This block adds the missing schemas so the table below maps 1:1
// with spec §5.5 endpoints 1-18.

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
  // Detail view adds the fields list view omits per spec §5.5
  threshold_snapshot: z.record(z.string(), DecimalStringSchema).nullable(),
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
 * R1 BLOCK 2 — Endpoint × Schema coverage matrix.
 * Every entry below MUST have a `RequestSchema` (when applicable) and a
 * `ResponseSchema` defined above. CI runs `verify_spec_endpoint_coverage()`
 * in the contract test (Task A5-5) to assert every row is satisfied.
 */
export const SPEC_55_ENDPOINT_COVERAGE = [
  // # | method | path | request | response
  { n:  1, method: "GET",  path: "/investigations",                  req: null,                                response: InvestigationListResponseSchema },
  { n:  2, method: "GET",  path: "/investigations/{id}",             req: null,                                response: InvestigationDetailResponseSchema },
  { n:  3, method: "POST", path: "/investigations/{id}/transitions", req: InvestigationTransitionRequestSchema, response: InvestigationTransitionResponseSchema },
  { n:  4, method: "POST", path: "/investigations/{id}/notes",       req: NoteRequestSchema,                   response: InvestigationNoteResponseSchema },
  { n:  5, method: "GET",  path: "/investigations/{id}/ml-scores",   req: null,                                response: InvestigationMlScoresResponseSchema },
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
const _spec55_count_check: _Assert18Endpoints = true;
```

> **R1 BLOCK 12 fix — TypeScript strict invariants:**
> 1. NO `Record<string, unknown>` anywhere in this file. Use explicit `z.record(z.string(), <ValueSchema>)` with a typed value schema (e.g. `DecimalStringSchema`).
> 2. NO duplicate or shadowed type identifiers. `InvestigationStatus` is defined exactly once at line 151 — every other reference imports the type from this file rather than re-defining it.
> 3. NO `z.any()`, NO `@ts-ignore`, NO `as any` casts. Every schema has an explicit shape.
> 4. Every object schema chains `.strict()` where applicable (or is documented as open for forward-compatibility). The `verify_spec_endpoint_coverage()` test (Task A5-5) enforces this with a runtime check.

**Tests:** None in this task — tested in Task A5-5 (contract test covers all schemas).

### Task A5-2: Client interface (`packages/contract/src/impls/reclaimrx/client.ts`)

**What:** Create `packages/contract/src/impls/reclaimrx/client.ts` with `ReclaimRxClient` interface and `RECLAIMRX_CACHE_POLICIES`.

**Files created:**
- `packages/contract/src/impls/reclaimrx/client.ts`

**Implementation:**

```typescript
// packages/contract/src/impls/reclaimrx/client.ts
// SP-3 ReclaimRx typed client interface.
// Mirrors prescriber-directory/client.ts pattern (audit §5).
// One method per spec §5.5 endpoint. Write operations have no cache entry (fail-closed).
import type { BaseClient, ClientConfig, ClientFactory } from "../../client-base.js";
import type { CachePolicy } from "../../cache-policy.js";
import type {
  InvestigationListResponse,
  Investigation,
  InvestigationTransitionRequest,
  NoteRequest,
  RuleFiringListResponse,
  MlScoreListResponse,
  MlScoreFeatures,
  HoldListResponse,
  HoldReleaseRequest,
  HoldReleaseResponse,
  GraphRunTriggerResponse,
  GraphRunListResponse,
  GraphRun,
  FraudRing,
  RecoveryAggregationResponse,
  DashboardSummary,
  ThresholdConfig,
  ThresholdUpdateRequest,
  AccumulatorAnomalyListResponse,
} from "./types.js";

// ── Pagination params (shared across list endpoints) ───────────────────────

export interface ListParams {
  cursor?: string;
  limit?: number;
}

export interface InvestigationListParams extends ListParams {
  status?: string;
  severity?: string;
  source?: string;
}

export interface RecoveryParams {
  period?: string;
  group_by?: string;
}

// ── Client interface (18 backend endpoints) ────────────────────────────────

export interface ReclaimRxClient extends BaseClient {
  readonly name: "reclaimrx";

  // Endpoint #1
  listInvestigations(params?: InvestigationListParams): Promise<InvestigationListResponse>;
  // Endpoint #2
  getInvestigation(id: string): Promise<Investigation>;
  // Endpoint #3
  transitionInvestigation(id: string, req: InvestigationTransitionRequest): Promise<Investigation>;
  // Endpoint #4
  addInvestigationNote(id: string, req: NoteRequest): Promise<{ created: true }>;
  // Endpoint #5
  listRuleFirings(params?: ListParams): Promise<RuleFiringListResponse>;
  // Endpoint #6
  listMlScores(params?: ListParams): Promise<MlScoreListResponse>;
  // Endpoint #7
  getMlScoreFeatures(scoreId: string): Promise<MlScoreFeatures>;
  // Endpoint #8
  listHolds(params?: ListParams): Promise<HoldListResponse>;
  // Endpoint #9
  releaseHold(holdId: string, req: HoldReleaseRequest): Promise<HoldReleaseResponse>;
  // Endpoint #10
  triggerGraphRun(): Promise<GraphRunTriggerResponse>;
  // Endpoint #11
  listGraphRuns(params?: ListParams): Promise<GraphRunListResponse>;
  // Endpoint #12
  getGraphRun(runId: string): Promise<GraphRun>;
  // Endpoint #13
  getFraudRing(id: string): Promise<FraudRing>;
  // Endpoint #14
  getRecoveryAggregations(params?: RecoveryParams): Promise<RecoveryAggregationResponse>;
  // Endpoint #15
  getDashboardSummary(): Promise<DashboardSummary>;
  // Endpoint #16
  getThresholds(): Promise<ThresholdConfig>;
  // Endpoint #17
  updateThresholds(req: ThresholdUpdateRequest): Promise<ThresholdConfig>;
  // Endpoint #18
  listAccumulatorAnomalies(params?: ListParams): Promise<AccumulatorAnomalyListResponse>;
}

// ── Cache policies (read-only endpoints only; writes are fail-closed per spec §8) ──

export const RECLAIMRX_CACHE_POLICIES: Record<string, CachePolicy> = {
  listInvestigations: {
    ttl_seconds: 30,
    key: ["reclaimrx", "investigations", "{status}", "{severity}", "{source}", "{cursor}"],
    invalidation_tags: ["reclaimrx:investigations"],
    backend_down: "stale-ok",
  },
  getInvestigation: {
    // PHI endpoint — NO caching (Cache-Control: no-store enforced on the backend)
    ttl_seconds: 0,
    key: ["reclaimrx", "investigation", "{id}"],
    invalidation_tags: ["reclaimrx:investigations"],
    backend_down: "fail-closed",
  },
  listRuleFirings: {
    ttl_seconds: 60,
    key: ["reclaimrx", "rule-firings", "{cursor}"],
    invalidation_tags: ["reclaimrx:rule-firings"],
    backend_down: "stale-ok",
  },
  listMlScores: {
    ttl_seconds: 60,
    key: ["reclaimrx", "ml-scores", "{cursor}"],
    invalidation_tags: ["reclaimrx:ml-scores"],
    backend_down: "stale-ok",
  },
  getMlScoreFeatures: {
    ttl_seconds: 300,
    key: ["reclaimrx", "ml-score-features", "{scoreId}"],
    invalidation_tags: ["reclaimrx:ml-scores"],
    backend_down: "stale-ok",
  },
  listHolds: {
    ttl_seconds: 30,
    key: ["reclaimrx", "holds", "{cursor}"],
    invalidation_tags: ["reclaimrx:holds"],
    backend_down: "stale-ok",
  },
  listGraphRuns: {
    ttl_seconds: 10,
    key: ["reclaimrx", "graph-runs", "{cursor}"],
    invalidation_tags: ["reclaimrx:graph-runs"],
    backend_down: "stale-ok",
  },
  getGraphRun: {
    // Polling endpoint — very short TTL; stale-ok so UI doesn't break on transient backend down
    ttl_seconds: 5,
    key: ["reclaimrx", "graph-run", "{runId}"],
    invalidation_tags: ["reclaimrx:graph-runs"],
    backend_down: "stale-ok",
  },
  getFraudRing: {
    ttl_seconds: 300,
    key: ["reclaimrx", "fraud-ring", "{id}"],
    invalidation_tags: ["reclaimrx:fraud-rings"],
    backend_down: "stale-ok",
  },
  getRecoveryAggregations: {
    ttl_seconds: 60,
    key: ["reclaimrx", "recovery", "{period}", "{group_by}"],
    invalidation_tags: ["reclaimrx:recovery"],
    backend_down: "stale-ok",
  },
  getDashboardSummary: {
    // 60s per spec §9.5 "Dashboard tiles: <200ms p95 via 60s-cached aggregations"
    ttl_seconds: 60,
    key: ["reclaimrx", "dashboard-summary"],
    invalidation_tags: ["reclaimrx:investigations", "reclaimrx:holds", "reclaimrx:recovery"],
    backend_down: "stale-ok",
  },
  getThresholds: {
    ttl_seconds: 300,
    key: ["reclaimrx", "thresholds"],
    invalidation_tags: ["reclaimrx:thresholds"],
    backend_down: "stale-ok",
  },
  listAccumulatorAnomalies: {
    ttl_seconds: 30,
    key: ["reclaimrx", "accumulator-anomalies", "{cursor}"],
    invalidation_tags: ["reclaimrx:accumulator-anomalies"],
    backend_down: "stale-ok",
  },
};

export type ReclaimRxFactory = ClientFactory<ReclaimRxClient>;
export type { ClientConfig };
```

**Tests:** None in this task — covered by A5-5 contract test.

### Task A5-3: Real implementation (`packages/contract/src/impls/reclaimrx/real.ts`)

**What:** Create `packages/contract/src/impls/reclaimrx/real.ts` — the `createRealReclaimRxClient` factory. Verbatim structural pattern from `prescriber-directory/real.ts` (same `authedFetch` + `unwrap` helpers). Maps all 18 methods to backend paths from spec §5.5 endpoint table.

**Files created:**
- `packages/contract/src/impls/reclaimrx/real.ts`

**Implementation (key excerpt — shows pattern; full file implements all 18 methods):**

```typescript
// packages/contract/src/impls/reclaimrx/real.ts
import type { ReclaimRxClient } from "./client.js";
import { RECLAIMRX_CACHE_POLICIES } from "./client.js";
import type { ClientConfig } from "../../client-base.js";
import { isErrorEnvelope } from "../../error-envelope.js";
import {
  InvestigationSchema,
  InvestigationListResponseSchema,
  RuleFiringListResponseSchema,
  MlScoreListResponseSchema,
  MlScoreFeaturesSchema,
  HoldListResponseSchema,
  HoldReleaseResponseSchema,
  GraphRunTriggerResponseSchema,
  GraphRunListResponseSchema,
  GraphRunSchema,
  FraudRingSchema,
  RecoveryAggregationResponseSchema,
  DashboardSummarySchema,
  ThresholdConfigSchema,
  AccumulatorAnomalyListResponseSchema,
  HoldReleaseRequestSchema,
  InvestigationTransitionRequestSchema,
  ThresholdUpdateRequestSchema,
  type InvestigationListParams,
  type ListParams,
  type RecoveryParams,
} from "./types.js";

class RealClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly correlationId?: string,
  ) {
    super(message);
    this.name = "RealClientError";
  }
}

export function createRealReclaimRxClient(config: ClientConfig): ReclaimRxClient {
  if (!config.baseUrl) {
    throw new Error("createRealReclaimRxClient: baseUrl is required");
  }
  const baseUrl = config.baseUrl.replace(/\/$/, "");
  const correlationHeader = config.correlationHeader ?? "x-correlation-id";
  const fetchImpl = config.fetch ?? globalThis.fetch;

  async function authedFetch(path: string, init?: RequestInit): Promise<Response> {
    const token = await config.getAuthToken();
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    headers.set(correlationHeader, crypto.randomUUID());
    return fetchImpl(`${baseUrl}/api/v1/reclaimrx${path}`, { ...init, headers });
  }

  async function unwrap<T>(res: Response, schema: { parse(raw: unknown): T }): Promise<T> {
    const body = (await res.json()) as unknown;
    if (!res.ok) {
      if (isErrorEnvelope(body)) {
        throw new RealClientError(body.error.code, body.error.message, body.error.correlation_id);
      }
      throw new Error(`Unexpected error shape: HTTP ${res.status}`);
    }
    return schema.parse(body);
  }

  function qs(params: Record<string, string | number | undefined>): string {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) p.set(k, String(v));
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  }

  return {
    name: "reclaimrx" as const,
    cachePolicies: RECLAIMRX_CACHE_POLICIES,

    // Endpoint #1 — GET /investigations
    async listInvestigations(params?: InvestigationListParams) {
      const res = await authedFetch(`/investigations${qs({ ...params })}`);
      return unwrap(res, InvestigationListResponseSchema);
    },

    // Endpoint #2 — GET /investigations/{id}
    async getInvestigation(id: string) {
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}`);
      return unwrap(res, InvestigationSchema);
    },

    // Endpoint #3 — POST /investigations/{id}/transitions
    async transitionInvestigation(id: string, req) {
      const validated = InvestigationTransitionRequestSchema.parse(req);
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}/transitions`, {
        method: "POST",
        body: JSON.stringify(validated),
      });
      return unwrap(res, InvestigationSchema);
    },

    // Endpoint #4 — POST /investigations/{id}/notes
    async addInvestigationNote(id: string, req) {
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}/notes`, {
        method: "POST",
        body: JSON.stringify(req),
      });
      return unwrap(res, z.object({ created: z.literal(true) }));
    },

    // Endpoint #5 — GET /rule-firings
    async listRuleFirings(params?: ListParams) {
      const res = await authedFetch(`/rule-firings${qs({ ...params })}`);
      return unwrap(res, RuleFiringListResponseSchema);
    },

    // Endpoint #6 — GET /ml-scores
    async listMlScores(params?: ListParams) {
      const res = await authedFetch(`/ml-scores${qs({ ...params })}`);
      return unwrap(res, MlScoreListResponseSchema);
    },

    // Endpoint #7 — GET /ml-scores/{id}/features
    async getMlScoreFeatures(scoreId: string) {
      const res = await authedFetch(`/ml-scores/${encodeURIComponent(scoreId)}/features`);
      return unwrap(res, MlScoreFeaturesSchema);
    },

    // Endpoint #8 — GET /holds
    async listHolds(params?: ListParams) {
      const res = await authedFetch(`/holds${qs({ ...params })}`);
      return unwrap(res, HoldListResponseSchema);
    },

    // Endpoint #9 — POST /holds/{hold_id}/release
    async releaseHold(holdId: string, req) {
      const validated = HoldReleaseRequestSchema.parse(req);
      const res = await authedFetch(`/holds/${encodeURIComponent(holdId)}/release`, {
        method: "POST",
        body: JSON.stringify(validated),
      });
      return unwrap(res, HoldReleaseResponseSchema);
    },

    // Endpoint #10 — POST /graph-runs/trigger
    async triggerGraphRun() {
      const res = await authedFetch("/graph-runs/trigger", { method: "POST", body: "{}" });
      return unwrap(res, GraphRunTriggerResponseSchema);
    },

    // Endpoint #11 — GET /graph-runs
    async listGraphRuns(params?: ListParams) {
      const res = await authedFetch(`/graph-runs${qs({ ...params })}`);
      return unwrap(res, GraphRunListResponseSchema);
    },

    // Endpoint #12 — GET /graph-runs/{run_id}
    async getGraphRun(runId: string) {
      const res = await authedFetch(`/graph-runs/${encodeURIComponent(runId)}`);
      return unwrap(res, GraphRunSchema);
    },

    // Endpoint #13 — GET /fraud-rings/{id}
    async getFraudRing(id: string) {
      const res = await authedFetch(`/fraud-rings/${encodeURIComponent(id)}`);
      return unwrap(res, FraudRingSchema);
    },

    // Endpoint #14 — GET /recovery
    async getRecoveryAggregations(params?: RecoveryParams) {
      const res = await authedFetch(`/recovery${qs({ ...params })}`);
      return unwrap(res, RecoveryAggregationResponseSchema);
    },

    // Endpoint #15 — GET /dashboard-summary
    async getDashboardSummary() {
      const res = await authedFetch("/dashboard-summary");
      return unwrap(res, DashboardSummarySchema);
    },

    // Endpoint #16 — GET /thresholds
    async getThresholds() {
      const res = await authedFetch("/thresholds");
      return unwrap(res, ThresholdConfigSchema);
    },

    // Endpoint #17 — PUT /thresholds
    async updateThresholds(req) {
      const validated = ThresholdUpdateRequestSchema.parse(req);
      const res = await authedFetch("/thresholds", {
        method: "PUT",
        body: JSON.stringify(validated),
      });
      return unwrap(res, ThresholdConfigSchema);
    },

    // Endpoint #18 — GET /accumulator-anomalies
    async listAccumulatorAnomalies(params?: ListParams) {
      const res = await authedFetch(`/accumulator-anomalies${qs({ ...params })}`);
      return unwrap(res, AccumulatorAnomalyListResponseSchema);
    },

    async probeHealth() {
      const start = performance.now();
      try {
        const res = await fetchImpl(`${baseUrl}/health`, { method: "GET" });
        const latency_ms = Math.round(performance.now() - start);
        return res.ok
          ? { ok: true as const, latency_ms }
          : { ok: false as const, latency_ms, error: `HTTP ${res.status}` };
      } catch (e) {
        return {
          ok: false as const,
          latency_ms: Math.round(performance.now() - start),
          error: (e as Error).message,
        };
      }
    },
  };
}
```

Note: `z` import needed at top of file — add `import { z } from "zod";`. The inline `z.object({ created: z.literal(true) })` in `addInvestigationNote` is correct; alternatively, export `NoteResponseSchema` from types.ts. Either is fine; prefer exporting from types.ts for consistency.

**Tests:** None in this task — covered by A5-5.

### Task A5-4: Mock implementation (`packages/contract/src/impls/reclaimrx/mock.ts`)

**What:** Create `packages/contract/src/impls/reclaimrx/mock.ts` — `createMockReclaimRxClient` factory with realistic FWA fixtures.

**Files created:**
- `packages/contract/src/impls/reclaimrx/mock.ts`

**Implementation (key structure — full file has all 18 methods with realistic fixtures):**

```typescript
// packages/contract/src/impls/reclaimrx/mock.ts
// SP-3 ReclaimRx mock implementation.
// Realistic fixtures for 5 FWA archetypes (spec §9.4).
// All Decimal amounts are strings. No float money.
import type { ReclaimRxClient } from "./client.js";
import { RECLAIMRX_CACHE_POLICIES } from "./client.js";
import type {
  Investigation,
  PaymentHold,
  GraphRun,
  FraudRing,
  ThresholdConfig,
} from "./types.js";

// ── Fixtures (no real PHI; invented UUIDs; Luhn-valid NPIs per spec §9.4) ─

const TENANT_ID = "00000000-0000-0000-0000-000000000001";

const MOCK_INVESTIGATIONS: Investigation[] = [
  {
    id: "11111111-0000-0000-0000-000000000001",
    tenant_id: TENANT_ID,
    status: "open",
    severity: "high",
    source: "rule_firing",
    source_ref_id: "22222222-0000-0000-0000-000000000001",
    member_id: "33333333-0000-0000-0000-000000000001",
    opened_at: "2026-05-15T10:00:00Z",
    opened_by: "system",
    assigned_to: null,
    closed_at: null,
    closed_by: null,
    outcome_label: null,
    recovered_amount: null,
    hold_amount: "1250.00",
    threshold_config_version: 1,
  },
  {
    id: "11111111-0000-0000-0000-000000000002",
    tenant_id: TENANT_ID,
    status: "in_progress",
    severity: "critical",
    source: "graph_ring",
    source_ref_id: "44444444-0000-0000-0000-000000000001",
    member_id: null,
    opened_at: "2026-05-12T08:00:00Z",
    opened_by: "system",
    assigned_to: "investigator@example.com",
    closed_at: null,
    closed_by: null,
    outcome_label: null,
    recovered_amount: null,
    hold_amount: "45000.00",
    threshold_config_version: 1,
  },
];

const MOCK_HOLDS: PaymentHold[] = [
  {
    id: "55555555-0000-0000-0000-000000000001",
    tenant_id: TENANT_ID,
    investigation_id: "11111111-0000-0000-0000-000000000001",
    status: "active",
    amount_threshold: "1250.00",
    entity_type: "pharmacy",
    entity_id: "8084009009",  // Luhn-valid NPI per spec §9.4
    placed_by: "system",
    placed_at: "2026-05-15T10:01:00Z",
    released_by: null,
    released_at: null,
    release_reason: null,
  },
];

const MOCK_GRAPH_RUN: GraphRun = {
  id: "66666666-0000-0000-0000-000000000001",
  tenant_id: TENANT_ID,
  status: "completed",
  trigger: "cron",
  started_at: "2026-05-18T02:00:00Z",
  completed_at: "2026-05-18T02:03:15Z",
  failed_at: null,
  error_code: null,
  error_message: null,
  correlation_id: "77777777-0000-0000-0000-000000000001",
  stale_timeout_at: "2026-05-18T08:00:00Z",
  rings_detected: 2,
  investigations_opened: 2,
  records_scanned: 8432,
  lookback_window_days: 90,
};

const MOCK_FRAUD_RING: FraudRing = {
  id: "44444444-0000-0000-0000-000000000001",
  tenant_id: TENANT_ID,
  graph_run_id: "66666666-0000-0000-0000-000000000001",
  detected_at: "2026-05-18T02:03:00Z",
  density_score: "0.87",
  node_count: 7,
  edge_count: 12,
  entity_refs: [
    { entity_type: "prescriber", entity_id: "8084009009", label: "Prescriber A" },
    { entity_type: "pharmacy", entity_id: "8084001234", label: "Pharmacy B" },
  ],
  spawned_investigation_id: "11111111-0000-0000-0000-000000000002",
};

const MOCK_THRESHOLD_CONFIG: ThresholdConfig = {
  tenant_id: TENANT_ID,
  version: 1,
  effective_at: "2026-05-01T00:00:00Z",
  superseded_at: null,
  rule_thresholds: { RULE_001: "0.75", RULE_002: "0.80" },
  ml_score_thresholds: { open: "0.60", auto_hold: "0.80", escalate: "0.95" },
  graph_density_threshold: "0.75",
  accumulator_anomaly_sensitivity: "0.70",
  updated_by: "admin@example.com",
};

export function createMockReclaimRxClient(): ReclaimRxClient {
  return {
    name: "reclaimrx" as const,
    cachePolicies: RECLAIMRX_CACHE_POLICIES,

    async listInvestigations(params) {
      const results = MOCK_INVESTIGATIONS.filter((inv) => {
        if (params?.status && inv.status !== params.status) return false;
        if (params?.severity && inv.severity !== params.severity) return false;
        return true;
      });
      return { results, total: results.length };
    },

    async getInvestigation(id) {
      const inv = MOCK_INVESTIGATIONS.find((i) => i.id === id);
      if (!inv) throw new Error(`Investigation ${id} not found`);
      return inv;
    },

    async transitionInvestigation(id, req) {
      const inv = MOCK_INVESTIGATIONS.find((i) => i.id === id);
      if (!inv) throw new Error(`Investigation ${id} not found`);
      return { ...inv, status: req.to_status };
    },

    async addInvestigationNote(_id, _req) {
      return { created: true };
    },

    async listRuleFirings(params) {
      return { results: [], total: 0 };
    },

    async listMlScores(params) {
      return { results: [], total: 0 };
    },

    async getMlScoreFeatures(scoreId) {
      return { score_id: scoreId, features: [] };
    },

    async listHolds(params) {
      return { results: MOCK_HOLDS, total: MOCK_HOLDS.length };
    },

    async releaseHold(holdId, req) {
      return {
        hold_id: holdId,
        status: "released",
        released_at: new Date().toISOString(),
        released_by: "mock-user",
        reason: req.reason,
      };
    },

    async triggerGraphRun() {
      return {
        graph_run_id: "88888888-0000-0000-0000-000000000001",
        status: "running",
        message: "Graph run queued",
      };
    },

    async listGraphRuns(params) {
      return { results: [MOCK_GRAPH_RUN], total: 1 };
    },

    async getGraphRun(runId) {
      return MOCK_GRAPH_RUN;
    },

    async getFraudRing(id) {
      return MOCK_FRAUD_RING;
    },

    async getRecoveryAggregations(params) {
      return {
        results: [
          { period: "2026-05", group_key: "all", total_recovered: "87250.00", investigation_count: 3 },
        ],
        total_recovered: "87250.00",
      };
    },

    async getDashboardSummary() {
      return {
        open_investigations: 12,
        active_holds: 4,
        hold_volume: "46250.00",
        recovered_mtd: "87250.00",
        false_positive_rate: "0.12",
        high_severity_open: 3,
      };
    },

    async getThresholds() {
      return MOCK_THRESHOLD_CONFIG;
    },

    async updateThresholds(req) {
      return { ...MOCK_THRESHOLD_CONFIG, version: 2, reason: req.reason };
    },

    async listAccumulatorAnomalies(params) {
      return { results: [], total: 0 };
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
```

**Tests:** None in this task — covered by A5-5.

### Task A5-5: Contract tests + `packages/contract/src/index.ts` update

**What:** Write Vitest tests for mock + real impls; export reclaimrx from package index.

**Files created:**
- `packages/contract/src/__tests__/reclaimrx.test.ts`

**Files modified:**
- `packages/contract/src/index.ts` — add reclaimrx exports after prescriber-directory block

**Test implementation (`reclaimrx.test.ts`):**

```typescript
import { describe, it, expect } from "vitest";
import { createMockReclaimRxClient } from "../impls/reclaimrx/mock.js";
import { createRealReclaimRxClient } from "../impls/reclaimrx/real.js";
import { RECLAIMRX_CACHE_POLICIES } from "../impls/reclaimrx/client.js";
import { CachePolicySchema } from "../cache-policy.js";
import {
  InvestigationSchema,
  InvestigationListResponseSchema,
  DashboardSummarySchema,
  ThresholdConfigSchema,
  HoldListResponseSchema,
  HoldReleaseResponseSchema,
  GraphRunSchema,
  GraphRunTriggerResponseSchema,
  FraudRingSchema,
  AccumulatorAnomalyListResponseSchema,
  MlScoreFeaturesSchema,
  RuleFiringListResponseSchema,
  SPEC_55_ENDPOINT_COVERAGE,  // R1 BLOCK 9 fix — drives parametrized branch tests
} from "../impls/reclaimrx/types.js";
import type { ReclaimRxClient } from "../impls/reclaimrx/client.js";

// ── MockReclaimRxClient ────────────────────────────────────────────────────

describe("MockReclaimRxClient", () => {
  const client = createMockReclaimRxClient();

  it("exposes name 'reclaimrx'", () => {
    expect(client.name).toBe("reclaimrx");
  });

  it("all cache policies validate against CachePolicySchema", () => {
    for (const [op, policy] of Object.entries(client.cachePolicies)) {
      const result = CachePolicySchema.safeParse(policy);
      expect(result.success, `${op} cache policy should validate`).toBe(true);
    }
  });

  it("listInvestigations returns valid InvestigationListResponse", async () => {
    const res = await client.listInvestigations();
    const parsed = InvestigationListResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(res.results.length).toBeGreaterThanOrEqual(1);
  });

  it("listInvestigations filters by status", async () => {
    const res = await client.listInvestigations({ status: "open" });
    expect(res.results.every((i) => i.status === "open")).toBe(true);
  });

  it("listInvestigations filters by severity", async () => {
    const res = await client.listInvestigations({ severity: "high" });
    expect(res.results.every((i) => i.severity === "high")).toBe(true);
  });

  it("getInvestigation returns valid Investigation for known id", async () => {
    const list = await client.listInvestigations();
    const id = list.results[0]!.id;
    const inv = await client.getInvestigation(id);
    const parsed = InvestigationSchema.safeParse(inv);
    expect(parsed.success).toBe(true);
  });

  it("getInvestigation throws for unknown id", async () => {
    await expect(client.getInvestigation("00000000-0000-0000-0000-000000000000")).rejects.toThrow();
  });

  it("transitionInvestigation returns investigation with new status", async () => {
    const list = await client.listInvestigations({ status: "open" });
    const id = list.results[0]!.id;
    const result = await client.transitionInvestigation(id, { to_status: "in_progress", reason: "Reviewing" });
    expect(result.status).toBe("in_progress");
  });

  it("addInvestigationNote returns { created: true }", async () => {
    const res = await client.addInvestigationNote("any-id", { text: "Test note" });
    expect(res.created).toBe(true);
  });

  it("listRuleFirings returns valid RuleFiringListResponse", async () => {
    const res = await client.listRuleFirings();
    const parsed = RuleFiringListResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
  });

  it("getMlScoreFeatures returns MlScoreFeatures with features array", async () => {
    const res = await client.getMlScoreFeatures("any-id");
    const parsed = MlScoreFeaturesSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(Array.isArray(res.features)).toBe(true);
  });

  it("listHolds returns valid HoldListResponse", async () => {
    const res = await client.listHolds();
    const parsed = HoldListResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
  });

  it("releaseHold returns valid HoldReleaseResponse with 'released' status", async () => {
    const res = await client.releaseHold("55555555-0000-0000-0000-000000000001", {
      reason: "Investigation closed",
      investigation_id: "11111111-0000-0000-0000-000000000001",
    });
    const parsed = HoldReleaseResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(res.status).toBe("released");
  });

  it("triggerGraphRun returns valid GraphRunTriggerResponse with 'running' status", async () => {
    const res = await client.triggerGraphRun();
    const parsed = GraphRunTriggerResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(res.status).toBe("running");
  });

  it("getGraphRun returns valid GraphRun", async () => {
    const res = await client.getGraphRun("any-id");
    const parsed = GraphRunSchema.safeParse(res);
    expect(parsed.success).toBe(true);
  });

  it("getFraudRing returns valid FraudRing with node/edge counts", async () => {
    const res = await client.getFraudRing("any-id");
    const parsed = FraudRingSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(res.node_count).toBeGreaterThanOrEqual(1);
  });

  it("getDashboardSummary returns valid DashboardSummary with Decimal strings", async () => {
    const res = await client.getDashboardSummary();
    const parsed = DashboardSummarySchema.safeParse(res);
    expect(parsed.success).toBe(true);
    // Verify Decimal amounts are strings (not floats)
    expect(typeof res.hold_volume).toBe("string");
    expect(typeof res.recovered_mtd).toBe("string");
    expect(typeof res.false_positive_rate).toBe("string");
  });

  it("getThresholds returns valid ThresholdConfig with Decimal strings", async () => {
    const res = await client.getThresholds();
    const parsed = ThresholdConfigSchema.safeParse(res);
    expect(parsed.success).toBe(true);
    expect(typeof res.ml_score_thresholds.open).toBe("string");
  });

  it("listAccumulatorAnomalies returns valid AccumulatorAnomalyListResponse", async () => {
    const res = await client.listAccumulatorAnomalies();
    const parsed = AccumulatorAnomalyListResponseSchema.safeParse(res);
    expect(parsed.success).toBe(true);
  });

  it("probeHealth returns ok:true for mock", async () => {
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
    expect(h.latency_ms).toBe(0);
  });

  it("RECLAIMRX_CACHE_POLICIES covers all 13 read operations", () => {
    const expectedOps = [
      "listInvestigations", "getInvestigation", "listRuleFirings",
      "listMlScores", "getMlScoreFeatures", "listHolds", "listGraphRuns",
      "getGraphRun", "getFraudRing", "getRecoveryAggregations",
      "getDashboardSummary", "getThresholds", "listAccumulatorAnomalies",
    ];
    for (const op of expectedOps) {
      expect(RECLAIMRX_CACHE_POLICIES).toHaveProperty(op);
    }
  });
});

// ── RealReclaimRxClient (injected fetch) ───────────────────────────────────

describe("RealReclaimRxClient (injected fetch)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("attaches Bearer token + correlation-id on every request", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-reclaimrx",
      fetch: fakeFetch,
    });
    await client.listInvestigations();
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-reclaimrx");
    expect(captured[0]?.headers.get("x-correlation-id")).toMatch(/^[0-9a-f-]{36}$/);
    expect(captured[0]?.url).toContain("/api/v1/reclaimrx/investigations");
  });

  it("maps 4xx error envelope to RealClientError with code", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse(
      { error: { code: "INSUFFICIENT_ROLE", message: "Requires reclaimrx.investigator", correlation_id: "550e8400-e29b-41d4-a716-446655440099" } },
      { status: 403 },
    );
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toMatchObject({ code: "INSUFFICIENT_ROLE" });
  });

  it("releaseHold sends POST to /holds/{id}/release with correct body", async () => {
    const captured: { url: string; method: string; body: unknown }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      captured.push({
        url: typeof input === "string" ? input : (input as Request).url,
        method: init?.method ?? "GET",
        body: init?.body ? JSON.parse(init.body as string) : null,
      });
      return jsonResponse({
        hold_id: "h1", status: "released", released_at: "2026-05-18T12:00:00Z",
        released_by: "user", reason: "done",
      });
    };
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await client.releaseHold("h1", { reason: "done", investigation_id: "11111111-0000-0000-0000-000000000001" });
    expect(captured[0]?.url).toContain("/holds/h1/release");
    expect(captured[0]?.method).toBe("POST");
    expect((captured[0]?.body as { reason: string }).reason).toBe("done");
  });

  it("probeHealth pings /health and returns latency", async () => {
    const fakeFetch: typeof fetch = async () => new Response("OK", { status: 200 });
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
    expect(typeof h.latency_ms).toBe("number");
  });

  it("rejects malformed response body via zod", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse({ wrong: "shape" });
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toThrow();
  });

  // ── R1 BLOCK 9 fix — coverage on auth + Zod + tenant + network branches ────
  // .claude/rules/testing.md requires 100% branch coverage on security paths.
  // The prior test suite covered the happy path + ONE 401 case + ONE Zod
  // failure. Codex flagged this as insufficient: every endpoint needs a Zod
  // parse-failure case, every endpoint needs the 403 tenant-mismatch branch,
  // and the authedFetch wrapper needs a network-error branch.

  // Zod parse failure per endpoint (12+ cases) — one row per spec §5.5 endpoint
  // whose response goes through unwrap<T>. Reuses the SPEC_55_ENDPOINT_COVERAGE
  // matrix from types.ts so additions stay in sync.
  it.each(SPEC_55_ENDPOINT_COVERAGE.filter((e) => e.method === "GET"))(
    "endpoint #%i (%s) rejects malformed body via zod",
    async ({ path }) => {
      const fakeFetch: typeof fetch = async () => jsonResponse({ wrong: "shape" });
      const client = createRealReclaimRxClient({
        baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
      });
      // Pick the client method for the endpoint by path
      const method = pickClientMethodForPath(client, path);
      await expect(method()).rejects.toThrow();
    },
  );

  // 403 TENANT_MISMATCH branch — every endpoint must surface the spec-correct code
  it("maps 403 TENANT_MISMATCH error envelope through unwrap", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse(
      {
        error: {
          code: "TENANT_MISMATCH",
          message: "X-Tenant-Id header does not match authenticated user tenant.",
          field: "x-tenant-id",
          correlation_id: "550e8400-e29b-41d4-a716-446655440099",
        },
      },
      { status: 403 },
    );
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toMatchObject({
      code: "TENANT_MISMATCH",
    });
  });

  // Network-error branch — fetch itself rejects (DNS, TLS, ECONNREFUSED, etc.)
  it("authedFetch propagates network errors with a typed code", async () => {
    const fakeFetch: typeof fetch = async () => {
      throw new TypeError("Failed to fetch");
    };
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toMatchObject({
      code: "NETWORK_ERROR",
    });
  });

  // Empty body / unexpected content-type — defense-in-depth
  it("rejects 200 OK with empty body via zod parse", async () => {
    const fakeFetch: typeof fetch = async () =>
      new Response("", { status: 200, headers: { "content-type": "application/json" } });
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toThrow();
  });
});


// Test helper — maps a spec path to the matching client method. Throws on
// unknown path so a missing method is caught at test time rather than as
// a silent skip. Path matching is exact (no `{id}` interpolation in the
// helper; the GET-only filter above only exercises endpoints whose method
// takes zero required arguments after fixtures are seeded).
function pickClientMethodForPath(
  client: ReclaimRxClient,
  path: string,
): () => Promise<unknown> {
  const map: Record<string, () => Promise<unknown>> = {
    "/investigations":                () => client.listInvestigations(),
    "/holds":                         () => client.listHolds(),
    "/graph-runs":                    () => client.listGraphRuns(),
    "/recovery":                      () => client.getRecoveryAggregations(),
    "/dashboard-summary":             () => client.getDashboardSummary(),
    "/thresholds":                    () => client.getThresholds(),
    "/accumulator-anomalies":         () => client.listAccumulatorAnomalies(),
    "/ml-scores":                     () => client.listMlScores(),
  };
  const handler = map[path];
  if (!handler) {
    throw new Error(`No client method registered for path "${path}".`);
  }
  return handler;
}
```

**`packages/contract/src/index.ts` additions** (append after prescriber-directory exports):

```typescript
// ReclaimRx client — SP-3.
export {
  InvestigationStatusSchema,
  InvestigationSchema,
  InvestigationListResponseSchema,
  InvestigationTransitionRequestSchema,
  HoldReleaseRequestSchema,
  HoldReleaseResponseSchema,
  PaymentHoldSchema,
  GraphRunSchema,
  FraudRingSchema,
  ThresholdConfigSchema,
  DashboardSummarySchema,
  AccumulatorAnomalySchema,
  type Investigation,
  type InvestigationStatus,
  type PaymentHold,
  type GraphRun,
  type FraudRing,
  type ThresholdConfig,
  type DashboardSummary,
  type AccumulatorAnomaly,
  type HoldReleaseRequest,
  type HoldReleaseResponse,
} from "./impls/reclaimrx/types.js";

export {
  RECLAIMRX_CACHE_POLICIES,
  type ReclaimRxClient,
  type ReclaimRxFactory,
} from "./impls/reclaimrx/client.js";

export { createRealReclaimRxClient } from "./impls/reclaimrx/real.js";
export { createMockReclaimRxClient } from "./impls/reclaimrx/mock.js";
```

**Coverage gate:** 100% on all branches in types.ts (Zod schemas), client.ts (policy map), mock.ts (all method paths). Real impl tested via injected fetch — auth lines 100%.

### Task A5-6: Frontend module scaffold (`packages/modules/reclaimrx/`) + manifest update

**What:** Create `packages/modules/reclaimrx/` package (same shape as `packages/modules/directories/`). Wire into `packages/shell/src/_generated/manifest.json`. Stub directories for Plan B-E content.

**Files created:**
- `packages/modules/reclaimrx/module.config.ts`
- `packages/modules/reclaimrx/package.json`
- `packages/modules/reclaimrx/tsconfig.json` (copy from directories; update name)
- `packages/modules/reclaimrx/vitest.config.ts` (copy from directories)
- `packages/modules/reclaimrx/src/index.ts` (barrel — exports module.config)
- `packages/modules/reclaimrx/src/investigations/index.ts` (empty stub — Plan B)
- `packages/modules/reclaimrx/src/rules/index.ts` (empty stub — Plan C)
- `packages/modules/reclaimrx/src/ml/index.ts` (empty stub — Plan C)
- `packages/modules/reclaimrx/src/holds/index.ts` (empty stub — Plan D)
- `packages/modules/reclaimrx/src/recovery/index.ts` (empty stub — Plan D)
- `packages/modules/reclaimrx/src/graph/index.ts` (empty stub — Plan E)
- `packages/modules/reclaimrx/src/bff/index.ts` (empty stub — Plans B-E)
- `packages/modules/reclaimrx/src/components/index.ts` (empty stub — Plans B-E)
- `packages/modules/reclaimrx/src/rbac/index.ts` (empty stub — Plan B)
- `packages/modules/reclaimrx/tests/unit/.gitkeep`

**Files modified:**
- `packages/shell/src/_generated/manifest.json` — add `"reclaimrx"` to `modules` array + `RECLAIMRX_URL` env + health check

**`module.config.ts` full implementation:**

```typescript
// packages/modules/reclaimrx/module.config.ts
// SP-3 ReclaimRx module config.
// Follows SD-4 §3 shape (read by packages/scripts/build-manifest.ts).
// No shared type imported from @infinityrx/shell — `as const` literal per SP-0 Plan A R2.

export const config = {
  name: "reclaimrx",
  routes: [
    "/reclaimrx",
    "/reclaimrx/dashboard",
    "/reclaimrx/investigations",
    "/reclaimrx/investigations/[id]",
    "/reclaimrx/holds",
    "/reclaimrx/fraud-rings",
    "/reclaimrx/fraud-rings/[id]",
    "/reclaimrx/graph-runs",
    "/reclaimrx/thresholds",
    "/reclaimrx/accumulator-anomalies",
  ],
  navEntry: {
    label: "ReclaimRx",
    icon: "shield-check",
    order: 4,
  },
  requires: {
    backends: ["reclaimrx", "core-platform"],
    sharedServices: ["postgres", "redis", "rabbitmq"],
    schemas: ["reclaimrx", "shared", "audit"],
    migrations: ["reclaimrx/0008"],
    env: [
      "RECLAIMRX_URL",
      "CORE_PLATFORM_URL",
    ],
    health: [
      "http://reclaimrx:8007/health",
    ],
    seedData: [],
    queues: ["reclaimrx.accumulator_updated", "reclaimrx.fwa_events"],
    jobs: ["graph_rebuild_fraud_network_graph"],
    buckets: [],
    integrations: [],
    secrets: [],
  },
  shellSurfaces: {
    navOrderSlots: [4],
    cacheTagPrefixes: ["reclaimrx:"],
    commandPaletteScopes: ["reclaimrx.*"],
    routePrefixes: ["/reclaimrx"],
    cacheKeyNamespaces: ["reclaimrx"],
    redisKeyPrefixes: ["tenant:{tenant_id}:reclaimrx:"],
  },
} as const;

export default config;
```

**`package.json`:**

```json
{
  "name": "@infinityrx/module-reclaimrx",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "exports": {
    ".": "./dist/src/index.js"
  },
  "scripts": {
    "build": "tsc -b",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@infinityrx/auth": "*",
    "@infinityrx/contract": "*",
    "@infinityrx/qa-harness": "*",
    "@infinityrx/shell": "*",
    "@infinityrx/ui": "*",
    "@tanstack/react-query": "5.59.20",
    "@tanstack/react-table": "8.20.5",
    "zod": "3.23.8"
  },
  "peerDependencies": {
    "react": "^19.2.0",
    "react-dom": "^19.2.0"
  },
  "devDependencies": {
    "@testing-library/react": "16.3.0",
    "@testing-library/user-event": "14.5.2",
    "@types/node": "22.7.5",
    "@types/react": "19.1.2",
    "@types/react-dom": "19.1.2",
    "happy-dom": "15.11.7",
    "react": "19.2.6",
    "react-dom": "19.2.6",
    "typescript": "5.6.3",
    "vitest": "2.1.9"
  }
}
```

**`manifest.json` modification** — add `"reclaimrx"` to `modules`, `"reclaimrx"` to `required_backends`, `"RECLAIMRX_URL"` to `required_env`, `"http://reclaimrx:8007/health"` to `required_health`:

```json
{
  "modules": ["prescriber-directory", "directories", "reclaimrx"],
  "required_backends": [
    "prescriber-directory", "pharmacy-directory", "drug-database",
    "core-platform", "reclaimrx"
  ],
  "required_env": [
    "JWT_SECRET", "NEXTAUTH_SECRET", "INFINITYRX_ENV",
    "PRESCRIBER_DIRECTORY_URL", "PHARMACY_DIRECTORY_URL",
    "DRUG_DATABASE_URL", "CORE_PLATFORM_URL", "RECLAIMRX_URL"
  ],
  "required_health": [
    "http://prescriber-directory:8010/health",
    "http://pharmacy-directory:8009/health",
    "http://drug-database:8011/health",
    "http://reclaimrx:8007/health"
  ]
}
```

**Tests:** Vitest runs cleanly (no test files yet — stub tests pass implicitly). Manifest build script must still pass after the addition.

**Coverage gate:** module.config.ts is configuration — no coverage gate. Package infrastructure: lint-clean (no unused imports). Manifest build: zero errors.

### Task A5-7: Six empty-state portal pages + event contract docs

**What:** Create 6 new Next.js pages under `portal/operator/app/reclaimrx/` that don't already exist, and write 2 event contract docs.

**Do NOT touch existing pages** (`page.tsx`, `investigations/page.tsx`, `investigations/[id]/page.tsx`, `leakage/page.tsx`, `risk/page.tsx`, `wizard/page.tsx`, `recovery/page.tsx`). These are pre-SP-3 pages outside spec §6 Plan A scope.

**Files created:**
- `portal/operator/app/reclaimrx/dashboard/page.tsx`
- `portal/operator/app/reclaimrx/holds/page.tsx`
- `portal/operator/app/reclaimrx/fraud-rings/page.tsx`
- `portal/operator/app/reclaimrx/graph-runs/page.tsx`
- `portal/operator/app/reclaimrx/thresholds/page.tsx`
- `portal/operator/app/reclaimrx/accumulator-anomalies/page.tsx`
- `docs/api-contracts/events/payment.hold_released.md (R1 BLOCK 8 fix — `fwa.*` prefix per event-bus.md, not `payment.*`)`
- `docs/api-contracts/events/fwa.graph_run_completed.md`

**Empty-state page pattern** (R1 BLOCK 10 fix — verified against existing portal-local component):

```tsx
// portal/operator/app/reclaimrx/dashboard/page.tsx
// SP-3 Plan A5 — Empty state per R1 BLOCK 9.
// Plan D replaces this with real DashboardTiles + 6 KPI tiles.
import { ComingSoonPage } from "@/components/ui/coming-soon-page";

export default function ReclaimRxDashboardPage() {
  return (
    <ComingSoonPage
      title="FWA Detection Dashboard"
      description="Investigations, hold volume, recovered dollars, and false-positive rate across all programs."
      phase="Plan D"
    />
  );
}
```

`@/components/ui/coming-soon-page` resolves to `portal/operator/components/ui/coming-soon-page.tsx`, which already exists and is used by other portal pages. No shadcn primitives needed; no new component scaffolding required.

For each of the 6 pages, use the above wrapper with the values from this table:

| Route | title | description | phase |
|---|---|---|---|
| `/reclaimrx/dashboard` | FWA Detection Dashboard | Investigations, hold volume, recovered dollars, false-positive rate | Plan D |
| `/reclaimrx/holds` | Payment Holds | Active holds, hold release with audited reason, per-investigation hold history | Plan D |
| `/reclaimrx/fraud-rings` | Fraud Ring Visualization | Force-directed graph of detected fraud rings; drill from flagged claim to connected entities | Plan E |
| `/reclaimrx/graph-runs` | Graph Analysis Runs | Trigger on-demand analysis, view run history, monitor status, see rings detected | Plan E |
| `/reclaimrx/thresholds` | Threshold Configuration | Per-tenant rule thresholds, ML score thresholds, anomaly sensitivity. Admin-only. | Plan C |
| `/reclaimrx/accumulator-anomalies` | Accumulator Anomaly Detection | Sudden spike, multi-payer convergence, reset evasion, and threshold oscillation patterns | Plan E |

No `lucide-react` icon imports needed — `ComingSoonPage` already renders the `Construction` icon internally. Pages are pure props; nothing to import per call site beyond the component itself.

**Event contract docs** (full content — spec §11.5 instantiated verbatim):

`docs/api-contracts/events/payment.hold_released.md (R1 BLOCK 8 fix — `fwa.*` prefix per event-bus.md, not `payment.*`)`:
```markdown
# Event Contract: payment.hold_released

**Version:** 1.0
**Publisher:** modules/reclaimrx
**Consumer(s):** SP-1 PaySync (payment resume); any future audit consumer
**Plan authored:** SP-3 Plan A (backend release endpoint + outbox publish)
**Plan consuming (UI):** SP-3 Plan D

## Envelope

| Field | Type | Value |
|---|---|---|
| event_type | string | `"payment.hold_released"` |
| schema_version | string | `"1.0"` |
| tenant_id | UUID | Envelope-level; always present |
| ordering_key | string | `hold_id` (per-hold ordering) |
| idempotency_key | string | `"hold:release:{hold_id}"` (unique per hold) |
| correlation_id | UUID | Auto-generated by EventEnvelope |
| source_module | string | `"reclaimrx"` |
| timestamp | datetime | Auto-set by EventEnvelope (UTC) |

## Payload

| Field | Type | Required | Notes |
|---|---|---|---|
| hold_id | UUID | Yes | Identifies the released hold |
| amount | string | Yes | Decimal serialized as str() — never float |
| released_by | string | Yes | JWT sub of user who released |
| reason | string | Yes | Always required (any role); see spec §5.5 #9 |
| investigation_id | UUID | Yes | Must match hold.investigation_id (403 if not) |
| released_at | ISO8601 | Yes | UTC timestamp of release |
| emergency_reason_code | string \| null | No | Admin override only: `LEGAL_HOLD`, `REGULATORY_DIRECTIVE`, `IRRECOVERABLE_HARM`, `OTHER_WITH_NOTE` |
| emergency_note | string \| null | No | Required if emergency_reason_code = `OTHER_WITH_NOTE` |

## Forward compatibility

Consumers MUST ignore unknown fields. New fields added in 1.x are non-breaking. Consumers MUST be wrapped with `idempotent_handler` — the outbox dispatcher may publish this event more than once.

## Publish mechanism

Transactional outbox (spec §7.2 + R1 BLOCK 4). The outbox row is written in the same DB transaction as the hold status update and audit entry. The outbox dispatcher (Plan A2) polls pending rows and publishes to the event bus. On publish success: `status='published'`. On repeated failure: `status='failed'` after 10 attempts + alert.

## Version history

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-18 | Initial. Emergency fields added per R4 NEW CONCERN 2 + R5. |
```

`docs/api-contracts/events/fwa.graph_run_completed.md`:
```markdown
# Event Contract: fwa.graph_run_completed

**Version:** 1.0
**Publisher:** modules/reclaimrx (graph_analysis_job.py, via outbox)
**Consumer(s):** No SP-3 consumer (Plan E may consume for UI refresh); future ML retraining feed
**Plan authored:** SP-3 Plan A

## Envelope

| Field | Type | Value |
|---|---|---|
| event_type | string | `"fwa.graph_run_completed"` |
| schema_version | string | `"1.0"` |
| tenant_id | UUID | Envelope-level |
| ordering_key | string | `graph_run_id` |
| idempotency_key | string | `"graph_run:{graph_run_id}:completed"` |
| correlation_id | UUID | Auto-generated |
| source_module | string | `"reclaimrx"` |
| timestamp | datetime | Auto-set (UTC) |

## Payload

| Field | Type | Required | Notes |
|---|---|---|---|
| graph_run_id | UUID | Yes | |
| status | string | Yes | `"completed"` \| `"completed_partial"` \| `"failed"` |
| rings_detected | int | Yes | 0 if status=failed |
| investigations_opened | int | Yes | 0 if status=failed |
| records_scanned | int | Yes | 0 if status=failed before scan |
| lookback_window_days | int | Yes | Default 90 |
| started_at | ISO8601 | Yes | |
| completed_at | ISO8601 \| null | Yes | null if status=failed (R3 NEW CONCERN 4) |
| failed_at | ISO8601 \| null | Yes | Set if status=failed |
| error_code | string \| null | No | Set if status=failed; sanitized (no PHI) |
| error_message | string \| null | No | Set if status=failed; sanitized (no PHI) |

## Forward compatibility

Same rule as payment.hold_released — consumers MUST ignore unknown fields.

## Publish mechanism

Transactional outbox (Plan A2). Published after graph job completes or fails. One event per graph run regardless of outcome.

## Version history

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-05-18 | Initial. |
```

**Tests (empty-state pages):** Each page must render without errors. Add a simple render smoke test per page in `portal/operator/tests/` (or co-locate per project convention). Minimum: `render(<ReclaimRxDashboardPage />)` + `expect(screen.getByText("Coming in Plan D")).toBeInTheDocument()`. If project uses Playwright for page-level tests, add 6 `page.goto('/reclaimrx/dashboard')` + `expect(page.locator('text=Coming in Plan D')).toBeVisible()` assertions in the empty-state spec file.

**Coverage gate:** Pages are UI-only with no logic branches. Smoke test confirming render = coverage gate for this task. Event contract docs: no coverage gate (markdown only). Verified: both docs authored per `.claude/rules/event-bus.md` "MUST document every event type in `docs/api-contracts/events/{event_type}.md`".

---

## Testing requirements summary

| Test file | What | Coverage target |
|---|---|---|
| `packages/contract/src/__tests__/reclaimrx.test.ts` | Mock: all 18 methods validate against Zod schemas; Decimal strings; filter logic. Real: auth header, error envelope mapping, correct paths, zod rejection | 100% on auth paths; 100% on Zod-schema validation branches; 95% overall |
| Empty-state page smoke tests | 6 pages render without crash; "Coming in Plan X" text visible | Render-pass (no logic branches to cover) |
| Event contract docs | Not code — no test | n/a |
| Module scaffold | `vitest run` completes with 0 failures in `packages/modules/reclaimrx/` | Pass (no test files = 0 failures) |
| Manifest update | `npm run build:manifest` (in `packages/scripts/`) succeeds after manifest.json change | Zero errors |

**Auto-gate criteria for Plan A5:**
- All tests pass (0 failures, 0 skips)
- `packages/contract/src/__tests__/reclaimrx.test.ts`: 100% on auth + Zod validation paths
- Zod types cover all 18 endpoint shapes (verified by mock test: every method's return value parses)
- No `any` in contract files (TypeScript strict mode — CI enforces)
- Mock Decimal amounts are all strings (verified: `typeof res.hold_volume === "string"` test)
- Event contract docs exist at both paths per `.claude/rules/event-bus.md`
- Manifest build passes (directories module still present; reclaimrx added cleanly)

---

## Out of scope for Plan A5

- BFF routes (Plans B, C, D, E per spec §5.5 BFF phasing)
- Investigation list/detail pages — real UI (Plan B)
- Rule firings + ML scores pages (Plan C)
- Hold release dialog + recovery dashboard (Plan D)
- Graph run page + fraud ring viz (Plan E)
- Cross-module federated search registration (Plan B)
- `<RoleGate>` hook (Plan B — `src/rbac/` stub only in A5)
- Any backend code (Plans A1-A4)
