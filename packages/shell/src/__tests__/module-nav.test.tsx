import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));

import { getSessionUser } from "../auth/get-session-user.js";
import { ModuleNav } from "../shell/module-nav.js";
import type { NavEntry } from "../shell/nav-types.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin"], mfaEnrolled: true };

const entries: NavEntry[] = [
  { moduleId: "reclaimrx", label: "ReclaimRx", href: "/reclaimrx", iconSlug: "shield", requiredRoles: [] },
  { moduleId: "billing", label: "Billing", href: "/billing", iconSlug: "dollar", requiredRoles: ["billing_admin"] },
  { moduleId: "paysync", label: "PaySync", href: "/paysync", iconSlug: "refresh", requiredRoles: ["paysync_user"] },
];

describe("ModuleNav", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders all entries accessible to the user's roles", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    // adminUser has platform_admin, not billing_admin or paysync_user
    // reclaimrx has requiredRoles: [] → visible to all
    const { getByText, queryByText } = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx", "billing", "paysync"] }) as never
    );
    expect(getByText("ReclaimRx")).toBeTruthy();
    expect(queryByText("Billing")).toBeNull();
    expect(queryByText("PaySync")).toBeNull();
  });

  it("renders no entries when manifest excludes all provided modules", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { queryByText } = render(
      await ModuleNav({ entries, manifestModules: [] }) as never
    );
    expect(queryByText("ReclaimRx")).toBeNull();
  });

  it("respects manifest ordering: renders entries in manifest order", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["platform_admin", "billing_admin", "paysync_user"] });
    const { getAllByRole } = render(
      await ModuleNav({ entries, manifestModules: ["paysync", "reclaimrx", "billing"] }) as never
    );
    const links = getAllByRole("link").map((el) => el.getAttribute("href"));
    expect(links).toEqual(["/paysync", "/reclaimrx", "/billing"]);
  });

  it("renders entries whose requiredRoles is a superset the user satisfies", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: ["billing_admin"] });
    const { getByText } = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx", "billing"] }) as never
    );
    expect(getByText("Billing")).toBeTruthy();
  });

  it("returns null when session is absent (unauthenticated path)", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(null);
    const result = render(
      await ModuleNav({ entries, manifestModules: ["reclaimrx"] }) as never
    );
    expect(result.queryByRole("link")).toBeNull();
  });
});
