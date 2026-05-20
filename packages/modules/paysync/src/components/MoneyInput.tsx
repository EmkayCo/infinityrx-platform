// packages/modules/paysync/src/components/MoneyInput.tsx
// Decimal-only money input. Validates on blur: rejects >4 decimal places,
// rejects NaN. Only fires onChange with the validated decimal string.
// Per .claude/rules/financial-precision.md — never accepts float/number.

import { useCallback, useState, type ChangeEvent, type FocusEvent, type ReactElement } from "react";

export interface MoneyInputProps {
  /** Initial decimal string value. */
  readonly initialValue?: string;
  /** Called with validated decimal string only. Never called with invalid value. */
  readonly onChange?: (decimalString: string) => void;
  /** HTML name attribute for form submission. */
  readonly name?: string;
  /** Max decimal places allowed. Default 4 (matches NUMERIC(x,4) money columns). */
  readonly maxDecimalPlaces?: number;
}

const DECIMAL_PATTERN = /^-?\d+(\.\d+)?$/;
const ERROR_TOO_MANY_DECIMALS = "Max 4 decimal places";
const ERROR_NOT_A_NUMBER = "Not a valid number";

export function MoneyInput({
  initialValue = "",
  onChange,
  name,
  maxDecimalPlaces = 4,
}: MoneyInputProps): ReactElement {
  const [draft, setDraft] = useState<string>(initialValue);
  const [error, setError] = useState<string | null>(null);

  const handleChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    setDraft(e.target.value);
    if (error !== null) setError(null);
  }, [error]);

  const handleBlur = useCallback((e: FocusEvent<HTMLInputElement>) => {
    const raw = e.target.value.trim();
    if (raw === "") {
      setError(null);
      onChange?.("");
      return;
    }
    if (!DECIMAL_PATTERN.test(raw)) {
      setError(ERROR_NOT_A_NUMBER);
      return;
    }
    const decimalIndex = raw.indexOf(".");
    const decimalPlaces = decimalIndex === -1 ? 0 : raw.length - decimalIndex - 1;
    if (decimalPlaces > maxDecimalPlaces) {
      setError(ERROR_TOO_MANY_DECIMALS);
      return;
    }
    setError(null);
    onChange?.(raw);
  }, [maxDecimalPlaces, onChange]);

  return (
    <span>
      <input
        type="text"
        inputMode="decimal"
        name={name}
        value={draft}
        onChange={handleChange}
        onBlur={handleBlur}
        data-testid="money-input"
        aria-invalid={error !== null}
        aria-errormessage={error !== null ? "money-input-error" : undefined}
      />
      {error !== null && (
        <span id="money-input-error" data-testid="money-input-error" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
