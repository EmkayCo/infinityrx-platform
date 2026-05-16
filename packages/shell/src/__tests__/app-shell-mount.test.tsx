import { describe, it, expect, vi, beforeEach } from "vitest";
import { render } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("../auth/get-session-user.js", () => ({ getSessionUser: vi.fn() }));
// Mock AppShell to verify the nav slot is passed correctly.
vi.mock("@infinityrx/ui", () => ({
  AppShell: vi.fn(({ children, nav, header }: { children: unknown; nav?: unknown; header?: unknown }) => (
    <div>
      {header !== undefined && <div data-testid="header-slot">{header as never}</div>}
      <div data-testid="nav-slot">{nav as never}</div>
      <main>{children as never}</main>
    </div>
  )),
}));

import { getSessionUser } from "../auth/get-session-user.js";
import { AppShellMount } from "../shell/app-shell-mount.js";
import type { NavEntry } from "../shell/nav-types.js";

const adminUser = { sub: "u1", tid: "t1", roles: ["platform_admin"], mfaEnrolled: true };
const entries: NavEntry[] = [
  { moduleId: "reclaimrx", label: "ReclaimRx", href: "/reclaimrx", iconSlug: "shield", requiredRoles: [] },
];
const manifest = { instance_name: "test", modules: ["reclaimrx"], audience: "operator" };

describe("AppShellMount", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders AppShell with nav slot populated when authenticated", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByTestId, getByText } = render(
      await AppShellMount({
        children: <span>page content</span>,
        navEntries: entries,
        manifest,
      }) as never
    );
    expect(getByTestId("nav-slot")).toBeTruthy();
    expect(getByText("page content")).toBeTruthy();
  });

  it("renders nav slot with only role-permitted entries", async () => {
    vi.mocked(getSessionUser).mockResolvedValue({ ...adminUser, roles: [] });
    // entries[0] has requiredRoles: [] → visible even with no roles
    const { getByText } = render(
      await AppShellMount({ children: <span>c</span>, navEntries: entries, manifest }) as never
    );
    expect(getByText("ReclaimRx")).toBeTruthy();
  });

  it("renders AppShell with empty nav when manifest has no modules", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const emptyManifest = { ...manifest, modules: [] };
    const result = render(
      await AppShellMount({ children: <span>c</span>, navEntries: entries, manifest: emptyManifest }) as never
    );
    // Nav slot should be empty (no links)
    expect(result.queryByRole("link")).toBeNull();
  });

  it("renders children in main slot", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await AppShellMount({ children: <span>my page</span>, navEntries: entries, manifest }) as never
    );
    expect(getByText("my page")).toBeTruthy();
  });

  it("renders AppShell with optional header when provided", async () => {
    vi.mocked(getSessionUser).mockResolvedValue(adminUser);
    const { getByText } = render(
      await AppShellMount({
        children: <span>c</span>,
        navEntries: entries,
        manifest,
        header: <header>My Header</header>,
      }) as never
    );
    expect(getByText("My Header")).toBeTruthy();
  });
});
