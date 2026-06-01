/**
 * Smoke tests for nav-config: verifies all paysync surface routes are declared
 * in the Billing & PaySync module's children list, and reclaimrx has the
 * detection-console routes (runs + upload).
 */
import { describe, it, expect } from "vitest";
import { NAV_MODULES } from "./nav-config";

const paySync = NAV_MODULES.find((m) => m.label === "Billing & PaySync");
const reclaimrx = NAV_MODULES.find((m) => m.label === "ReclaimRx");

describe("nav-config paysync surface routes", () => {
  it("Billing & PaySync module exists", () => {
    expect(paySync).toBeDefined();
  });

  const expectedHrefs = [
    "/admin/paysync/cycles",
    "/admin/paysync/batches",
    "/admin/paysync/carryovers",
    "/admin/paysync/invoices",
    "/admin/paysync/payment-runs",
    "/admin/paysync/files",
    "/admin/paysync/bank-settlements",
    "/admin/paysync/reconciliations",
    "/admin/paysync/journal",
    "/admin/paysync/uploads",
  ];

  for (const href of expectedHrefs) {
    it(`has nav entry for ${href}`, () => {
      const child = paySync?.children?.find((c) => c.href === href);
      expect(child).toBeDefined();
    });
  }
});

describe("nav-config reclaimrx detection-console routes", () => {
  it("ReclaimRx module exists", () => {
    expect(reclaimrx).toBeDefined();
  });

  it("has Detection Runs nav entry at /reclaimrx/runs", () => {
    const child = reclaimrx?.children?.find((c) => c.href === "/reclaimrx/runs");
    expect(child).toBeDefined();
    expect(child?.label).toBe("Detection Runs");
  });

  it("has Upload CSV nav entry at /reclaimrx/upload", () => {
    const child = reclaimrx?.children?.find((c) => c.href === "/reclaimrx/upload");
    expect(child).toBeDefined();
    expect(child?.label).toBe("Upload CSV");
  });

  it("still has Leakage Monitor entry at /reclaimrx/leakage", () => {
    const child = reclaimrx?.children?.find((c) => c.href === "/reclaimrx/leakage");
    expect(child).toBeDefined();
  });
});
