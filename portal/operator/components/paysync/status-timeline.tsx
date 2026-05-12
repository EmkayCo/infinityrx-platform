"use client";

import { Check, Clock, X } from "lucide-react";
import { cn } from "@shared/lib/format";

export interface TimelineStep {
  id: string;
  label: string;
  description?: string;
  state: "completed" | "current" | "pending" | "failed" | "skipped";
  occurredAt?: string | null;
}

export function StatusTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol role="list" className="flex flex-col">
      {steps.map((step, idx) => {
        const isLast = idx === steps.length - 1;
        return (
          <li key={step.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <StepDot state={step.state} />
              {!isLast && (
                <span
                  aria-hidden="true"
                  className={cn(
                    "w-0.5 flex-1",
                    step.state === "completed" ? "bg-emerald-500/40" :
                    step.state === "current" ? "bg-amber-500/40" :
                    "bg-border",
                  )}
                />
              )}
            </div>
            <div className={cn("pb-4", isLast && "pb-0")}>
              <p className={cn(
                "text-sm font-medium",
                step.state === "current" && "text-amber-600",
                step.state === "failed" && "text-rose-500",
                step.state === "skipped" && "text-muted-foreground line-through",
              )}>
                {step.label}
              </p>
              {step.description && (
                <p className="text-xs text-muted-foreground">{step.description}</p>
              )}
              {step.occurredAt && (
                <p className="text-[11px] text-muted-foreground">
                  {new Date(step.occurredAt).toLocaleString()}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function StepDot({ state }: { state: TimelineStep["state"] }) {
  const cls =
    state === "completed" ? "bg-emerald-500 text-white" :
    state === "current" ? "bg-amber-500 text-white animate-pulse" :
    state === "failed" ? "bg-rose-500 text-white" :
    state === "skipped" ? "bg-muted text-muted-foreground line-through" :
    "border bg-background text-muted-foreground";
  return (
    <span
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px]",
        cls,
      )}
      aria-label={state}
    >
      {state === "completed" && <Check className="h-3 w-3" />}
      {state === "current" && <Clock className="h-3 w-3" />}
      {state === "failed" && <X className="h-3 w-3" />}
    </span>
  );
}
