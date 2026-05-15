import { describe, it, expect } from "vitest";
import { createMockPrescriberDirectoryClient } from "../impls/prescriber-directory/mock.js";
import { PRESCRIBER_DIRECTORY_CACHE_POLICIES } from "../impls/prescriber-directory/client.js";
import { CachePolicySchema } from "../cache-policy.js";

describe("MockPrescriberDirectoryClient", () => {
  const client = createMockPrescriberDirectoryClient();

  it("exposes the expected name", () => {
    expect(client.name).toBe("prescriber-directory");
  });

  it("exposes cache policies that validate against CachePolicySchema", () => {
    for (const [op, policy] of Object.entries(client.cachePolicies)) {
      const result = CachePolicySchema.safeParse(policy);
      expect(result.success, `${op} policy should validate`).toBe(true);
    }
  });

  it("search returns matches by last_name", async () => {
    const r = await client.search({ q: "Smith", limit: 20 });
    expect(r.results.length).toBeGreaterThanOrEqual(1);
    expect(r.results[0]?.last_name).toBe("Smith");
  });

  it("search returns matches by NPI substring", async () => {
    const r = await client.search({ q: "1234567893", limit: 20 });
    expect(r.results.length).toBe(1);
    expect(r.results[0]?.npi).toBe("1234567893");
  });

  it("search respects state filter", async () => {
    const r = await client.search({ q: "M", state: "NY", limit: 20 });
    expect(r.results.every((p) => p.state === "NY")).toBe(true);
  });

  it("search honors limit", async () => {
    const r = await client.search({ q: "M", limit: 1 });
    expect(r.results.length).toBeLessThanOrEqual(1);
  });

  it("getByNpi returns the matching prescriber", async () => {
    const p = await client.getByNpi("1234567893");
    expect(p?.first_name).toBe("Jane");
  });

  it("getByNpi returns null for unknown NPI", async () => {
    const p = await client.getByNpi("9999999999");
    expect(p).toBeNull();
  });

  it("probeHealth returns ok:true for mock", async () => {
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
  });

  it("PRESCRIBER_DIRECTORY_CACHE_POLICIES has both operations", () => {
    expect(PRESCRIBER_DIRECTORY_CACHE_POLICIES).toHaveProperty("search");
    expect(PRESCRIBER_DIRECTORY_CACHE_POLICIES).toHaveProperty("getByNpi");
  });
});

// ── RealImpl tests via injected fetch (no network) ──
import { createRealPrescriberDirectoryClient } from "../impls/prescriber-directory/real.js";

describe("RealPrescriberDirectoryClient (injected fetch)", () => {
  function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
    return new Response(JSON.stringify(body), {
      ...init,
      headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    });
  }

  it("attaches Bearer token + correlation header on every request", async () => {
    const captured: { headers: Headers; url: string }[] = [];
    const fakeFetch: typeof fetch = async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : (input as Request).url;
      captured.push({ headers: new Headers(init?.headers), url });
      return jsonResponse({ results: [], total: 0 });
    };
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test",
      getAuthToken: async () => "tok-abc",
      fetch: fakeFetch,
    });
    await client.search({ q: "Smith", limit: 20 });
    expect(captured[0]?.headers.get("authorization")).toBe("Bearer tok-abc");
    expect(captured[0]?.headers.get("x-correlation-id")).toMatch(/^[0-9a-f-]{36}$/);
    expect(captured[0]?.url).toContain("/prescribers/search");
  });

  it("parses a successful search response via zod", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse({
      results: [{
        npi: "1234567893", first_name: "Jane", last_name: "Smith", credential: "MD",
        primary_specialty: "Internal Medicine", state: "NY", zip: "10001", active: true,
      }],
      total: 1,
    });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const res = await client.search({ q: "Smith", limit: 20 });
    expect(res.results[0]?.last_name).toBe("Smith");
    expect(res.total).toBe(1);
  });

  it("getByNpi returns null on HTTP 404", async () => {
    const fakeFetch: typeof fetch = async () => new Response(null, { status: 404 });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const p = await client.getByNpi("9999999999");
    expect(p).toBeNull();
  });

  it("rejects responses that do not match the zod schema", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse({ wrong: "shape" });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.search({ q: "S", limit: 20 })).rejects.toThrow();
  });

  it("maps an error envelope from a 4xx/5xx response to an error with the code", async () => {
    const fakeFetch: typeof fetch = async () => jsonResponse(
      { error: { code: "RATE_LIMITED", message: "Slow down", correlation_id: "550e8400-e29b-41d4-a716-446655440099" } },
      { status: 429 },
    );
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    await expect(client.search({ q: "S", limit: 20 })).rejects.toMatchObject({ code: "RATE_LIMITED" });
  });

  it("probeHealth pings /health and reports latency", async () => {
    const fakeFetch: typeof fetch = async () => new Response("OK", { status: 200 });
    const client = createRealPrescriberDirectoryClient({
      baseUrl: "http://x.test", getAuthToken: async () => "t", fetch: fakeFetch,
    });
    const h = await client.probeHealth();
    expect(h.ok).toBe(true);
    expect(typeof h.latency_ms).toBe("number");
  });
});
