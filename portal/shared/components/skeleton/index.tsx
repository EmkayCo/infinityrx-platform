import { cn } from "@shared/lib/format";

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className, style }: SkeletonProps) {
  return (
    <div
      className={cn("shimmer animate-pulse rounded-md bg-slate-200 dark:bg-slate-700/50", className)}
      aria-hidden="true"
      style={style}
    />
  );
}

export function ContentSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading content">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn("h-4", i === lines - 1 ? "w-3/4" : "w-full")}
        />
      ))}
    </div>
  );
}

export function CardSkeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("space-y-3 p-4 rounded-lg border bg-card", className)} role="status" aria-label="Loading card">
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-2/5" />
        <Skeleton className="h-8 w-8 rounded-full" />
      </div>
      <Skeleton className="h-8 w-3/5" />
      <div className="space-y-1.5">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-4/5" />
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="w-full space-y-2" role="status" aria-label="Loading table">
      <div className="flex gap-3 pb-2 border-b">
        {Array.from({ length: cols }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3 py-2">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function DashboardWidgetSkeleton() {
  return (
    <div
      className="rounded-lg border bg-card p-4 space-y-4 h-full min-h-[180px]"
      role="status"
      aria-label="Loading widget"
    >
      <div className="flex items-center justify-between">
        <Skeleton className="h-5 w-2/5" />
        <div className="flex gap-1">
          <Skeleton className="h-7 w-7 rounded-md" />
          <Skeleton className="h-7 w-7 rounded-md" />
        </div>
      </div>
      <Skeleton className="h-10 w-3/5" />
      <div className="grid grid-cols-2 gap-2">
        <Skeleton className="h-16 rounded-md" />
        <Skeleton className="h-16 rounded-md" />
      </div>
      <Skeleton className="h-3 w-2/5" />
    </div>
  );
}

export function SkeletonChart({ className }: SkeletonProps) {
  return (
    <div className={cn("flex items-end gap-2 h-32", className)} role="status" aria-label="Loading chart">
      {[60, 80, 45, 90, 70, 55, 85, 65, 75, 50, 95, 40].map((h, i) => (
        <Skeleton key={i} className="flex-1" style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

// Backwards-compatibility aliases for T2/T3 teammate code
export { TableSkeleton as SkeletonTable };
export { CardSkeleton as SkeletonCard };
