"use client";

// Reconciliation tie expected/actual/delta display with color-blind
// safe iconography (icon + label, not color-only).

import Decimal from "decimal.js";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { cn } from "@shared/lib/format";
import type { TieResult } from "@shared/lib/paysync-api";

export interface DeltaDisplayProps {
  label: string;
  description?: string;
  tie: TieResult;
  toleranceCents?: number;
}

export function DeltaDisplay({
  label, description, tie, toleranceCents = 1,
}: DeltaDisplayProps) {
  const matched = tie.status === "match";
  const toneCls = matched
    ? "border-emerald-500/30 bg-emerald-500/5"
    : "border-rose-500/40 bg-rose-500/5";
  const Icon = matched ? CheckCircle2 : AlertTriangle;
  const iconCls = matched ? "text-emerald-500" : "text-rose-500";

  const delta = new Decimal(tie.delta);
  const deltaAbs = delta.abs();
  const tolerance = new Decimal(toleranceCents).div(100);
  const withinTolerance = deltaAbs.lte(tolerance);

  return (
    <div className={cn("rounded-lg border p-4", toneCls)}>
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold">{label}</p>
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          <Icon className={cn("h-4 w-4", iconCls)} aria-hidden="true" />
          <span className={cn(
            "rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase",
            matched
              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
              : "bg-rose-500/10 text-rose-700 dark:text-rose-300",
          )}>
            {tie.status}
          </span>
        </div>
      </div>

      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-[11px] uppercase text-muted-foreground">Expected</dt>
          <dd className="font-mono tabular-nums">{formatMoney(tie.expected)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase text-muted-foreground">Actual</dt>
          <dd className="font-mono tabular-nums">{formatMoney(tie.actual)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase text-muted-foreground">Delta</dt>
          <dd className={cn(
            "font-mono tabular-nums",
            !matched && !withinTolerance && "font-semibold text-rose-600",
          )}>
            {delta.gte(0) ? "+" : ""}{formatMoney(tie.delta)}
          </dd>
        </div>
      </dl>

      {tie.reasons.length > 0 && (
        <div className="mt-3 border-t pt-3">
          <p className="mb-1 text-[11px] uppercase text-muted-foreground">
            Mismatch reasons
          </p>
          <ul className="list-disc space-y-1 pl-4 text-xs">
            {tie.reasons.map((r, i) => (<li key={i}>{r}</li>))}
          </ul>
        </div>
      )}
    </div>
  );
}

function formatMoney(value: string): string {
  try {
    const d = new Decimal(value);
    return `$${d.toFixed(2)}`;
  } catch {
    return value;
  }
}
