/**
 * Smoke tests for nav-config: verifies all paysync surface routes are declared
 * in the Billing & PaySync module's children list.
 */
import { describe, it, expect } from "vitest";
import { NAV_MODULES } from "./nav-config";

const paySync = NAV_MODULES.find((m) => m.label === "Billing & PaySync");

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
