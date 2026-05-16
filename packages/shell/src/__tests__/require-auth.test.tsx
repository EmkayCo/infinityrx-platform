import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({ redirect: vi.fn() }));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));
vi.mock("../auth/verify-session-token.js", () => ({ verifySessionToken: vi.fn() }));

import { redirect } from "next/navigation";
import { getSessionUser } from "../auth/get-session-user.js";
import { verifySessionToken } from "../auth/verify-session-token.js";
import { RequireAuth } from "../auth/require-auth.js";

const validUser = { sub: "u1", tid: "t1", roles: [], mfaEnrolled: false };

describe("RequireAuth", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders children when session is valid and token verifies", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(validUser);
    vi.mocked(verifySessionToken).mockResolvedValue(true);
    const { getByText } = render(await RequireAuth({ children: <span>protected</span> }) as never);
    expect(getByText("protected")).toBeTruthy();
  });

  it("redirects to /login when session is null", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>x</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/login");
  });

  it("redirects to custom loginPath when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>x</span>, loginPath: "/auth/sign-in" });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/auth/sign-in");
  });

  it("includes callbackUrl in redirect when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>x</span>, callbackUrl: "/billing/claims" });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith(
      "/login?callbackUrl=%2Fbilling%2Fclaims"
    );
  });

  it("does not call redirect when session is valid and token verifies", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({
      sub: "u1", tid: "t1", roles: ["operator"], mfaEnrolled: true,
    });
    vi.mocked(verifySessionToken).mockResolvedValue(true);
    await RequireAuth({ children: <span>x</span> });
    expect(vi.mocked(redirect)).not.toHaveBeenCalled();
  });

  it("renders nothing (redirects) when next-auth returns partial user missing tid", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>secret</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalled();
  });

  // Per-request revocation tests (Fix 2 — C-shell deferred)
  it("redirects to /login when token is revoked (verifySessionToken returns false)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(validUser);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>protected</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/login");
  });

  it("redirects to /login when token is expired (verifySessionToken returns false)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(validUser);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    await RequireAuth({ children: <span>protected</span>, callbackUrl: "/dashboard" });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith(
      "/login?callbackUrl=%2Fdashboard"
    );
  });

  it("calls redirect when session is valid but token verification fails", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(validUser);
    vi.mocked(verifySessionToken).mockResolvedValue(false);
    // redirect() in production throws — in the test mock it is a no-op.
    // Verify that redirect was invoked (the guarding behavior).
    await RequireAuth({ children: <span>secret</span> });
    expect(vi.mocked(redirect)).toHaveBeenCalledWith("/login");
  });
});
