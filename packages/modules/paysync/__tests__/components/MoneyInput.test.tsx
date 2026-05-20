// packages/modules/paysync/__tests__/components/MoneyInput.test.tsx
// 100% branch coverage required (financial path per Auto-Gate).

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { MoneyInput } from "../../src/components/MoneyInput.js";

afterEach(() => cleanup());

describe("MoneyInput", () => {
  it("renders with empty initial value by default", () => {
    render(<MoneyInput />);
    expect(screen.getByTestId<HTMLInputElement>("money-input").value).toBe("");
  });

  it("renders with provided initial value", () => {
    render(<MoneyInput initialValue="42.50" />);
    expect(screen.getByTestId<HTMLInputElement>("money-input").value).toBe("42.50");
  });

  it("fires onChange with valid decimal string on blur", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "1234.56");
    await user.tab();
    expect(onChange).toHaveBeenCalledWith("1234.56");
  });

  it("does NOT fire onChange when value has >4 decimal places", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "1.23456");
    await user.tab();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId("money-input-error").textContent).toBe("Max 4 decimal places");
  });

  it("does NOT fire onChange when value is not a number", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "abc");
    await user.tab();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId("money-input-error").textContent).toBe("Not a valid number");
  });

  it("fires onChange with empty string when blurred empty", async () => {
    const onChange = vi.fn();
    render(<MoneyInput initialValue="100" onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.clear(input);
    await user.tab();
    expect(onChange).toHaveBeenCalledWith("");
  });

  it("accepts negative decimal values", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "-50.25");
    await user.tab();
    expect(onChange).toHaveBeenCalledWith("-50.25");
  });

  it("accepts integer values (no decimal)", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "100");
    await user.tab();
    expect(onChange).toHaveBeenCalledWith("100");
  });

  it("clears error on subsequent change after invalid blur", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "abc");
    await user.tab();
    expect(screen.getByTestId("money-input-error")).toBeTruthy();
    await user.click(input);
    await user.type(input, "1");
    expect(screen.queryByTestId("money-input-error")).toBeNull();
  });

  it("honors maxDecimalPlaces override", async () => {
    const onChange = vi.fn();
    render(<MoneyInput maxDecimalPlaces={2} onChange={onChange} />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "1.234");
    await user.tab();
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByTestId("money-input-error").textContent).toBe("Max 4 decimal places");
  });

  it("works without an onChange handler (no crash)", async () => {
    render(<MoneyInput />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.type(input, "5.00");
    await expect(user.tab()).resolves.not.toThrow();
  });

  it("trims whitespace before validation", async () => {
    const onChange = vi.fn();
    render(<MoneyInput onChange={onChange} initialValue="  100.50  " />);
    const input = screen.getByTestId<HTMLInputElement>("money-input");
    const user = userEvent.setup();
    await user.tab();  // blur the field; trim happens inside handler
    // Move focus back, do nothing, then blur to trigger handler.
    await user.click(input);
    await user.tab();
    expect(onChange).toHaveBeenCalledWith("100.50");
  });
});
