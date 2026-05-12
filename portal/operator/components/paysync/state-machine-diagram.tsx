"use client";

// Visual state machine renderer with current state highlighted.
// Used for batch and invoice lifecycle displays.

import { ChevronRight } from "lucide-react";
import { cn } from "@shared/lib/format";

export interface StateMachineNode {
  id: string;
  label: string;
  terminal?: boolean;
}

export interface StateMachineDiagramProps {
  nodes: StateMachineNode[];
  current: string;
  branches?: Record<string, string[]>;
}

export function StateMachineDiagram({ nodes, current }: StateMachineDiagramProps) {
  const currentIdx = nodes.findIndex((n) => n.id === current);

  return (
    <div className="flex flex-wrap items-center gap-1">
      {nodes.map((node, idx) => {
        const isCurrent = node.id === current;
        const isPast = idx < currentIdx;
        const cls =
          isCurrent ? "border-amber-500 bg-amber-500/10 text-amber-700 dark:text-amber-300" :
          isPast ? "border-emerald-500/50 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300" :
          node.terminal ? "border-rose-500/50 bg-rose-500/5 text-rose-600 dark:text-rose-300" :
          "border-border bg-background text-muted-foreground";
        return (
          <div key={node.id} className="flex items-center gap-1">
            <span className={cn(
              "rounded-md border px-2 py-1 text-xs font-medium",
              cls,
              isCurrent && "shadow-sm",
            )}>
              {node.label}
            </span>
            {idx < nodes.length - 1 && (
              <ChevronRight className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
            )}
          </div>
        );
      })}
    </div>
  );
}
