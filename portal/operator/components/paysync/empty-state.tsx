"use client";

// Empty-state components — helpful "Get started" rather than "No data".

import type { ReactNode } from "react";
import { cn } from "@shared/lib/format";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
  className?: string;
}

export function EmptyState({
  icon, title, description, primaryAction, secondaryAction, className,
}: EmptyStateProps) {
  return (
    <div className={cn(
      "rounded-lg border border-dashed bg-card/40 p-8 text-center",
      className,
    )}>
      {icon && (
        <div className="mb-3 flex justify-center">
          <div className="rounded-full bg-muted/50 p-3 text-muted-foreground">
            {icon}
          </div>
        </div>
      )}
      <p className="text-sm font-medium">{title}</p>
      {description && (
        <div className="mt-1 mx-auto max-w-md text-xs text-muted-foreground">
          {description}
        </div>
      )}
      {(primaryAction || secondaryAction) && (
        <div className="mt-4 flex justify-center gap-2">
          {primaryAction}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
