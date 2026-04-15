"use client";

import React from "react";
import { cn, formatDollars, formatDollarsVerbal, getDollarScale } from "@shared/lib/format";
import type { Money } from "@shared/types/common";

interface DollarDisplayProps {
  amount: Money | number | null | undefined;
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  showScale?: boolean;
  /** Show verbal description, e.g. "thirteen million two hundred forty-seven thousand..." */
  showVerbal?: boolean;
  /** Show +/- sign prefix */
  showSign?: boolean;
}

const sizeClasses = {
  sm: "text-sm",
  md: "text-base",
  lg: "text-lg font-semibold",
  xl: "text-2xl font-bold",
};

export function DollarDisplay({
  amount,
  className,
  size = "md",
  showScale = true,
  showVerbal = false,
  showSign = false,
}: DollarDisplayProps) {
  const formatted = formatDollars(amount);
  const scale = getDollarScale(amount);
  const verbal = showVerbal ? formatDollarsVerbal(amount) : null;
  const numeric = amount != null ? parseFloat(String(amount)) : 0;
  const prefix = showSign && numeric > 0 ? "+" : "";

  return (
    <span className={cn("inline-flex flex-col gap-0.5", className)}>
      <span
        className={cn(
          "font-mono tabular-nums text-fg",
          sizeClasses[size],
          showScale && scale === "bold" && "font-bold",
          showScale && scale === "highlight" && "font-bold text-interactive bg-interactive-bg px-1 rounded"
        )}
        aria-label={verbal ?? formatted}
      >
        {prefix}{formatted}
      </span>
      {showVerbal && verbal && (
        <span className="text-xs text-fg-muted italic leading-tight">
          {verbal}
        </span>
      )}
    </span>
  );
}

/** Inline cell variant for table rows */
export function DollarCell({
  amount,
  className,
}: {
  amount: Money | number | null | undefined;
  className?: string;
}) {
  return <DollarDisplay amount={amount} size="sm" showScale={false} className={className} />;
}

/** Delta variant shows +/- with color coding */
export function DollarDelta({
  amount,
  className,
}: {
  amount: Money | number | null | undefined;
  className?: string;
}) {
  const numeric = amount != null ? parseFloat(String(amount)) : 0;
  return (
    <span
      className={cn(
        "inline-flex items-center text-sm font-medium tabular-nums font-mono",
        numeric > 0 && "text-success",
        numeric < 0 && "text-error",
        numeric === 0 && "text-fg-muted",
        className
      )}
    >
      {numeric > 0 ? "+" : ""}{formatDollars(amount)}
    </span>
  );
}

interface DollarInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  id?: string;
}

export function DollarInput({
  value,
  onChange,
  placeholder = "0.00",
  className,
  disabled,
  id,
}: DollarInputProps) {
  return (
    <div className={cn("relative", className)}>
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-fg-muted pointer-events-none">
        $
      </span>
      <input
        id={id}
        type="text"
        inputMode="decimal"
        value={value}
        onChange={(e) => {
          const raw = e.target.value.replace(/[^0-9.]/g, "");
          onChange(raw);
        }}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          "w-full pl-7 pr-3 py-2 rounded-md border border-border-default bg-card text-fg",
          "font-mono text-sm placeholder:text-fg-placeholder",
          "focus:outline-none focus:ring-2 focus:ring-interactive/40 focus:border-interactive",
          disabled && "opacity-50 cursor-not-allowed"
        )}
      />
    </div>
  );
}
