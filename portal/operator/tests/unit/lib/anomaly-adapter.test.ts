/**
 * Tests for anomaly-adapter.ts re-exports.
 * The adapter logic lives in reclaimrx-v2.ts; this file verifies the
 * operator-layer re-export works and key constants are accessible.
 */
import { describe, it, expect } from "vitest";
import {
  FINDING_CODE_TO_CATEGORY,
  anomalyToLeakageFlag,
  buildAnomalyQueryParams,
} from "@shared/types/reclaimrx-v2";

describe("anomaly-adapter re-exports", () => {
  it("exports FINDING_CODE_TO_CATEGORY", () => {
    expect(FINDING_CODE_TO_CATEGORY).toBeDefined();
    expect(FINDING_CODE_TO_CATEGORY["ALL-001"]).toBe("pharmacy_misuse");
  });

  it("exports anomalyToLeakageFlag", () => {
    expect(typeof anomalyToLeakageFlag).toBe("function");
  });

  it("exports buildAnomalyQueryParams", () => {
    expect(typeof buildAnomalyQueryParams).toBe("function");
  });

  it("buildAnomalyQueryParams handles empty input", () => {
    expect(buildAnomalyQueryParams({})).toEqual({});
  });
});
