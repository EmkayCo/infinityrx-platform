import { describe, it, expect } from "vitest";
import { CachePolicySchema } from "../cache-policy.js";

describe("CachePolicy", () => {
  it("accepts a TTL-only policy", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["prescriber", "by-npi", "{npi}"],
      invalidation_tags: ["prescriber"],
      backend_down: "stale-ok",
    });
    expect(result.success).toBe(true);
  });

  it("rejects ttl_seconds <= 0", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 0,
      key: ["x"],
      invalidation_tags: [],
      backend_down: "fail-fast",
    });
    expect(result.success).toBe(false);
  });

  it("rejects key with empty segment", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["", "by-npi"],
      invalidation_tags: [],
      backend_down: "stale-ok",
    });
    expect(result.success).toBe(false);
  });

  it("rejects unknown backend_down value", () => {
    const result = CachePolicySchema.safeParse({
      ttl_seconds: 60,
      key: ["x"],
      invalidation_tags: [],
      backend_down: "explode",
    });
    expect(result.success).toBe(false);
  });

  it("accepts each of the 3 backend_down values", () => {
    for (const v of ["stale-ok", "fail-fast", "fall-back-to-mock"] as const) {
      const result = CachePolicySchema.safeParse({
        ttl_seconds: 60,
        key: ["x"],
        invalidation_tags: [],
        backend_down: v,
      });
      expect(result.success, `${v} should parse`).toBe(true);
    }
  });
});
