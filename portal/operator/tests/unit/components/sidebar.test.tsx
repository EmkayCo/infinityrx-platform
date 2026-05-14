/**
 * B11 w4 — Sidebar single-open accordion unit test.
 *
 * Companion to the e2e test in tests/e2e/b11-dogfood.spec.ts (F-ISSUE-2).
 * This unit test asserts the behavior at the component boundary: clicking
 * a second module collapses the first, exactly one module can be expanded
 * at a time.
 *
 * Pre-w4 behavior (the bug): clicking N modules left all N expanded.
 * Post-w4 behavior: clicking the Nth module collapses N-1 through 1.
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";

// Mock next/navigation — Sidebar reads pathname via usePathname()
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

// Mock useAuth — Sidebar gates modules by permission
vi.mock("@shared/hooks/use-auth", () => ({
  useAuth: () => ({
    user: { id: "test", role: "platform_admin" },
    hasPermission: () => true,
  }),
}));

// Mock the logo — irrelevant to accordion behavior
vi.mock("@/components/ui/ifx-logo", () => ({
  IfxLogo: () => null,
}));

function countExpandedSections(): number {
  // Trigger buttons get aria-expanded="true" when their module is open
  return screen.queryAllByRole("button", { expanded: true }).length;
}

describe("Sidebar accordion (B11 w4 / F-009)", () => {
  beforeEach(() => {
    cleanup();
    localStorage.clear();
  });

  it("starts with at most one module expanded (the active route's module, or none)", () => {
    render(<Sidebar />);
    expect(countExpandedSections()).toBeLessThanOrEqual(1);
  });

  it("clicking a second module collapses the first (single-open accordion)", () => {
    render(<Sidebar />);

    const programsTrigger = screen.getByRole("button", { name: /^Programs$/ });
    const claimsTrigger = screen.getByRole("button", { name: /^Claims$/ });

    fireEvent.click(programsTrigger);
    expect(programsTrigger.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(claimsTrigger);

    // F-009 pre-fix would have BOTH true here. Post-fix: only Claims.
    expect(claimsTrigger.getAttribute("aria-expanded")).toBe("true");
    expect(programsTrigger.getAttribute("aria-expanded")).toBe("false");
    expect(countExpandedSections()).toBe(1);
  });

  it("clicking the same module twice collapses it (toggle)", () => {
    render(<Sidebar />);
    const programsTrigger = screen.getByRole("button", { name: /^Programs$/ });

    fireEvent.click(programsTrigger);
    expect(programsTrigger.getAttribute("aria-expanded")).toBe("true");

    fireEvent.click(programsTrigger);
    expect(programsTrigger.getAttribute("aria-expanded")).toBe("false");
    expect(countExpandedSections()).toBe(0);
  });

  it("clicking through 5 different modules sequentially leaves exactly 1 expanded", () => {
    render(<Sidebar />);
    for (const label of ["Programs", "Claims", "Accounting", "ReclaimRx", "Analytics"]) {
      const trigger = screen.getByRole("button", { name: new RegExp(`^${label}$`) });
      fireEvent.click(trigger);
    }
    expect(countExpandedSections()).toBe(1);
    // The last-clicked module (Analytics) should be the one open
    expect(
      screen.getByRole("button", { name: /^Analytics$/ }).getAttribute("aria-expanded")
    ).toBe("true");
  });

  it("persists the open module to localStorage", () => {
    render(<Sidebar />);
    const claims = screen.getByRole("button", { name: /^Claims$/ });
    fireEvent.click(claims);
    expect(localStorage.getItem("ifx-sidebar-expanded-module")).toBe(JSON.stringify("Claims"));
  });
});
