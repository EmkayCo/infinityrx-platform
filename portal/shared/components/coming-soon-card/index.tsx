"use client";

import { Clock } from "lucide-react";
import { cn } from "@shared/lib/format";

interface ComingSoonCardProps {
  moduleName: string;
  description: string;
  expectedAvailability?: string;
  className?: string;
}

export function ComingSoonCard({
  moduleName,
  description,
  expectedAvailability,
  className,
}: ComingSoonCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 rounded-lg border border-dashed bg-muted/30 p-8 text-center",
        className
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <Clock className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
      </div>
      <div>
        <h3 className="font-semibold text-base">{moduleName}</h3>
        <p className="mt-1 text-sm text-muted-foreground max-w-sm">{description}</p>
        {expectedAvailability && (
          <p className="mt-2 text-xs text-teal-600 dark:text-teal-400 font-medium">
            Expected: {expectedAvailability}
          </p>
        )}
      </div>
      <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
        <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden="true" />
        Coming Soon
      </span>
    </div>
  );
}
