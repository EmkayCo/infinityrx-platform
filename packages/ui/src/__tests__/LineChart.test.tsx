import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LineChart } from "../charts/LineChart.js";

const data = [
  { month: "Jan", value: 100 },
  { month: "Feb", value: 120 },
];

describe("LineChart", () => {
  it("renders a chart container", () => {
    const { container } = render(
      <LineChart data={data} xKey="month" yKey="value" title="Claims Over Time" />,
    );
    expect(container.querySelector(".irx-line-chart")).toBeDefined();
  });

  it("renders the chart title", () => {
    render(<LineChart data={data} xKey="month" yKey="value" title="Claims Over Time" />);
    expect(screen.getByText("Claims Over Time")).toBeDefined();
  });

  it("renders without crashing on empty data", () => {
    const { container } = render(
      <LineChart data={[]} xKey="month" yKey="value" title="Empty" />,
    );
    expect(container.querySelector(".irx-line-chart")).toBeDefined();
  });
});
