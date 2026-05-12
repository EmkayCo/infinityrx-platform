import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StateMachineDiagram } from "@/components/paysync/state-machine-diagram";

describe("StateMachineDiagram", () => {
  const nodes = [
    { id: "draft", label: "Draft" },
    { id: "approved", label: "Approved" },
    { id: "submitted", label: "Submitted" },
    { id: "settled", label: "Settled" },
  ];

  it("renders all node labels", () => {
    render(<StateMachineDiagram nodes={nodes} current="approved" />);
    expect(screen.getByText("Draft")).toBeDefined();
    expect(screen.getByText("Approved")).toBeDefined();
    expect(screen.getByText("Submitted")).toBeDefined();
    expect(screen.getByText("Settled")).toBeDefined();
  });

  it("highlights current node with amber styling", () => {
    render(<StateMachineDiagram nodes={nodes} current="submitted" />);
    const current = screen.getByText("Submitted");
    expect(current.className).toContain("border-amber-500");
  });

  it("marks past nodes with emerald", () => {
    render(<StateMachineDiagram nodes={nodes} current="submitted" />);
    const past = screen.getByText("Draft");
    expect(past.className).toContain("emerald");
  });
});
