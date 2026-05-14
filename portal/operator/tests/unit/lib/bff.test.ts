/**
 * B11 w2.x — Real unit tests for lib/bff.ts (codex adversarial R1
 * must-fix #2). Replaces the `export {};` hook-satisfaction stub
 * with actual coverage of:
 *
 *   resolveSession:
 *     - 401 when no session
 *     - 403 when session.access_token is missing
 *     - 403 when session.tenant_id does not match JWT.tid
 *     - ok when everything aligns
 *
 *   forwardJson:
 *     - TIMEOUT when fetch is aborted on the AbortController
 *     - NETWORK when fetch throws (e.g., connection refused)
 *     - UPSTREAM_ERROR when fetch returns non-2xx
 *     - PARSE_ERROR when fetch returns 2xx with non-JSON body
 *     - ok with parsed data on 2xx + JSON
 *     - Authorization + x-tenant-id headers attached on every call
 */
import { describe, it, expect, beforeEach, vi } from "vitest";

// NextAuth `auth()` is mocked at module level. vi.mock factory is
// hoisted by Vitest, so top-level locals it references must be created
// via vi.hoisted() (which is also hoisted). Standard Vitest pattern.
const { authMock } = vi.hoisted(() => ({ authMock: vi.fn() }));
vi.mock("@shared/lib/auth", () => ({ auth: authMock }));

// Import AFTER mock registration so the mock is in effect.
import { resolveSession, forwardJson, type BffSession } from "@/lib/bff";

function makeJwt(claims: Record<string, unknown>): string {
  // Minimal HS256-shaped string. Signature is fake but the body decode
  // path (used by readJwtClaim in bff.ts) only base64-decodes payload[1].
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  const sig = "fake_signature_unused_by_portal_side_decode";
  return `${header}.${payload}.${sig}`;
}

describe("resolveSession", () => {
  beforeEach(() => {
    authMock.mockReset();
  });

  it("returns 401 when no session", async () => {
    authMock.mockResolvedValue(null);
    const r = await resolveSession();
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.response.status).toBe(401);
      const body = (await r.response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("UNAUTHENTICATED");
    }
  });

  it("returns 403 when session is missing access_token", async () => {
    authMock.mockResolvedValue({
      user: { id: "u1", tenant_id: "t1" },
      // no access_token
    });
    const r = await resolveSession();
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.response.status).toBe(403);
      const body = (await r.response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("INCOMPLETE_SESSION");
    }
  });

  it("returns 403 when session.tenant_id does not match JWT.tid", async () => {
    const jwt = makeJwt({ tid: "tenant-from-jwt", sub: "u1" });
    authMock.mockResolvedValue({
      user: { id: "u1", tenant_id: "tenant-DIFFERENT-from-jwt" },
      access_token: jwt,
    });
    const r = await resolveSession();
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.response.status).toBe(403);
      const body = (await r.response.json()) as { error: { code: string } };
      expect(body.error.code).toBe("TENANT_CLAIM_MISMATCH");
    }
  });

  it("returns ok when session, JWT, and tenant all align", async () => {
    const jwt = makeJwt({ tid: "tenant-alpha", sub: "u1" });
    authMock.mockResolvedValue({
      user: {
        id: "u1",
        tenant_id: "tenant-alpha",
        permissions: ["platform_admin"],
      },
      access_token: jwt,
    });
    const r = await resolveSession();
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.session.tenantId).toBe("tenant-alpha");
      expect(r.session.userId).toBe("u1");
      expect(r.session.jwt).toBe(jwt);
      expect(r.session.roles).toContain("platform_admin");
    }
  });

  it("tolerates JWT without tid claim (defense-in-depth, not a hard reject)", async () => {
    // If the JWT has no tid claim at all, we cannot verify mismatch.
    // resolveSession passes through; the backend's own JWT verification
    // is the authoritative gate. This matches a dev-bypass-only path
    // where someone strips tid (the test should NOT 403 in this case
    // because the backend handles its own claim validation).
    const jwt = makeJwt({ sub: "u1" /* no tid */ });
    authMock.mockResolvedValue({
      user: { id: "u1", tenant_id: "tenant-alpha" },
      access_token: jwt,
    });
    const r = await resolveSession();
    expect(r.ok).toBe(true);
  });
});

describe("forwardJson", () => {
  const session: BffSession = {
    jwt: "test.jwt.token",
    tenantId: "tenant-a",
    userId: "u1",
    roles: ["platform_admin"],
  };

  beforeEach(() => {
    vi.useRealTimers();
  });

  it("returns ok+data on 2xx with JSON body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ value: 42 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const r = await forwardJson<{ value: number }>("https://test/api", session);
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.data.value).toBe(42);

    // Authorization + x-tenant-id headers are attached
    const callArgs = fetchMock.mock.calls[0];
    const headers = (callArgs[1] as RequestInit).headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer test.jwt.token");
    expect(headers["x-tenant-id"]).toBe("tenant-a");
  });

  it("returns UPSTREAM_ERROR on non-2xx response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 422 })));

    const r = await forwardJson("https://test/api", session);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.failure.reason).toBe("UPSTREAM_ERROR");
      expect(r.failure.status).toBe(422);
    }
  });

  it("returns NETWORK on fetch throw (connection refused)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("fetch failed: ECONNREFUSED"))
    );

    const r = await forwardJson("https://test/api", session);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.failure.reason).toBe("NETWORK");
      expect(r.failure.status).toBe(0);
    }
  });

  it("returns PARSE_ERROR when backend returns 200 with non-JSON body", async () => {
    // 200 status but body isn't JSON — historically swallowed as
    // {degraded:true}; codex BLOCKED that. Must surface as PARSE_ERROR.
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("not-json-at-all", { status: 200 }))
    );

    const r = await forwardJson("https://test/api", session);
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.failure.reason).toBe("PARSE_ERROR");
      expect(r.failure.status).toBe(200);
    }
  });

  it("returns TIMEOUT when the AbortController fires before fetch resolves", async () => {
    // Simulate timeout: fetch throws an AbortError because controller was
    // aborted. Our forwardJson sets didTimeout=true via the timer callback,
    // so the resulting failure reason should be TIMEOUT (not NETWORK).
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(
      (_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError"))
          );
        })
    );
    vi.stubGlobal("fetch", fetchMock);

    const promise = forwardJson("https://test/api", session, { timeoutMs: 100 });
    await vi.advanceTimersByTimeAsync(150);
    const r = await promise;
    expect(r.ok).toBe(false);
    if (!r.ok) {
      expect(r.failure.reason).toBe("TIMEOUT");
    }
  });
});
