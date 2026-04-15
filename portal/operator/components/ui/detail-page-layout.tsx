import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { cn } from "@shared/lib/format";
import { KpiCardRow } from "./kpi-card-row";
import type { KpiCardProps } from "./kpi-card";

interface BackLink {
  href: string;
  label: string;
}

interface DetailPageLayoutProps {
  backLink?: BackLink;
  title: string;
  subtitle?: string | React.ReactNode;
  eyebrow?: string;
  actions?: React.ReactNode;
  summaryCards?: KpiCardProps[];
  summaryColumns?: 2 | 3 | 4 | 5 | 6;
  children: React.ReactNode;
  className?: string;
}

export function DetailPageLayout({
  backLink,
  title,
  subtitle,
  eyebrow,
  actions,
  summaryCards,
  summaryColumns,
  children,
  className,
}: DetailPageLayoutProps) {
  return (
    <div className={cn("flex flex-col gap-6", className)}>
      {/* Back link */}
      {backLink && (
        <Link
          href={backLink.href}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-ifx-gray-400 hover:text-ifx-blue transition-colors w-fit"
        >
          <ArrowLeft className="h-4 w-4" />
          {backLink.label}
        </Link>
      )}

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1 min-w-0">
          {eyebrow && (
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
              {eyebrow}
            </span>
          )}
          <h1 className="text-2xl font-bold text-ifx-gray-900 leading-tight">{title}</h1>
          {subtitle && (
            <div className="text-sm text-ifx-gray-400">{subtitle}</div>
          )}
        </div>
        {actions && (
          <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
        )}
      </div>

      {/* Summary cards */}
      {summaryCards && summaryCards.length > 0 && (
        <KpiCardRow cards={summaryCards} columns={summaryColumns} />
      )}

      {/* Content */}
      <div className="flex flex-col gap-6">{children}</div>
    </div>
  );
}
