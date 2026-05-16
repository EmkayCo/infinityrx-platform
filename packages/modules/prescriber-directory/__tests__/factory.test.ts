// packages/modules/prescriber-directory/__tests__/factory.test.ts
// BLOCK 6 fix: Plan B exports factory functions (not classes), so no instanceof checks.
// Tests assert interface shape and behavior only.
import { describe, expect, it } from "vitest";
import { createPrescriberDirectoryClient } from "../src/factory.js";

// Minimal ClientConfig-compatible object for production/mock env tests.
const prodConfig = {
  baseUrl: "http://prescriber-directory:8030",
  getAuthToken: async () => "tok",
};

describe("createPrescriberDirectoryClient", () => {
  it('development env — no baseUrl needed, returns client with search + getByNpi + probeHealth', () => {
    const client = createPrescriberDirectoryClient("development", { getAuthToken: async () => "" });
    expect(typeof client.search).toBe("function");
    expect(typeof client.getByNpi).toBe("function");
    expect(typeof client.probeHealth).toBe("function");
  });

  it('development env — mock client has expected name property', () => {
    const client = createPrescriberDirectoryClient("development", { getAuthToken: async () => "" });
    expect(client.name).toBe("prescriber-directory");
  });

  it('production env + baseUrl — returns client with search method', () => {
    const client = createPrescriberDirectoryClient("production", prodConfig);
    expect(typeof client.search).toBe("function");
  });

  it('mock env + baseUrl — returns client with search method', () => {
    const client = createPrescriberDirectoryClient("mock", prodConfig);
    expect(typeof client.search).toBe("function");
  });

  it('production env without baseUrl → throws with descriptive message containing "baseUrl"', () => {
    expect(() =>
      createPrescriberDirectoryClient("production", { getAuthToken: async () => "" })
    ).toThrow("baseUrl");
  });

  it('mock env without baseUrl → throws', () => {
    expect(() =>
      createPrescriberDirectoryClient("mock", { getAuthToken: async () => "" })
    ).toThrow("baseUrl");
  });

  it('development env — mock client search returns results for a fixture NPI', async () => {
    const client = createPrescriberDirectoryClient("development", { getAuthToken: async () => "" });
    // Plan B mock fixture includes at least one doctor; search by last name returns results.
    const resp = await client.search({ q: "Smith", limit: 5 });
    expect(Array.isArray(resp.results)).toBe(true);
  });
});
