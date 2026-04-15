import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge, inferStatusVariant } from "@/components/ui/status-badge";

describe("StatusBadge", () => {
  it("renders the status text", () => {
    render(<StatusBadge status="Active" />);
    expect(screen.getByText("Active")).toBeDefined();
  });

  it("infers success variant from 'active'", () => {
    expect(inferStatusVariant("active")).toBe("success");
    expect(inferStatusVariant("ACTIVE")).toBe("success");
    expect(inferStatusVariant("Paid")).toBe("success");
  });

  it("infers error variant from 'reversed'", () => {
    expect(inferStatusVariant("reversed")).toBe("error");
    expect(inferStatusVariant("Disabled")).toBe("error");
    expect(inferStatusVariant("critical")).toBe("error");
  });

  it("falls back to neutral for unknown status", () => {
    expect(inferStatusVariant("xyz")).toBe("neutral");
  });

  it("honors explicit variant prop", () => {
    render(<StatusBadge status="Custom" variant="navy" />);
    const el = screen.getByText("Custom");
    expect(el.className).toMatch(/ifx-navy/);
  });
});
