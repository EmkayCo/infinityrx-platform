// packages/contract/src/impls/reclaimrx/mock.ts
// SP-3 ReclaimRx mock implementation.
// Realistic fixtures for 5 FWA archetypes (spec §9.4).
// All Decimal amounts are strings. No float money.
// MOCK_FIXED_TIMESTAMP + MOCK_NOTE_ID constants ensure deterministic replays (R3 NEW-6 fix).
import type { ReclaimRxClient } from "./client.js";
import { RECLAIMRX_CACHE_POLICIES } from "./client.js";
import type {
  Investigation,
  PaymentHold,
  GraphRun,
  FraudRing,
  ThresholdConfig,
} from "./types.js";

// ── Fixtures (no real PHI; invented UUIDs; Luhn-valid NPIs per spec §9.4) ──
//
// R3 NEW-6 fix: all timestamps use MOCK_FIXED_TIMESTAMP for deterministic
// replays. Earlier drafts used new Date().toISOString() which caused CI/local
// divergence on snapshot tests.

const TENANT_ID = "00000000-0000-0000-0000-000000000001";
const MOCK_FIXED_TIMESTAMP = "2026-05-18T00:00:00.000Z";
const MOCK_NOTE_ID = "33333333-0000-0000-0000-000000000099";

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
      // R3 NEW-5 fix: return the extended detail shape, not the bare base.
      const inv = MOCK_INVESTIGATIONS.find((i) => i.id === id);
      if (!inv) throw new Error(`Investigation ${id} not found`);
      return {
        ...inv,
        threshold_snapshot: null,
        status_transitions: [],
        notes: [],
      };
    },

    async transitionInvestigation(id, req) {
      // R3 NEW-5 fix: return InvestigationTransitionResponse-shaped row.
      const inv = MOCK_INVESTIGATIONS.find((i) => i.id === id);
      if (!inv) throw new Error(`Investigation ${id} not found`);
      return {
        investigation_id: inv.id,
        from_status: inv.status,
        to_status: req.to_status,
        reason: req.reason,
        transitioned_by: "mock-user",
        transitioned_at: MOCK_FIXED_TIMESTAMP,
        outcome_label: req.outcome_label ?? null,
        recovered_amount: req.recovered_amount ?? null,
      };
    },

    async addInvestigationNote(id, req) {
      // R3 NEW-5 + NEW-6 fix: typed InvestigationNoteResponse + fixed timestamp.
      return {
        id: MOCK_NOTE_ID,
        investigation_id: id,
        text: req.text,
        created_by: "mock-user",
        created_at: MOCK_FIXED_TIMESTAMP,
      };
    },

    async listRuleFirings(_params) {
      return { results: [], total: 0 };
    },

    async listMlScores(_params) {
      return { results: [], total: 0 };
    },

    async getMlScoreFeatures(_scoreId) {
      // Use a fixed UUID — score_id must be a valid UUID per MlScoreFeaturesSchema.
      return { score_id: "99999999-0000-0000-0000-000000000001", features: [] };
    },

    async listHolds(_params) {
      return { results: MOCK_HOLDS, total: MOCK_HOLDS.length };
    },

    async releaseHold(holdId, req) {
      // R3 NEW-6 fix: deterministic timestamp so test replays are stable.
      return {
        hold_id: holdId,
        status: "released",
        released_at: MOCK_FIXED_TIMESTAMP,
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

    async listGraphRuns(_params) {
      return { results: [MOCK_GRAPH_RUN], total: 1 };
    },

    async getGraphRun(_runId) {
      return MOCK_GRAPH_RUN;
    },

    async getFraudRing(_id) {
      return MOCK_FRAUD_RING;
    },

    async getRecoveryAggregations(_params) {
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
      return {
        ...MOCK_THRESHOLD_CONFIG,
        version: 2,
        // reason is not a field in ThresholdConfig — strip it
        updated_by: "mock-user",
        effective_at: MOCK_FIXED_TIMESTAMP,
        ...(req.rule_thresholds && { rule_thresholds: req.rule_thresholds }),
        ...(req.ml_score_thresholds && { ml_score_thresholds: req.ml_score_thresholds }),
        ...(req.graph_density_threshold && { graph_density_threshold: req.graph_density_threshold }),
        ...(req.accumulator_anomaly_sensitivity && { accumulator_anomaly_sensitivity: req.accumulator_anomaly_sensitivity }),
      };
    },

    async listAccumulatorAnomalies(_params) {
      return { results: [], total: 0 };
    },

    async probeHealth() {
      return { ok: true, latency_ms: 0 };
    },
  };
}
