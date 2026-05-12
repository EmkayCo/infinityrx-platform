"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { cn } from "@shared/lib/format";
import type { ReconciliationFinding } from "@shared/lib/paysync-api";

export function MismatchFindingCard({ finding }: { finding: ReconciliationFinding }) {
  const [open, setOpen] = useState(false);
  const Chevron = open ? ChevronUp : ChevronDown;

  return (
    <div className="rounded-md border bg-card p-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-start gap-3 text-left"
        aria-expanded={open}
      >
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
        <div className="flex-1">
          <p className="text-sm font-medium">
            <span className={cn(
              "mr-2 rounded bg-muted/50 px-1.5 py-0.5 text-[10px] font-mono",
            )}>
              Tie {finding.tie}
            </span>
            {finding.category}
          </p>
          <p className="text-xs text-muted-foreground">{finding.detail}</p>
        </div>
        <div className="flex items-center gap-2">
          {finding.amount && (
            <span className="font-mono text-xs tabular-nums">${finding.amount}</span>
          )}
          <Chevron className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </button>
      {open && finding.related_entity_id && (
        <div className="mt-3 border-t pt-2 text-xs text-muted-foreground">
          <p>Related entity:</p>
          <p className="font-mono">{finding.related_entity_id}</p>
        </div>
      )}
    </div>
  );
}
