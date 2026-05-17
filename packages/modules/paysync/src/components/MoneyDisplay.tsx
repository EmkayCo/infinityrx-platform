// packages/modules/paysync/src/components/MoneyDisplay.tsx
// Formats a Decimal-string money amount as USD.
// Receives `value: string` per .claude/rules/financial-precision.md —
// never `number` or `float`. Backend serializes Decimal to string; this
// component is the display half of that contract.
//
// Gate-close fix (Codex): Intl.NumberFormat.format() accepts a Decimal
// STRING directly (ES2024+ behavior; supported in Node 20+ and modern
// browsers). We no longer convert to Number(value), so high-precision
// or large-magnitude Decimal strings format without going through
// float64 rounding. Validity is checked via regex, not Number(NaN).

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
// Decimal literal: optional sign, integer part, optional fractional part.
// Matches anything that round-trips through a strict Decimal serializer.
const DECIMAL_PATTERN = /^-?\d+(?:\.\d+)?$/;

export function MoneyDisplay({
  value,
  currency = USD,
  locale = EN_US,
  className,
}: MoneyDisplayProps): ReactElement {
  // Defensive: reject anything that isn't a valid Decimal string. We
  // intentionally do NOT use Number(value) here — that would coerce
  // strings like "1.0000000000000001" to 1 silently (float64 precision
  // loss). The regex test admits exactly the shapes a Decimal serializer
  // would emit, and rejects everything else without touching the value
  // as a float.
  if (!DECIMAL_PATTERN.test(value)) {
    return (
      <span data-testid="money-display-invalid" className={className}>
        —
      </span>
    );
  }

  // Intl.NumberFormat.format accepts a Decimal string directly per the
  // updated ECMA-402 spec. The formatter rounds to the currency's display
  // precision (2 fractional digits for USD) but the FULL precision is
  // preserved on the way in — no float64 round-trip.
  const formatted = new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
  }).format(value as unknown as number); // runtime accepts string; types lag.

  return (
    <span data-testid="money-display" className={className}>
      {formatted}
    </span>
  );
}
