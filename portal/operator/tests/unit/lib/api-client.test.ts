/**
 * Tests for api-client header wiring.
 *
 * The contract under test: every outbound GET carries both an
 * Authorization Bearer token AND an x-tenant-id header. Either one
 * missing breaks the request — Authorization missing -> 401, x-tenant-id
 * missing -> 422 Field required. Both must be set BEFORE the request
 * reaches the network, which is why this is a unit test that mocks
 * global.fetch and inspects the merged RequestInit.
 */
import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { apiGet, configureApiClient } from "@shared/lib/api-client";

// The api-client treats isMockEnabled() === true as "return mocks, don't fetch."
// We need real-fetch behavior for these tests.
vi.mock("@shared/lib/mock-data", () => ({
  isMockEnabled: () => false,
  mockResponse: () => Promise.reject(new Error("mock should not be called")),
}));

describe("api-client header wiring", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );
    // @ts-expect-error — assigning to global for the duration of the test
    global.fetch = fetchMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    configureApiClient({ tokenProvider: async () => null });
  });

  it("sends Authorization Bearer when tokenProvider returns a token", async () => {
    configureApiClient({ tokenProvider: async () => "tok-123" });
    await apiGet("http://x/y");
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer tok-123");
  });

  it("sends x-tenant-id header from tenantProvider", async () => {
    configureApiClient({
      tokenProvider: async () => "tok-123",
      tenantProvider: async () => "a0000000-0000-0000-0000-000000000001",
    });
    await apiGet("http://x/y");
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["x-tenant-id"]).toBe("a0000000-0000-0000-0000-000000000001");
  });

  it("omits Authorization when tokenProvider returns null", async () => {
    configureApiClient({ tokenProvider: async () => null });
    await apiGet("http://x/y");
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["Authorization"]).toBeUndefined();
  });

  it("falls back to NEXT_PUBLIC_DEFAULT_TENANT_ID when tenantProvider yields nothing", async () => {
    process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID =
      "a0000000-0000-0000-0000-000000000001";
    configureApiClient({ tokenProvider: async () => "tok" });
    await apiGet("http://x/y");
    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers["x-tenant-id"]).toBe(
      "a0000000-0000-0000-0000-000000000001"
    );
    delete process.env.NEXT_PUBLIC_DEFAULT_TENANT_ID;
  });
});
