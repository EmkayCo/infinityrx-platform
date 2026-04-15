"use client";

import { AlertTriangle } from "lucide-react";
import { cn } from "@shared/lib/format";

interface DemoBannerProps {
  tenantSlug?: string | null;
  className?: string;
}

const DEMO_TENANT_SLUG = "infinityrx-demo";

/**
 * Visual marker shown across every page when the active tenant is the
 * sales-demo tenant. Prevents anyone from confusing fictional demo data
 * with production data.
 *
 * The check is tenant-slug based — any tenant whose slug equals
 * `infinityrx-demo` triggers the banner.
 */
export function DemoBanner({ tenantSlug, className }: DemoBannerProps) {
  if (!tenantSlug || tenantSlug !== DEMO_TENANT_SLUG) {
    return null;
  }

  return (
    <div
      role="alert"
      aria-live="polite"
      className={cn(
        "flex h-8 items-center justify-center gap-2 bg-amber-400 text-amber-950",
        "border-b border-amber-500 text-xs font-semibold uppercase tracking-wide",
        className,
      )}
    >
      <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
      <span>Demo Environment — Fictional Data</span>
    </div>
  );
}
