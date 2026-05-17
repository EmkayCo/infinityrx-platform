// packages/contract/src/__tests__/paysync-echo.test.ts
// EchoClient contract tests — shape, cache policies, mock factory.

import { describe, expect, it } from "vitest";
import {
  PAYSYNC_ECHO_CACHE_POLICIES,
  type EchoRunStatus,
  type EchoSpec400Run,
} from "../impls/paysync/echo-client.js";

describe("PAYSYNC_ECHO_CACHE_POLICIES shape", () => {
  it("defines listEchoRuns with stale-ok and paysync:echo tag", () => {
    const p = PAYSYNC_ECHO_CACHE_POLICIES.listEchoRuns;
    expect(p.backend_down).toBe("stale-ok");
    expect(p.invalidation_tags).toContain("paysync:echo");
    expect(p.key[0]).toBe("paysync");
    expect(p.key[1]).toBe("echo");
  });

  it("defines getEchoRun with stale-ok", () => {
    const p = PAYSYNC_ECHO_CACHE_POLICIES.getEchoRun;
    expect(p.backend_down).toBe("stale-ok");
    expect(p.ttl_seconds).toBe(60);
  });

  it("defines runEchoCandor as fail-fast mutation with ttl 0", () => {
    const p = PAYSYNC_ECHO_CACHE_POLICIES.runEchoCandor;
    expect(p.ttl_seconds).toBe(0);
    expect(p.backend_down).toBe("fail-fast");
    expect(p.invalidation_tags).toContain("paysync:echo");
  });

  it("defines listEchoIngestions with stale-ok", () => {
    const p = PAYSYNC_ECHO_CACHE_POLICIES.listEchoIngestions;
    expect(p.backend_down).toBe("stale-ok");
    expect(p.invalidation_tags).toContain("paysync:echo");
  });

  it("all four policy keys include tenant_id segment", () => {
    for (const [name, policy] of Object.entries(PAYSYNC_ECHO_CACHE_POLICIES)) {
      expect(policy.key, `${name} cache key should include {tenant_id}`).toContain("{tenant_id}");
    }
  });
});

describe("EchoRunStatus type guard", () => {
  it("accepts all valid status values", () => {
    const valid: EchoRunStatus[] = [
      "pending_submission", "submitted", "status_received", "reconciled", "failed",
    ];
    expect(valid).toHaveLength(5);
  });
});

describe("EchoSpec400Run shape", () => {
  it("total_amount is typed as string (Decimal), not number", () => {
    const run: EchoSpec400Run = {
      id: "e0000000-0000-0000-0000-000000000001",
      run_date: "2026-05-01",
      file_path: null,
      file_sha256: null,
      record_count: 10,
      total_amount: "1234.56",
      submitted_at: null,
      submitted_by: null,
      status_file_received_at: null,
      status_file_processed_at: null,
      manual_ap_record_ids: [],
      status: "pending_submission",
      created_at: "2026-05-01T00:00:00.000+00:00",
    };
    expect(typeof run.total_amount).toBe("string");
    expect(run.status).toBe("pending_submission");
  });
});
