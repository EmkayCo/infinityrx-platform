import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { KpiCard } from "@/components/ui/kpi-card";

describe("KpiCard", () => {
  it("renders label and raw value", () => {
    render(<KpiCard label="Claims" value={1234} />);
    expect(screen.getByText("Claims")).toBeDefined();
    expect(screen.getByText("1,234")).toBeDefined();
  });

  it("formats currency", () => {
    render(<KpiCard label="Revenue" value="1234.5" format="currency" />);
    expect(screen.getByText("$1,234.50")).toBeDefined();
  });

  it("formats compact currency for millions", () => {
    render(<KpiCard label="Spend" value={5_250_000} format="currency-compact" />);
    expect(screen.getByText("$5.25M")).toBeDefined();
  });

  it("renders trend with up direction", () => {
    render(
      <KpiCard
        label="Growth"
        value={100}
        trend={{ value: 12.5, direction: "up", label: "vs prior" }}
      />,
    );
    expect(screen.getByText("12.5%")).toBeDefined();
    expect(screen.getByText("vs prior")).toBeDefined();
  });

  it("wraps card in link when href provided", () => {
    render(<KpiCard label="Claims" value={100} href="/claims" />);
    const link = screen.getByRole("link");
    expect(link.getAttribute("href")).toBe("/claims");
  });
});
