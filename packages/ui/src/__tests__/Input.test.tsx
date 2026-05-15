import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { Input } from "../primitives/Input.js";

describe("Input", () => {
  it("renders an input element", () => {
    render(<Input placeholder="Search" />);
    expect(screen.getByPlaceholderText("Search")).toBeDefined();
  });

  it("forwards ref to the underlying input", () => {
    const ref = React.createRef<HTMLInputElement>();
    render(<Input ref={ref} />);
    expect(ref.current?.tagName).toBe("INPUT");
  });

  it("passes through type and value props", () => {
    render(<Input type="email" defaultValue="test@example.com" />);
    const input = screen.getByDisplayValue("test@example.com") as HTMLInputElement;
    expect(input.type).toBe("email");
  });

  it("is disabled when disabled prop is set", () => {
    render(<Input disabled />);
    expect((screen.getByRole("textbox") as HTMLInputElement).disabled).toBe(true);
  });
});
