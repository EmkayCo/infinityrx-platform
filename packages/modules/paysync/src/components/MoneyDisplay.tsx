// packages/modules/paysync/src/components/MoneyDisplay.tsx
// Formats a Decimal-string money amount as USD.
// Receives `value: string` per .claude/rules/financial-precision.md —
// never `number` or `float`. Backend serializes Decimal to string; this
// component is the display half of that contract.

import type { ReactElement } from "react";

export interface MoneyDisplayProps {
  /** Decimal-encoded amount as a string. Examples: "1234.56", "-89.10", "0.00". */
  readonly value: string;
  /** Currency code; defaults to USD. */
  readonly currency?: string;
  /** Locale for formatting; defaults to en-US. */
  readonly locale?: string;
  /** Optional className for the root span. */
  readonly className?: string;
}

const USD = "USD";
const EN_US = "en-US";

export function MoneyDisplay({
  value,
  currency = USD,
  locale = EN_US,
  className,
}: MoneyDisplayProps): ReactElement {
  // Reject obviously invalid input deterministically. Production data is
  // controlled (Decimal string from backend), but defensive rendering avoids
  // NaN currency strings if a stub returns garbage.
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return (
      <span data-testid="money-display-invalid" className={className}>
        —
      </span>
    );
  }

  const formatted = new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(numeric);

  return (
    <span data-testid="money-display" className={className}>
      {formatted}
    </span>
  );
}
