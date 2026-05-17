import { describe, it, expect, vi, afterEach } from "vitest";
import { DEMO_TENANT_ID, PAYSYNC_SEED_BINDING, seedPaysync } from "../paysync-seed.js";

describe("paysync-seed constants", () => {
  it("DEMO_TENANT_ID matches the canonical fixture tenant", () => {
    expect(DEMO_TENANT_ID).toBe("t0000000-0000-0000-0000-000000000001");
  });

  it("PAYSYNC_SEED_BINDING has kind 'paysync'", () => {
    expect(PAYSYNC_SEED_BINDING.kind).toBe("paysync");
  });

  it("PAYSYNC_SEED_BINDING label mentions key fixture tables", () => {
    expect(PAYSYNC_SEED_BINDING.label).toMatch(/upload/i);
    expect(PAYSYNC_SEED_BINDING.label).toMatch(/batch/i);
    expect(PAYSYNC_SEED_BINDING.label).toMatch(/journal/i);
  });
});

describe("seedPaysync", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("sends POST to /api/v1/billing/seed with tenant_id in body", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ inserted: 42 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await seedPaysync({ baseURL: "http://localhost:8001" });

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8001/api/v1/billing/seed");
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body as string) as Record<string, unknown>;
    expect(body.tenant_id).toBe(DEMO_TENANT_ID);
    expect(result.ok).toBe(true);
    expect(result.status).toBe(200);
  });

  it("includes Authorization header when token is provided", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });
    vi.stubGlobal("fetch", mockFetch);

    await seedPaysync({ baseURL: "http://localhost:8001", token: "test-token-abc" });

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer test-token-abc");
  });

  it("throws on non-2xx response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ error: "forbidden" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(seedPaysync({ baseURL: "http://localhost:8001" })).rejects.toThrow("403");
  });
});
