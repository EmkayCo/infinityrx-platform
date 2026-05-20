// packages/modules/paysync/__tests__/components/MoneyDisplay.test.tsx
// 100% branch coverage required (financial path per Auto-Gate).

import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MoneyDisplay } from "../../src/components/MoneyDisplay.js";

afterEach(() => cleanup());

describe("MoneyDisplay", () => {
  it("formats positive decimal string as USD", () => {
    render(<MoneyDisplay value="1234.56" />);
    expect(screen.getByTestId("money-display").textContent).toBe("$1,234.56");
  });

  it("formats negative decimal string as USD with sign", () => {
    render(<MoneyDisplay value="-89.10" />);
    // Intl.NumberFormat may render with parentheses or minus depending on locale variant; both contain "89.10".
    const text = screen.getByTestId("money-display").textContent ?? "";
    expect(text).toMatch(/89\.10/);
    expect(text).toMatch(/[-(]/);
  });

  it("formats zero", () => {
    render(<MoneyDisplay value="0.00" />);
    expect(screen.getByTestId("money-display").textContent).toBe("$0.00");
  });

  it("renders em-dash placeholder when value is not numeric", () => {
    render(<MoneyDisplay value="not-a-number" />);
    expect(screen.getByTestId("money-display-invalid").textContent).toBe("—");
  });

  it("renders em-dash when value is empty string", () => {
    // Empty string is NOT a valid Decimal serialization — must format as the
    // invalid-input placeholder. (Gate-close fix: previous code routed through
    // Number("") which coerced to 0; the regex-based validation rejects it.)
    render(<MoneyDisplay value="" />);
    expect(screen.getByTestId("money-display-invalid").textContent).toBe("—");
  });

  it("honors custom currency code", () => {
    render(<MoneyDisplay value="100" currency="EUR" locale="en-US" />);
    const text = screen.getByTestId("money-display").textContent ?? "";
    expect(text).toMatch(/€100\.00/);
  });

  it("honors custom locale", () => {
    render(<MoneyDisplay value="1234.56" locale="de-DE" currency="EUR" />);
    // de-DE uses "1.234,56 €" formatting
    const text = screen.getByTestId("money-display").textContent ?? "";
    expect(text).toMatch(/1\.234,56/);
  });

  it("applies optional className to root span", () => {
    render(<MoneyDisplay value="1.00" className="custom-cls" />);
    expect(screen.getByTestId("money-display").className).toBe("custom-cls");
  });

  it("applies optional className to invalid-value root span", () => {
    render(<MoneyDisplay value="bad" className="custom-cls" />);
    expect(screen.getByTestId("money-display-invalid").className).toBe("custom-cls");
  });
});
