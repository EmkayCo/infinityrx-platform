// tests/unit/FreshnessChip.test.tsx
// Green (<7d), yellow (7-14d), red (>14d or null), "Never loaded" for null.
import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { FreshnessChip } from "../../src/components/FreshnessChip.js";

function isoDateDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

describe("FreshnessChip", () => {
  it("renders green indicator when lastRunAt is today (0 days ago)", () => {
    const { container } = render(
      <FreshnessChip sourceKey="nppes" lastRunAt={isoDateDaysAgo(0)} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip).toBeTruthy();
    // Green class present
    expect(chip.className).toMatch(/green/i);
    expect(chip.textContent).toMatch(/0 days? ago/i);
  });

  it("renders green indicator when lastRunAt is 6 days ago", () => {
    const { container } = render(
      <FreshnessChip sourceKey="nppes" lastRunAt={isoDateDaysAgo(6)} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/green/i);
    expect(chip.textContent).toMatch(/6 days? ago/i);
  });

  it("renders yellow indicator when lastRunAt is exactly 7 days ago", () => {
    const { container } = render(
      <FreshnessChip sourceKey="ncpdp" lastRunAt={isoDateDaysAgo(7)} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/yellow/i);
    expect(chip.textContent).toMatch(/7 days? ago/i);
  });

  it("renders yellow indicator when lastRunAt is 14 days ago", () => {
    const { container } = render(
      <FreshnessChip sourceKey="ncpdp" lastRunAt={isoDateDaysAgo(14)} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/yellow/i);
    expect(chip.textContent).toMatch(/14 days? ago/i);
  });

  it("renders red indicator when lastRunAt is 15 days ago", () => {
    const { container } = render(
      <FreshnessChip sourceKey="fda_ndc" lastRunAt={isoDateDaysAgo(15)} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/red/i);
    expect(chip.textContent).toMatch(/15 days? ago/i);
  });

  it("renders red indicator and 'Never loaded' when lastRunAt is null", () => {
    const { container } = render(
      <FreshnessChip sourceKey="fda_ndc" lastRunAt={null} />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/red/i);
    expect(chip.textContent).toMatch(/never loaded/i);
  });

  it("includes the sourceKey label in the rendered output", () => {
    render(<FreshnessChip sourceKey="cms_asp" lastRunAt={isoDateDaysAgo(1)} />);
    expect(screen.getByText(/cms_asp/i)).toBeTruthy();
  });

  it("accepts optional className prop", () => {
    const { container } = render(
      <FreshnessChip sourceKey="nppes" lastRunAt={null} className="extra-class" />,
    );
    const chip = container.firstChild as HTMLElement;
    expect(chip.className).toMatch(/extra-class/);
  });
});
