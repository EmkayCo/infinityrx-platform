// packages/contract/src/impls/reclaimrx/client.ts
// SP-3 ReclaimRx typed client interface.
// Mirrors prescriber-directory/client.ts pattern.
// One method per spec §5.5 endpoint. Write operations have no cache entry (fail-closed).
import type { BaseClient, ClientConfig, ClientFactory } from "../../client-base.js";
import type { CachePolicy } from "../../cache-policy.js";
import type {
  InvestigationListResponse,
  InvestigationDetailResponse,
  InvestigationTransitionRequest,
  InvestigationTransitionResponse,
  NoteRequest,
  InvestigationNoteResponse,
  GraphRunDetailResponse,
  FraudRingDetailResponse,
  RuleFiringListResponse,
  MlScoreListResponse,
  MlScoreFeatures,
  HoldListResponse,
  HoldReleaseRequest,
  HoldReleaseResponse,
  GraphRunTriggerResponse,
  GraphRunListResponse,
  RecoveryAggregationResponse,
  DashboardSummary,
  ThresholdConfig,
  ThresholdUpdateRequest,
  AccumulatorAnomalyListResponse,
  InvestigationStatus,
  InvestigationSeverity,
  InvestigationSource,
} from "./types.js";

// ── Pagination params (shared across list endpoints) ───────────────────────

export interface ListParams {
  cursor?: string;
  limit?: number;
}

// R2 NEW-4 fix: InvestigationListParams uses enum unions from types.ts, NOT broad `string`.
export interface InvestigationListParams extends ListParams {
  status?: InvestigationStatus;
  severity?: InvestigationSeverity;
  source?: InvestigationSource;
}

export type RecoveryPeriod = "mtd" | "qtd" | "ytd" | "last_30d" | "last_90d";
export type RecoveryGroupBy = "program" | "pharmacy" | "rule" | "severity";

export interface RecoveryParams {
  period?: RecoveryPeriod;
  group_by?: RecoveryGroupBy;
}

// ── Client interface (18 backend endpoints) ────────────────────────────────

export interface ReclaimRxClient extends BaseClient {
  readonly name: "reclaimrx";

  // Endpoint #1
  listInvestigations(params?: InvestigationListParams): Promise<InvestigationListResponse>;
  // Endpoint #2 — detail extends base with threshold_snapshot/status_transitions/notes
  getInvestigation(id: string): Promise<InvestigationDetailResponse>;
  // Endpoint #3 — returns the transition record, not the full investigation
  transitionInvestigation(id: string, req: InvestigationTransitionRequest): Promise<InvestigationTransitionResponse>;
  // Endpoint #4 — typed note response
  addInvestigationNote(id: string, req: NoteRequest): Promise<InvestigationNoteResponse>;
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
  // Endpoint #12 — detail schema alias
  getGraphRun(runId: string): Promise<GraphRunDetailResponse>;
  // Endpoint #13 — detail schema alias
  getFraudRing(id: string): Promise<FraudRingDetailResponse>;
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

// ── Cache policies (read-only endpoints; writes are fail-closed per spec §8) ──
// Note: CachePolicySchema.backend_down accepts "stale-ok" | "fail-fast" | "fall-back-to-mock".
// PHI detail endpoint uses "fail-fast" (not cached; must not serve stale PHI data).

export const RECLAIMRX_CACHE_POLICIES: Record<string, CachePolicy> = {
  listInvestigations: {
    ttl_seconds: 30,
    key: ["reclaimrx", "investigations", "{status}", "{severity}", "{source}", "{cursor}"],
    invalidation_tags: ["reclaimrx:investigations"],
    backend_down: "stale-ok",
  },
  getInvestigation: {
    // PHI endpoint — short TTL + fail-fast (Cache-Control: no-store enforced on backend)
    ttl_seconds: 5,
    key: ["reclaimrx", "investigation", "{id}"],
    invalidation_tags: ["reclaimrx:investigations"],
    backend_down: "fail-fast",
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
