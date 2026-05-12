import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StatusTimeline } from "@/components/paysync/status-timeline";

describe("StatusTimeline", () => {
  it("renders all step labels in order", () => {
    render(<StatusTimeline steps={[
      { id: "a", label: "Open", state: "completed", occurredAt: "2026-04-26T10:00:00Z" },
      { id: "b", label: "Closing", state: "current" },
      { id: "c", label: "Closed", state: "pending" },
    ]} />);
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(screen.getByText("Open")).toBeDefined();
    expect(screen.getByText("Closing")).toBeDefined();
    expect(screen.getByText("Closed")).toBeDefined();
  });

  it("strikes through skipped steps", () => {
    render(<StatusTimeline steps={[
      { id: "x", label: "Skipped step", state: "skipped" },
    ]} />);
    const text = screen.getByText("Skipped step");
    expect(text.className).toContain("line-through");
  });

  it("highlights failed steps", () => {
    render(<StatusTimeline steps={[
      { id: "f", label: "Failed step", state: "failed" },
    ]} />);
    const text = screen.getByText("Failed step");
    expect(text.className).toContain("text-rose-500");
  });
});
