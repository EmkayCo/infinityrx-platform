import { cn } from "@shared/lib/format";

export type StatusVariant =
  | "success"
  | "warning"
  | "error"
  | "info"
  | "neutral"
  | "investigation"
  | "navy";

interface StatusBadgeProps {
  status: string;
  variant?: StatusVariant;
  className?: string;
}

const VARIANT_CLASSES: Record<StatusVariant, string> = {
  success: "bg-ifx-success-light text-ifx-success-text",
  warning: "bg-ifx-warning-light text-ifx-warning-text",
  error: "bg-ifx-error-light text-ifx-error-text",
  info: "bg-ifx-info-light text-ifx-info-text",
  neutral: "bg-ifx-gray-100 text-ifx-gray-700",
  investigation: "bg-ifx-investigation-light text-ifx-investigation-text",
  navy: "bg-ifx-primary-bg text-ifx-navy dark:text-ifx-primary-light",
};

const DEFAULT_STATUS_VARIANTS: Record<string, StatusVariant> = {
  active: "success",
  enabled: "success",
  paid: "success",
  healthy: "success",
  settled: "success",
  approved: "success",
  confirmed: "success",
  completed: "success",
  recovered: "success",

  pending: "warning",
  degraded: "warning",
  processing: "warning",
  draft: "warning",
  in_progress: "warning",
  "in progress": "warning",
  awaiting: "warning",

  disabled: "error",
  reversed: "error",
  critical: "error",
  failed: "error",
  rejected: "error",
  denied: "error",
  unhealthy: "error",
  escalated: "error",

  new: "info",
  open: "info",
  submitted: "info",

  closed: "neutral",
  dismissed: "neutral",
  inactive: "neutral",
  ended: "neutral",
};

export function inferStatusVariant(status: string): StatusVariant {
  return DEFAULT_STATUS_VARIANTS[status.toLowerCase()] ?? "neutral";
}

export function StatusBadge({ status, variant, className }: StatusBadgeProps) {
  const resolvedVariant = variant ?? inferStatusVariant(status);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        VARIANT_CLASSES[resolvedVariant],
        className,
      )}
    >
      {status}
    </span>
  );
}
