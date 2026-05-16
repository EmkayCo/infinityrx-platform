import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));

import { getSessionUser } from "../auth/get-session-user.js";
import { RequireRole } from "../auth/require-role.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin", "billing_admin"], mfaEnrolled: true };

describe("RequireRole", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders children when user has all required roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await RequireRole({ roles: ["platform_admin"], children: <span>admin panel</span> }) as never
    );
    expect(getByText("admin panel")).toBeTruthy();
  });

  it("renders fallback when user is missing a required role", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["billing_admin"] });
    const result = render(
      await RequireRole({
        roles: ["platform_admin"],
        children: <span>restricted</span>,
        fallback: <span>access denied</span>,
      }) as never
    );
    expect(result.queryByText("restricted")).toBeNull();
    expect(result.getByText("access denied")).toBeTruthy();
  });

  it("renders children when required roles is empty (any authenticated user)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: [] });
    const { getByText } = render(
      await RequireRole({ roles: [], children: <span>open</span> }) as never
    );
    expect(getByText("open")).toBeTruthy();
  });

  it("renders fallback (null) when session is absent", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    const result = render(
      await RequireRole({ roles: ["platform_admin"], children: <span>secret</span> }) as never
    );
    expect(result.queryByText("secret")).toBeNull();
  });

  it("renders children when user has a superset of required roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await RequireRole({ roles: ["platform_admin", "billing_admin"], children: <span>both</span> }) as never
    );
    expect(getByText("both")).toBeTruthy();
  });
});
