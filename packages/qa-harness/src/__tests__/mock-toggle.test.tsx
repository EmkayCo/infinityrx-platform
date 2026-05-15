import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { BaseClient } from "@infinityrx/contract";
import { MockToggle } from "../mock-toggle.js";

function makeMockClient(name: string): BaseClient {
  return {
    name,
    cachePolicies: {},
    probeHealth: vi.fn().mockResolvedValue({ ok: true, latency_ms: 5 }),
  };
}

describe("MockToggle", () => {
  it("renders a toggle per client", () => {
    const clients = [makeMockClient("prescriber-directory"), makeMockClient("billing")];
    render(<MockToggle clients={clients} onToggle={() => {}} />);
    expect(screen.getByText("prescriber-directory")).toBeDefined();
    expect(screen.getByText("billing")).toBeDefined();
  });

  it("calls onToggle with (name, 'mock') when mock button clicked", async () => {
    const onToggle = vi.fn();
    const clients = [makeMockClient("prescriber-directory")];
    render(<MockToggle clients={clients} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole("button", { name: /mock/i }));
    expect(onToggle).toHaveBeenCalledWith("prescriber-directory", "mock");
  });

  it("calls onToggle with (name, 'real') when real button clicked", async () => {
    const onToggle = vi.fn();
    const clients = [makeMockClient("billing")];
    render(<MockToggle clients={clients} onToggle={onToggle} />);
    await userEvent.click(screen.getByRole("button", { name: /real/i }));
    expect(onToggle).toHaveBeenCalledWith("billing", "real");
  });

  it("shows current mode for each client when initialModes provided", () => {
    const clients = [makeMockClient("prescriber-directory")];
    const { container } = render(
      <MockToggle clients={clients} onToggle={() => {}} initialModes={{ "prescriber-directory": "mock" }} />,
    );
    // The current-mode span shows "mock" when initialModes seeds it
    expect(container.querySelector(".irx-qa-mock-toggle__current")?.textContent).toBe("mock");
  });
});
