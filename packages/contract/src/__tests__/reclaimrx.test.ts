// packages/contract/src/__tests__/reclaimrx.test.ts
// SP-3 ReclaimRx contract tests.
// Tests mock + real implementations against Zod schemas.
// Covers: auth headers, error envelopes, Zod parse failures, network errors.
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
  SPEC_55_ENDPOINT_COVERAGE,
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

  it("transitionInvestigation returns transition record with new status", async () => {
    const list = await client.listInvestigations({ status: "open" });
    const id = list.results[0]!.id;
    const result = await client.transitionInvestigation(id, { to_status: "in_progress", reason: "Reviewing" });
    expect(result.to_status).toBe("in_progress");
  });

  it("addInvestigationNote returns InvestigationNoteResponse with deterministic id", async () => {
    const list = await client.listInvestigations();
    const id = list.results[0]!.id;
    const res = await client.addInvestigationNote(id, { text: "Test note" });
    expect(res.id).toBeDefined();
    expect(res.investigation_id).toBe(id);
    expect(res.text).toBe("Test note");
    expect(res.created_at).toBe("2026-05-18T00:00:00.000Z");
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

  it("SPEC_55_ENDPOINT_COVERAGE has exactly 18 entries", () => {
    expect(SPEC_55_ENDPOINT_COVERAGE.length).toBe(18);
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
        hold_id: "55555555-0000-0000-0000-000000000001",
        status: "released",
        released_at: "2026-05-18T12:00:00Z",
        released_by: "user",
        reason: "done",
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

  // ── R1 BLOCK 9 fix — Zod parse failure per GET endpoint ──────────────────
  // Parametrized test: every GET endpoint must reject a malformed response body.
  // Uses SPEC_55_ENDPOINT_COVERAGE matrix so additions stay in sync automatically.
  it.each(SPEC_55_ENDPOINT_COVERAGE.filter((e) => e.method === "GET"))(
    "endpoint #$n ($path) rejects malformed body via zod",
    async ({ path }) => {
      const fakeFetch: typeof fetch = async () => jsonResponse({ wrong: "shape" });
      const client = createRealReclaimRxClient({
        baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
      });
      const method = pickClientMethodForPath(client, path);
      await expect(method()).rejects.toThrow();
    },
  );

  // 403 TENANT_MISMATCH branch — spec-correct error code propagation
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

  // Network-error branch — fetch itself rejects (DNS, TLS, ECONNREFUSED)
  it("authedFetch propagates network errors with a typed NETWORK_ERROR code", async () => {
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

  // Empty body / non-parseable JSON — MALFORMED_RESPONSE branch
  it("rejects 200 OK with empty body as MALFORMED_RESPONSE", async () => {
    const fakeFetch: typeof fetch = async () =>
      new Response("", { status: 200, headers: { "content-type": "application/json" } });
    const client = createRealReclaimRxClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.listInvestigations()).rejects.toMatchObject({
      code: "MALFORMED_RESPONSE",
    });
  });
});


// Test helper — maps a spec path to the matching client method.
// Throws on unknown path so a missing method is caught at test time.
// Detail paths use a stub PLACEHOLDER id — the test only cares that
// authedFetch + unwrap fire, not what the id value is.
function pickClientMethodForPath(
  client: ReclaimRxClient,
  path: string,
): () => Promise<unknown> {
  const PLACEHOLDER = "00000000-0000-0000-0000-000000000000";
  const map: Record<string, () => Promise<unknown>> = {
    "/investigations":                () => client.listInvestigations(),
    "/holds":                         () => client.listHolds(),
    "/graph-runs":                    () => client.listGraphRuns(),
    "/recovery":                      () => client.getRecoveryAggregations(),
    "/dashboard-summary":             () => client.getDashboardSummary(),
    "/thresholds":                    () => client.getThresholds(),
    "/accumulator-anomalies":         () => client.listAccumulatorAnomalies(),
    "/ml-scores":                     () => client.listMlScores(),
    "/rule-firings":                  () => client.listRuleFirings(),
    "/investigations/{id}":           () => client.getInvestigation(PLACEHOLDER),
    "/ml-scores/{id}/features":       () => client.getMlScoreFeatures(PLACEHOLDER),
    "/graph-runs/{run_id}":           () => client.getGraphRun(PLACEHOLDER),
    "/fraud-rings/{id}":              () => client.getFraudRing(PLACEHOLDER),
  };
  const handler = map[path];
  if (!handler) {
    throw new Error(`No client method registered for path "${path}".`);
  }
  return handler;
}
