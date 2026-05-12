import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  CycleStatusBadge, BatchStatusBadge, InvoiceStatusBadge,
  ManualApStatusBadge,
} from "@/components/paysync/cycle-status-badge";

describe("paysync status badges", () => {
  it("renders cycle statuses with normalized labels", () => {
    const { rerender } = render(<CycleStatusBadge status="open" />);
    expect(screen.getByText("open")).toBeDefined();
    rerender(<CycleStatusBadge status="closed_finalized" />);
    expect(screen.getByText("closed finalized")).toBeDefined();
  });

  it("renders batch status pending_approval as 'pending approval'", () => {
    render(<BatchStatusBadge status="pending_approval" />);
    expect(screen.getByText("pending approval")).toBeDefined();
  });

  it("renders invoice status partial", () => {
    render(<InvoiceStatusBadge status="partial" />);
    expect(screen.getByText("partial")).toBeDefined();
  });

  it("renders manual AP statuses", () => {
    render(<ManualApStatusBadge status="recognized" />);
    expect(screen.getByText("recognized")).toBeDefined();
  });
});
