import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { DeltaDisplay } from "@/components/paysync/delta-display";

describe("DeltaDisplay", () => {
  it("renders match status with green icon and zero delta", () => {
    render(<DeltaDisplay
      label="Tie 1: Claims ↔ Invoice"
      tie={{
        status: "match",
        expected: "1234.56",
        actual: "1234.56",
        delta: "0.00",
        reasons: [],
      }}
    />);
    expect(screen.getByText("Tie 1: Claims ↔ Invoice")).toBeDefined();
    expect(screen.getByText("match")).toBeDefined();
    // Expected and Actual both render $1234.56 — getAllByText handles dupes.
    expect(screen.getAllByText("$1234.56").length).toBe(2);
  });

  it("renders mismatch with reasons list", () => {
    render(<DeltaDisplay
      label="Tie 2"
      tie={{
        status: "mismatch",
        expected: "100.00",
        actual: "95.00",
        delta: "-5.00",
        reasons: ["claim X missing from AP", "manual AP recognition skipped Y"],
      }}
    />);
    expect(screen.getByText("mismatch")).toBeDefined();
    expect(screen.getByText("claim X missing from AP")).toBeDefined();
    expect(screen.getByText("manual AP recognition skipped Y")).toBeDefined();
  });

  it("formats positive delta with leading +", () => {
    render(<DeltaDisplay
      label="t"
      tie={{
        status: "mismatch", expected: "100", actual: "105",
        delta: "5.00", reasons: [],
      }}
    />);
    expect(screen.getByText("+$5.00")).toBeDefined();
  });
});
