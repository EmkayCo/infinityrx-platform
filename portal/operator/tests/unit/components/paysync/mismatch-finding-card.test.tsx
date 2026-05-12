import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { MismatchFindingCard } from "@/components/paysync/mismatch-finding-card";

describe("MismatchFindingCard", () => {
  it("renders tie label, category, and detail", () => {
    render(<MismatchFindingCard finding={{
      tie: 2,
      category: "manual_ap_amount_mismatch",
      detail: "Manual AP record total diverges from cycle pay aggregate by $5.00",
      amount: "5.00",
      related_entity_id: null,
    }} />);
    expect(screen.getByText("Tie 2")).toBeDefined();
    expect(screen.getByText("manual_ap_amount_mismatch")).toBeDefined();
    expect(screen.getByText(/Manual AP record total/)).toBeDefined();
    expect(screen.getByText("$5.00")).toBeDefined();
  });

  it("expands to show related entity on click", () => {
    render(<MismatchFindingCard finding={{
      tie: 1,
      category: "claim_missing",
      detail: "Claim X not in invoice line set",
      amount: "100.00",
      related_entity_id: "claim-uuid-12345",
    }} />);
    const button = screen.getByRole("button");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("claim-uuid-12345")).toBeDefined();
  });
});
