import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import RoleSwitcherChip from "../../src/components/dev-only/RoleSwitcherChip.js";

afterEach(() => cleanup());

describe("RoleSwitcherChip (dev-only)", () => {
  it("renders the current role as the selected option", () => {
    render(<RoleSwitcherChip currentRole="approver" onRoleChange={() => {}} />);
    const select = screen.getByTestId<HTMLSelectElement>("role-switcher-select");
    expect(select.value).toBe("approver");
  });

  it("fires onRoleChange when user picks a new role", async () => {
    const onRoleChange = vi.fn();
    render(<RoleSwitcherChip currentRole="operator" onRoleChange={onRoleChange} />);
    const user = userEvent.setup();
    await user.selectOptions(screen.getByTestId("role-switcher-select"), "auditor");
    expect(onRoleChange).toHaveBeenCalledWith("auditor");
  });

  it("shows all 3 RBAC roles as options", () => {
    render(<RoleSwitcherChip currentRole="operator" onRoleChange={() => {}} />);
    const options = screen.getAllByRole("option") as HTMLOptionElement[];
    expect(options.map((o) => o.value)).toEqual(["operator", "approver", "auditor"]);
  });
});
