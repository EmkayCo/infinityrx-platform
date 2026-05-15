import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Button } from "../primitives/Button.js";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeDefined();
  });

  it("applies destructive variant class", () => {
    const { container } = render(<Button variant="destructive">Del</Button>);
    expect(container.firstChild?.toString()).toContain("destructive");
    // cva emits the variant name as part of the className
    expect((container.firstChild as HTMLElement).className).toMatch(/destructive/);
  });

  it("applies size class for lg", () => {
    const { container } = render(<Button size="lg">Big</Button>);
    expect((container.firstChild as HTMLElement).className).toMatch(/lg/);
  });

  it("is disabled when disabled prop is set", () => {
    render(<Button disabled>No</Button>);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
  });
});
