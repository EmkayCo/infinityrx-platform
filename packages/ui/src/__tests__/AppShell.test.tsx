import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { AppShell } from "../shells/AppShell.js";

describe("AppShell", () => {
  it("renders header content", () => {
    render(
      <AppShell header={<div>My Header</div>}>
        <p>Main</p>
      </AppShell>,
    );
    expect(screen.getByText("My Header")).toBeDefined();
  });

  it("renders children as the main content", () => {
    render(
      <AppShell>
        <p>Page content</p>
      </AppShell>,
    );
    expect(screen.getByText("Page content")).toBeDefined();
  });

  it("renders nav slot when provided", () => {
    render(
      <AppShell nav={<nav>Nav</nav>}>
        <p>M</p>
      </AppShell>,
    );
    expect(screen.getByText("Nav")).toBeDefined();
  });

  it("omits nav region when nav prop is not provided", () => {
    const { container } = render(
      <AppShell>
        <p>M</p>
      </AppShell>,
    );
    expect(container.querySelector(".irx-app-shell__nav")).toBeNull();
  });
});
