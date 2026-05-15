import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { KPICard } from "../charts/KPICard.js";

describe("KPICard", () => {
  it("renders the label", () => {
    render(<KPICard label="Total Claims" value="1,234" />);
    expect(screen.getByText("Total Claims")).toBeDefined();
  });

  it("renders the value", () => {
    render(<KPICard label="Total Claims" value="1,234" />);
    expect(screen.getByText("1,234")).toBeDefined();
  });

  it("renders positive delta badge", () => {
    render(<KPICard label="Claims" value="1,000" delta="+12%" />);
    expect(screen.getByText("+12%")).toBeDefined();
  });

  it("renders without delta when omitted", () => {
    const { container } = render(<KPICard label="Claims" value="1,000" />);
    expect(container.querySelector(".irx-kpi-card__delta")).toBeNull();
  });
});
