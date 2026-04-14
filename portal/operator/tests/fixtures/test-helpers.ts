/**
 * Shared test helpers — assertions, render wrappers, matchers.
 */
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactElement } from "react";
import { expect } from "vitest";

/**
 * Assert that a value looks like a valid monetary amount — either a number
 * or a decimal string. Rejects NaN, null, undefined, and non-numeric strings.
 */
export function expectValidMoney(value: unknown, label = "amount"): void {
  if (typeof value === "number") {
    expect(Number.isFinite(value), `${label} is finite`).toBe(true);
    return;
  }
  if (typeof value === "string") {
    const n = parseFloat(value);
    expect(Number.isFinite(n), `${label} parses to finite number (got "${value}")`).toBe(true);
    return;
  }
  expect.fail(`${label} is ${value === undefined ? "undefined" : value === null ? "null" : typeof value}, expected number or decimal string`);
}

/**
 * Assert every field in `required` is present on `obj` and not null/undefined.
 */
export function expectShape<T extends object>(
  obj: unknown,
  required: readonly (keyof T)[],
  label = "object"
): asserts obj is T {
  expect(obj, `${label} exists`).toBeDefined();
  expect(obj, `${label} is not null`).not.toBeNull();
  expect(typeof obj, `${label} is object`).toBe("object");
  const o = obj as Record<string, unknown>;
  for (const key of required) {
    expect(o[key as string], `${label}.${String(key)} is present`).not.toBeUndefined();
  }
}

/**
 * Render helper — wraps with providers we'll need for component tests.
 * Currently pass-through; add QueryClientProvider etc. as needed.
 */
export function renderWithProviders(ui: ReactElement, opts?: RenderOptions) {
  return render(ui, opts);
}
