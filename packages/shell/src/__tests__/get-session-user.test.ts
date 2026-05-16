import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the auth.config binding and server-only before importing module under test.
// This ensures we test the session-extraction logic without running the full
// next-auth JWT callback chain (which requires Plan B's verifyAccessToken).
vi.mock("../auth/auth.config.js", () => ({
  auth: vi.fn(),
}));
vi.mock("server-only", () => ({}));

import { auth } from "../auth/auth.config.js";
import { getSessionUser } from "../auth/get-session-user.js";

describe("getSessionUser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("returns null when session is absent", async () => {
    vi.mocked(auth).mockResolvedValue(null as never);
    expect(await getSessionUser()).toBeNull();
  });

  it("returns null when session.user is missing required fields", async () => {
    vi.mocked(auth).mockResolvedValue({ user: { sub: "u1" } } as never);
    expect(await getSessionUser()).toBeNull();
  });

  it("returns UserIdentity with correct shape when session is valid", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: {
        sub: "00000000-0000-0000-0000-000000000001",
        tid: "00000000-0000-0000-0000-000000000002",
        roles: ["platform_admin"],
        mfaEnrolled: true,
      },
    } as never);
    const user = await getSessionUser();
    expect(user).toEqual({
      sub: "00000000-0000-0000-0000-000000000001",
      tid: "00000000-0000-0000-0000-000000000002",
      roles: ["platform_admin"],
      mfaEnrolled: true,
    });
  });

  it("defaults mfaEnrolled to false when not present in session", async () => {
    vi.mocked(auth).mockResolvedValue({
      user: {
        sub: "u1",
        tid: "t1",
        roles: [],
      },
    } as never);
    const user = await getSessionUser();
    expect(user?.mfaEnrolled).toBe(false);
  });
});
