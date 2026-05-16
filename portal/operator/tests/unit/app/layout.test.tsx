// portal/operator/tests/unit/app/layout.test.tsx
// Tests that RootLayout passes ManifestNav into the nav slot.
// The existing layout (fonts, Providers, AppShell, auth headers) is preserved;
// we only test the nav slot addition Plan D makes (BLOCK 4 fix).
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

// Stub @/components/layout/app-shell to isolate the nav slot under test.
vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({
    children,
    nav,
    isAuthenticated: _isAuthenticated,
  }: {
    children: React.ReactNode;
    nav?: React.ReactNode;
    isAuthenticated?: boolean;
  }) => (
    <div data-testid="app-shell">
      {nav && <div data-testid="nav-slot">{nav}</div>}
      <div data-testid="main-slot">{children}</div>
    </div>
  ),
}));

// Stub ManifestNav since it reads the filesystem.
vi.mock("../../../app/_nav/manifest-nav", () => ({
  ManifestNav: () => <nav data-testid="manifest-nav">nav stub</nav>,
}));

// Stub next/headers (used by the existing layout's isAuthenticated check).
vi.mock("next/headers", () => ({
  headers: () => Promise.resolve({ get: () => null }),
}));

// Stub font imports so the layout doesn't try to load Google Fonts in test.
vi.mock("next/font/google", () => ({
  Lato: () => ({ variable: "--font-lato" }),
  IBM_Plex_Mono: () => ({ variable: "--font-ibm-mono" }),
}));

vi.mock("@shared/components/theme-toggle", () => ({
  themeInitScript: "",
}));

vi.mock("@/components/providers", () => ({
  Providers: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Import layout AFTER mocks are set up.
import RootLayout from "../../../app/layout";

describe("RootLayout (Plan D surgical additions)", () => {
  it("ManifestNav is passed into AppShell nav slot", async () => {
    const jsx = await RootLayout({ children: <span data-testid="child">x</span> });
    render(jsx as React.ReactElement);
    expect(screen.getByTestId("nav-slot")).toBeDefined();
    expect(screen.getByTestId("manifest-nav")).toBeDefined();
  });

  it("children are still rendered (existing layout shell preserved)", async () => {
    const jsx = await RootLayout({ children: <div data-testid="page-content">Hello</div> });
    render(jsx as React.ReactElement);
    expect(screen.getByTestId("page-content")).toBeDefined();
  });
});
