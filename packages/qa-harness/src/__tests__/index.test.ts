/**
 * Smoke-tests the qa-harness public surface: verify named exports exist and
 * are of the expected type. This catches regressions where a re-export is
 * accidentally dropped from index.ts.
 */
import { describe, it, expect } from "vitest";
import * as surface from "../index.js";

describe("qa-harness public surface", () => {
  it("exports ServicesHealth component", () => {
    expect(typeof surface.ServicesHealth).toBe("function");
  });

  it("exports MockToggle component", () => {
    expect(typeof surface.MockToggle).toBe("function");
  });

  it("exports CompositionViewer component", () => {
    expect(typeof surface.CompositionViewer).toBe("function");
  });

  it("exports FactoryBindings component", () => {
    expect(typeof surface.FactoryBindings).toBe("function");
  });

  it("exports CorrelationIdJump component", () => {
    expect(typeof surface.CorrelationIdJump).toBe("function");
  });

  it("exports seedPaysync function", () => {
    expect(typeof surface.seedPaysync).toBe("function");
  });

  it("exports PAYSYNC_SEED_BINDING constant", () => {
    expect(surface.PAYSYNC_SEED_BINDING).toBeDefined();
    expect(surface.PAYSYNC_SEED_BINDING.kind).toBe("paysync");
  });

  it("exports DEMO_TENANT_ID constant", () => {
    expect(typeof surface.DEMO_TENANT_ID).toBe("string");
  });

  it("exports fetchTestAuthToken function", () => {
    expect(typeof surface.fetchTestAuthToken).toBe("function");
  });

  it("exports injectJwtIntoContext function", () => {
    expect(typeof surface.injectJwtIntoContext).toBe("function");
  });

  it("exports OPERATOR_USER_ID constant", () => {
    expect(typeof surface.OPERATOR_USER_ID).toBe("string");
  });

  it("exports APPROVER_USER_ID constant", () => {
    expect(typeof surface.APPROVER_USER_ID).toBe("string");
  });

  it("exports AUDITOR_USER_ID constant", () => {
    expect(typeof surface.AUDITOR_USER_ID).toBe("string");
  });

  it("exports cleanupBillingData function", () => {
    expect(typeof surface.cleanupBillingData).toBe("function");
  });

  it("exports BILLING_TRUNCATE_ORDER array", () => {
    expect(Array.isArray(surface.BILLING_TRUNCATE_ORDER)).toBe(true);
  });

  it("exports createPaysyncContext function", () => {
    expect(typeof surface.createPaysyncContext).toBe("function");
  });

  it("exports PAYSYNC_E2E_BASE_URLS object", () => {
    expect(typeof surface.PAYSYNC_E2E_BASE_URLS).toBe("object");
  });
});
