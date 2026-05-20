// Stub: verifies package index exports the reclaimrx client (SP-3).
// Full coverage in reclaimrx.test.ts.
import { describe, it, expect } from "vitest";
import {
  createMockReclaimRxClient,
  createRealReclaimRxClient,
  RECLAIMRX_CACHE_POLICIES,
} from "../index.js";

describe("@infinityrx/contract index — reclaimrx exports", () => {
  it("createMockReclaimRxClient is exported", () => {
    expect(typeof createMockReclaimRxClient).toBe("function");
  });

  it("createRealReclaimRxClient is exported", () => {
    expect(typeof createRealReclaimRxClient).toBe("function");
  });

  it("RECLAIMRX_CACHE_POLICIES is exported", () => {
    expect(typeof RECLAIMRX_CACHE_POLICIES).toBe("object");
  });
});
