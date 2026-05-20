import { describe, it, expect } from "vitest";
import { PAYSYNC_E2E_BASE_URLS } from "../browser-context.js";

describe("browser-context", () => {
  it("PAYSYNC_E2E_BASE_URLS exposes portal, billing, and core URLs", () => {
    expect(typeof PAYSYNC_E2E_BASE_URLS.portal).toBe("string");
    expect(typeof PAYSYNC_E2E_BASE_URLS.billing).toBe("string");
    expect(typeof PAYSYNC_E2E_BASE_URLS.core).toBe("string");
  });

  it("portal URL defaults to localhost:3000", () => {
    expect(PAYSYNC_E2E_BASE_URLS.portal).toContain("3000");
  });

  it("billing URL defaults to localhost:8001", () => {
    expect(PAYSYNC_E2E_BASE_URLS.billing).toContain("8001");
  });

  it("core URL defaults to localhost:8000", () => {
    expect(PAYSYNC_E2E_BASE_URLS.core).toContain("8000");
  });
});
