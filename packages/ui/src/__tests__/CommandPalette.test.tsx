import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CommandPalette } from "../command/CommandPalette.js";

const items = [
  { id: "claims", label: "Go to Claims" },
  { id: "billing", label: "Go to Billing" },
];

describe("CommandPalette", () => {
  it("does not show when open is false", () => {
    render(<CommandPalette open={false} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows when open is true", () => {
    render(<CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("renders command items when open", () => {
    render(<CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={() => {}} />);
    expect(screen.getByText("Go to Claims")).toBeDefined();
    expect(screen.getByText("Go to Billing")).toBeDefined();
  });

  it("calls onSelect with item id when item is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <CommandPalette open={true} onOpenChange={() => {}} items={items} onSelect={onSelect} />,
    );
    await userEvent.click(screen.getByText("Go to Claims"));
    expect(onSelect).toHaveBeenCalledWith("claims");
  });
});
