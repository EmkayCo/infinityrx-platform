// packages/modules/reclaimrx/tests/unit/module.config.test.ts
// Verifies the reclaimrx module config shape.
import { describe, it, expect } from "vitest";
import config from "../../module.config.js";

describe("reclaimrx module.config", () => {
  it("has name 'reclaimrx'", () => {
    expect(config.name).toBe("reclaimrx");
  });

  it("has navEntry with correct label", () => {
    expect(config.navEntry.label).toBe("ReclaimRx");
  });

  it("requires RECLAIMRX_URL env", () => {
    expect(config.requires.env).toContain("RECLAIMRX_URL");
  });

  it("routes include /reclaimrx", () => {
    expect(config.routes).toContain("/reclaimrx");
  });
});
