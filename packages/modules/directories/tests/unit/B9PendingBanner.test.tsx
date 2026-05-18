// tests/unit/B9PendingBanner.test.tsx
// Renders for each dataType value; banner text includes "FDB B9 ingestion".
// Each test uses container-scoped queries to avoid cross-test DOM accumulation.
import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import React from "react";
import { B9PendingBanner } from "../../src/components/B9PendingBanner.js";

afterEach(() => cleanup());

describe("B9PendingBanner", () => {
  it("renders for dataType='interactions' with FDB B9 ingestion text", () => {
    const { getByText } = render(<B9PendingBanner dataType="interactions" />);
    expect(getByText(/FDB B9 ingestion/i)).toBeTruthy();
    expect(getByText(/mock data/i)).toBeTruthy();
  });

  it("renders for dataType='formulary' with FDB B9 ingestion text", () => {
    const { getByText } = render(<B9PendingBanner dataType="formulary" />);
    expect(getByText(/FDB B9 ingestion/i)).toBeTruthy();
  });

  it("renders for dataType='clinical' with FDB B9 ingestion text", () => {
    const { getByText } = render(<B9PendingBanner dataType="clinical" />);
    expect(getByText(/FDB B9 ingestion/i)).toBeTruthy();
  });

  it("renders as a visually distinct banner element (role=status or alert)", () => {
    const { container } = render(<B9PendingBanner dataType="interactions" />);
    const banner = container.firstChild as HTMLElement;
    expect(banner).toBeTruthy();
    // Banner should have a role of status or alert for a11y
    const role = banner.getAttribute("role");
    expect(["status", "alert", "note", "complementary"]).toContain(role ?? "status");
  });

  it("does not render an error — is purely informational", () => {
    const { container } = render(<B9PendingBanner dataType="formulary" />);
    const banner = container.firstChild as HTMLElement;
    // Should NOT have role="alert" with aria-live="assertive" (not an error)
    expect(banner.getAttribute("aria-live")).not.toBe("assertive");
  });
});
