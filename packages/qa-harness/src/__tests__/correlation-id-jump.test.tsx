import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CorrelationIdJump } from "../correlation-id-jump.js";

describe("CorrelationIdJump", () => {
  beforeEach(() => {
    const mockClipboard = { writeText: vi.fn().mockResolvedValue(undefined) };
    Object.defineProperty(navigator, "clipboard", {
      value: mockClipboard,
      writable: true,
      configurable: true,
    });
  });

  it("renders an input field", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("renders a copy button", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.getByRole("button", { name: /copy/i })).toBeDefined();
  });

  it("calls navigator.clipboard.writeText with the correlation id when copy is clicked", async () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    await userEvent.type(screen.getByRole("textbox"), "550e8400-e29b-41d4-a716-446655440000");
    await userEvent.click(screen.getByRole("button", { name: /copy/i }));
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "550e8400-e29b-41d4-a716-446655440000",
    );
  });

  it("renders a log-search link when a correlation id is typed", async () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    await userEvent.type(screen.getByRole("textbox"), "abc-123");
    expect(screen.getByRole("link")).toBeDefined();
    expect((screen.getByRole("link") as HTMLAnchorElement).href).toContain("abc-123");
  });

  it("does not render a link when the input is empty", () => {
    render(<CorrelationIdJump logSearchBaseUrl="https://logs.example.com/search" />);
    expect(screen.queryByRole("link")).toBeNull();
  });
});
