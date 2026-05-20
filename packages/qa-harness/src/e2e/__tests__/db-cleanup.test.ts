import { describe, it, expect } from "vitest";
import { BILLING_TRUNCATE_ORDER } from "../db-cleanup.js";

describe("db-cleanup", () => {
  it("BILLING_TRUNCATE_ORDER is a non-empty array of strings", () => {
    expect(Array.isArray(BILLING_TRUNCATE_ORDER)).toBe(true);
    expect(BILLING_TRUNCATE_ORDER.length).toBeGreaterThan(0);
    for (const table of BILLING_TRUNCATE_ORDER) {
      expect(typeof table).toBe("string");
    }
  });

  it("dependent tables appear before parent tables in truncation order", () => {
    // file_artifacts reference batches; batches reference cycles
    const fileIdx = BILLING_TRUNCATE_ORDER.indexOf("billing.file_artifacts");
    const batchIdx = BILLING_TRUNCATE_ORDER.indexOf("billing.payment_batches");
    const cycleIdx = BILLING_TRUNCATE_ORDER.indexOf("billing.payment_cycles");
    expect(fileIdx).toBeGreaterThanOrEqual(0);
    expect(batchIdx).toBeGreaterThanOrEqual(0);
    expect(cycleIdx).toBeGreaterThanOrEqual(0);
    // children must come before parents in truncation order
    expect(fileIdx).toBeLessThan(batchIdx);
    expect(batchIdx).toBeLessThan(cycleIdx);
  });
});
