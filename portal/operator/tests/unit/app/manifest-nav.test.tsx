// portal/operator/tests/unit/app/manifest-nav.test.tsx
// Tests for ManifestNav server component (Plan D T5 — manifest-driven nav).
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

// Stub node:fs so the test doesn't need a real _generated/manifest.json.
// vitest 4 requires a "default" export when mocking CJS-style node builtins
// that also have named exports — without it the named import binding throws.
vi.mock("node:fs", () => {
  const readFileSync = vi.fn();
  return { default: { readFileSync }, readFileSync };
});

import { readFileSync } from "node:fs";
import { ManifestNav } from "../../../app/_nav/manifest-nav";

describe("ManifestNav", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders nav items for each module in manifest.json", () => {
    vi.mocked(readFileSync).mockReturnValue(
      JSON.stringify({ modules: ["prescriber-directory", "reclaimrx"] })
    );
    render(<ManifestNav />);
    expect(screen.getByText("Prescriber Directory")).toBeDefined();
    expect(screen.getByText("Reclaimrx")).toBeDefined();
  });

  it("renders 'No modules loaded' when manifest has empty modules array", () => {
    vi.mocked(readFileSync).mockReturnValue(JSON.stringify({ modules: [] }));
    render(<ManifestNav />);
    expect(screen.getByText("No modules loaded.")).toBeDefined();
  });

  it("renders gracefully when _generated/manifest.json does not exist (readFileSync throws)", () => {
    vi.mocked(readFileSync).mockImplementation(() => { throw new Error("ENOENT"); });
    render(<ManifestNav />);
    expect(screen.getByText("No modules loaded.")).toBeDefined();
  });

  it("nav links use the module route prefix as href", () => {
    vi.mocked(readFileSync).mockReturnValue(
      JSON.stringify({ modules: ["prescriber-directory"] })
    );
    render(<ManifestNav />);
    const link = screen.getByRole("link", { name: "Prescriber Directory" });
    expect(link.getAttribute("href")).toBe("/prescriber-directory");
  });

  it("nav has accessible aria-label", () => {
    vi.mocked(readFileSync).mockReturnValue(JSON.stringify({ modules: [] }));
    render(<ManifestNav />);
    expect(screen.getByRole("navigation")).toBeDefined();
  });
});
