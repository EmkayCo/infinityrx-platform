// packages/contract/src/impls/reclaimrx/real.ts
// SP-3 ReclaimRx real client factory.
// Mirrors createRealPrescriberDirectoryClient pattern.
// authedFetch: Bearer token + correlation header on every request.
// unwrap: Zod parse + isErrorEnvelope error mapping.
import type { ReclaimRxClient } from "./client.js";
import { RECLAIMRX_CACHE_POLICIES } from "./client.js";
import type { ClientConfig } from "../../client-base.js";
import { isErrorEnvelope } from "../../error-envelope.js";
import {
  InvestigationListResponseSchema,
  InvestigationDetailResponseSchema,
  InvestigationTransitionResponseSchema,
  InvestigationTransitionRequestSchema,
  InvestigationNoteResponseSchema,
  RuleFiringListResponseSchema,
  MlScoreListResponseSchema,
  MlScoreFeaturesSchema,
  HoldListResponseSchema,
  HoldReleaseResponseSchema,
  HoldReleaseRequestSchema,
  GraphRunTriggerResponseSchema,
  GraphRunListResponseSchema,
  GraphRunDetailResponseSchema,
  FraudRingDetailResponseSchema,
  RecoveryAggregationResponseSchema,
  DashboardSummarySchema,
  ThresholdConfigSchema,
  ThresholdUpdateRequestSchema,
  AccumulatorAnomalyListResponseSchema,
} from "./types.js";
import type {
  InvestigationListParams,
  ListParams,
  RecoveryParams,
} from "./client.js";

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
    // R2 BLOCK 9 fix — wrap fetch in try/catch so DNS, TLS, ECONNREFUSED,
    // or AbortError surface as a typed RealClientError with code "NETWORK_ERROR".
    const token = await config.getAuthToken();
    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Content-Type", "application/json");
    headers.set(correlationHeader, crypto.randomUUID());
    try {
      return await fetchImpl(`${baseUrl}/api/v1/reclaimrx${path}`, {
        ...init,
        headers,
      });
    } catch (err) {
      throw new RealClientError(
        "NETWORK_ERROR",
        err instanceof Error ? err.message : "fetch failed",
        undefined,
      );
    }
  }

  async function unwrap<T>(res: Response, schema: { parse(raw: unknown): T }): Promise<T> {
    // R2 BLOCK 9 follow-up — guard against empty-body / non-JSON responses.
    let body: unknown;
    try {
      body = (await res.json()) as unknown;
    } catch (err) {
      throw new RealClientError(
        "MALFORMED_RESPONSE",
        err instanceof Error ? err.message : "response body is not valid JSON",
        undefined,
      );
    }
    if (!res.ok) {
      if (isErrorEnvelope(body)) {
        throw new RealClientError(body.error.code, body.error.message, body.error.correlation_id);
      }
      throw new RealClientError(
        "UNEXPECTED_ERROR_SHAPE",
        `Unexpected error shape: HTTP ${res.status}`,
        undefined,
      );
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
    // R2 NEW-1 fix: use InvestigationDetailResponseSchema (extended) not the base.
    async getInvestigation(id: string) {
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}`);
      return unwrap(res, InvestigationDetailResponseSchema);
    },

    // Endpoint #3 — POST /investigations/{id}/transitions
    // R2 NEW-1 fix: use InvestigationTransitionResponseSchema (dedicated).
    async transitionInvestigation(id: string, req) {
      const validated = InvestigationTransitionRequestSchema.parse(req);
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}/transitions`, {
        method: "POST",
        body: JSON.stringify(validated),
      });
      return unwrap(res, InvestigationTransitionResponseSchema);
    },

    // Endpoint #4 — POST /investigations/{id}/notes
    // R2 NEW-1 fix: use InvestigationNoteResponseSchema (dedicated typed shape).
    async addInvestigationNote(id: string, req) {
      const res = await authedFetch(`/investigations/${encodeURIComponent(id)}/notes`, {
        method: "POST",
        body: JSON.stringify(req),
      });
      return unwrap(res, InvestigationNoteResponseSchema);
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
    // R2 NEW-1 fix: use GraphRunDetailResponseSchema.
    async getGraphRun(runId: string) {
      const res = await authedFetch(`/graph-runs/${encodeURIComponent(runId)}`);
      return unwrap(res, GraphRunDetailResponseSchema);
    },

    // Endpoint #13 — GET /fraud-rings/{id}
    // R2 NEW-1 fix: detail schema alias.
    async getFraudRing(id: string) {
      const res = await authedFetch(`/fraud-rings/${encodeURIComponent(id)}`);
      return unwrap(res, FraudRingDetailResponseSchema);
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
