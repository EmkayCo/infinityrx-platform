import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("../auth/auth.config.js", () => ({ auth: vi.fn() }));
vi.mock("@infinityrx/auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@infinityrx/auth")>();
  return {
    ...actual,
    verifyAccessToken: vi.fn(),
    resolveEnvClaim: vi.fn().mockReturnValue("development"),
  };
});

// React.cache is a no-op in test env — module must still export verifySessionToken.
vi.mock("react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react")>();
  return { ...actual, cache: (fn: unknown) => fn };
});

import { auth } from "../auth/auth.config.js";
import { verifyAccessToken } from "@infinityrx/auth";

// verifySessionToken is imported AFTER mocks are set up.
// Using dynamic import ensures the mocked react.cache and auth are used.
const { verifySessionToken } = await import("../auth/verify-session-token.js");

describe("verifySessionToken", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.JWT_SECRET = "test-secret-at-least-32-chars-long-abc";
    process.env.INFINITYRX_ENV = "development";
  });

  it("returns false when session is absent", async () => {
    vi.mocked(auth).mockResolvedValue(null as never);
    const result = await verifySessionToken();
    expect(result).toBe(false);
  });

  it("returns false when session has no accessToken", async () => {
    vi.mocked(auth).mockResolvedValue({ user: { sub: "u1" } } as never);
    const result = await verifySessionToken();
    expect(result).toBe(false);
  });

  it("returns true when verifyAccessToken resolves (valid token)", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: { sub: "u1", accessToken: "valid.jwt.token" },
    } as never);
    vi.mocked(verifyAccessToken).mockResolvedValue({
      sub: "u1", tid: "t1", roles: [], typ: "access",
      iat: 0, exp: 9999999999, jti: "jti-1",
      iss: "infinityrx", aud: "infinityrx-backend", env: "development",
    });
    const result = await verifySessionToken();
    expect(result).toBe(true);
    expect(vi.mocked(verifyAccessToken)).toHaveBeenCalledOnce();
  });

  it("returns false when verifyAccessToken throws (revoked or expired token)", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: { sub: "u1", accessToken: "expired.jwt.token" },
    } as never);
    vi.mocked(verifyAccessToken).mockRejectedValue(new Error("REVOKED_TOKEN"));
    const result = await verifySessionToken();
    expect(result).toBe(false);
  });
});
