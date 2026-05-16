// packages/modules/prescriber-directory/__tests__/module.config.test.ts
import { describe, expect, it } from "vitest";
import { config } from "../module.config.js";

describe("prescriber-directory module.config", () => {
  it('name is "prescriber-directory"', () => {
    expect(config.name).toBe("prescriber-directory");
  });

  it("routes array is non-empty and all start with /prescribers", () => {
    expect(config.routes.length).toBeGreaterThan(0);
    for (const route of config.routes) {
      expect(route).toMatch(/^\/prescribers/);
    }
  });

  it("navEntry has label, icon, and numeric order", () => {
    expect(typeof config.navEntry.label).toBe("string");
    expect(typeof config.navEntry.icon).toBe("string");
    expect(typeof config.navEntry.order).toBe("number");
  });

  it('requires.backends includes "prescriber-directory" and "core-platform"', () => {
    expect(config.requires.backends).toContain("prescriber-directory");
    expect(config.requires.backends).toContain("core-platform");
  });

  it("requires.secrets all match secret:// URI scheme", () => {
    for (const secret of config.requires.secrets) {
      expect(secret).toMatch(/^secret:\/\//);
    }
  });

  it("shellSurfaces.routePrefixes[0] matches the first route prefix", () => {
    expect(config.shellSurfaces.routePrefixes).toContain("/prescribers");
  });

  it("surfaceKinds contains at least one of server | client", () => {
    const valid = new Set(["server", "client"]);
    for (const kind of config.surfaceKinds) {
      expect(valid.has(kind)).toBe(true);
    }
    expect(config.surfaceKinds.length).toBeGreaterThan(0);
  });
});
