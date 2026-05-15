import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FactoryBindings } from "../factory-bindings.js";

const bindings = [
  { kind: "tenant+prescribers+claims", label: "Seed: 1 tenant + 10 prescribers + 5 claims" },
  { kind: "fwa-sample", label: "Seed: FWA sample data" },
];

describe("FactoryBindings", () => {
  it("renders a button per binding", () => {
    render(<FactoryBindings bindings={bindings} seed={() => Promise.resolve()} />);
    expect(screen.getByRole("button", { name: /tenant.*prescribers/i })).toBeDefined();
    expect(screen.getByRole("button", { name: /fwa/i })).toBeDefined();
  });

  it("calls seed with the binding kind when clicked", async () => {
    const seed = vi.fn().mockResolvedValue(undefined);
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(seed).toHaveBeenCalledWith("fwa-sample");
  });

  it("shows loading state while seed is in progress", async () => {
    let resolve!: () => void;
    const seed = vi.fn().mockReturnValue(new Promise<void>((r) => { resolve = r; }));
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(screen.getByText(/seeding/i)).toBeDefined();
    resolve();
  });

  it("shows success message after seed resolves", async () => {
    const seed = vi.fn().mockResolvedValue(undefined);
    render(<FactoryBindings bindings={bindings} seed={seed} />);
    await userEvent.click(screen.getByRole("button", { name: /fwa/i }));
    expect(await screen.findByText(/seeded/i)).toBeDefined();
  });
});
