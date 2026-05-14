"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  FileText,
  Info,
  Layers,
  LayoutDashboard,
  Plus,
  RefreshCw,
  Search,
  TrendingUp,
  X,
  XCircle,
} from "lucide-react";

import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { cn, formatRelative } from "@shared/lib/format";
import { apiGet } from "@shared/lib/api-client";
import { useAuth } from "@shared/hooks/use-auth";
import type {
  DashboardAlert,
  DashboardActivityEvent,
} from "@shared/lib/mock-data/seed/programs";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DashboardKpi {
  active_programs: number;
  total_claims_ytd: number;
  total_copay_spend_ytd: string;
  gtn_ratio: string;
  active_investigations: number;
  pending_payments: number;
  // B11 w2 — BFF flags fields whose backend source is unreachable or
  // not yet wired. UI renders "Unavailable" instead of zero when a
  // field is listed here. Without this, zero is indistinguishable
  // from "real value is zero" and the dashboard lies.
  unavailable_fields?: string[];
}

interface ProgramHealthCard {
  program_id: string;
  program_name: string;
  manufacturer: string;
  claims_period: number;
  spend_period: string;
  gtn_percent: string;
  active_alerts: number;
  href: string;
}

// ─── Dashboard Preset tabs ─────────────────────────────────────────────────────

const PRESETS = [
  { id: "overview", label: "Overview" },
  { id: "billing_ops", label: "Billing Operations" },
  { id: "fwa_investigation", label: "FWA Investigation" },
  { id: "executive", label: "Executive" },
] as const;
type PresetId = (typeof PRESETS)[number]["id"];

const PRESET_STORAGE_KEY = "ifx-dashboard-preset-v2";
const ONBOARDING_FLAG = "ifx-onboarding-completed";

// ─── Severity badge ───────────────────────────────────────────────────────────

function SeverityIcon({
  severity,
}: {
  severity: "info" | "warning" | "error";
}) {
  if (severity === "error")
    return <XCircle className="h-4 w-4 shrink-0 text-red-500" />;
  if (severity === "warning")
    return <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500" />;
  return <Info className="h-4 w-4 shrink-0 text-blue-500" />;
}

// ─── Alerts & Actions section ─────────────────────────────────────────────────

function AlertsSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-alerts"],
    queryFn: () =>
      apiGet<{ alerts: DashboardAlert[] }>("/api/v1/dashboard/alerts"),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <div className="h-5 w-40 shimmer rounded mb-3" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-12 shimmer rounded mb-2" />
        ))}
      </div>
    );
  }

  const alerts = data?.alerts ?? [];

  return (
    <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
      <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
        <h3 className="text-sm font-bold text-ifx-gray-900">
          Alerts &amp; Actions
        </h3>
        <span className="text-xs text-ifx-gray-400">
          {alerts.length} item{alerts.length !== 1 ? "s" : ""} need attention
        </span>
      </header>
      <ul className="divide-y divide-ifx-gray-100">
        {alerts.length === 0 && (
          <li className="px-4 py-8 text-center text-sm text-ifx-gray-400">
            No items require attention.
          </li>
        )}
        {alerts.map((alert) => (
          <li key={alert.id}>
            <Link
              href={alert.href}
              className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--ifx-lavender)] transition-colors"
              aria-label={alert.title}
            >
              <SeverityIcon severity={alert.severity} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-ifx-gray-900 leading-tight">
                  {alert.title}
                </p>
                <p className="text-xs text-ifx-gray-400 mt-0.5 truncate">
                  {alert.description}
                </p>
              </div>
              <ArrowRight className="h-4 w-4 shrink-0 text-ifx-gray-400 mt-0.5" />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Activity Feed section ─────────────────────────────────────────────────────

function ActivityFeedSection({
  onEventClick,
}: {
  onEventClick?: (event: DashboardActivityEvent) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-activity"],
    queryFn: () =>
      apiGet<{ events: DashboardActivityEvent[] }>(
        "/api/v1/dashboard/activity"
      ),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <div className="h-5 w-32 shimmer rounded mb-3" />
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-14 shimmer rounded mb-2" />
        ))}
      </div>
    );
  }

  const events = data?.events ?? [];

  return (
    <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
      <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
        <h3 className="text-sm font-bold text-ifx-gray-900">Recent Activity</h3>
        <Link
          href="/reclaimrx"
          className="text-xs text-ifx-blue hover:underline"
        >
          View all
        </Link>
      </header>
      <ul className="divide-y divide-ifx-gray-100">
        {events.length === 0 && (
          <li className="px-4 py-8 text-center text-sm text-ifx-gray-400">
            No recent activity.
          </li>
        )}
        {events.map((event) => (
          <li key={event.id}>
            <Link
              href={event.entity_href}
              onClick={() => onEventClick?.(event)}
              className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--ifx-lavender)] transition-colors"
              aria-label={event.title}
              data-entity-type={event.entity_type}
              data-entity-id={event.entity_id}
            >
              <SeverityIcon severity={event.severity ?? "info"} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-ifx-gray-900 leading-tight">
                  {event.title}
                </p>
                <p className="text-xs text-ifx-gray-400 mt-0.5 line-clamp-2">
                  {event.description}
                </p>
              </div>
              <span className="text-[10px] text-ifx-gray-400 shrink-0 mt-0.5 whitespace-nowrap">
                {formatRelative(event.timestamp)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ─── Program Health Cards ─────────────────────────────────────────────────────

function ProgramHealthSection() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-program-health"],
    queryFn: () =>
      apiGet<{ programs: ProgramHealthCard[] }>(
        "/api/v1/dashboard/program-health"
      ),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-32 shimmer rounded-lg" />
        ))}
      </div>
    );
  }

  const programs = data?.programs ?? [];

  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-base font-bold text-ifx-gray-900">
          Program Health
        </h2>
        <Link
          href="/programs"
          className="text-xs text-ifx-blue hover:underline inline-flex items-center gap-1"
        >
          All programs <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {programs.map((prog) => (
          <Link
            key={prog.program_id}
            href={prog.href}
            className="rounded-lg bg-white ifx-card-shadow p-4 hover:-translate-y-0.5 transition-all ifx-card-shadow-lift block"
            aria-label={`${prog.program_name} — program health`}
          >
            <p className="text-[10px] font-semibold uppercase tracking-wider text-ifx-navy mb-1">
              {prog.manufacturer}
            </p>
            <p className="text-sm font-bold text-ifx-gray-900 leading-snug mb-3">
              {prog.program_name}
            </p>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <p className="text-base font-bold tabular-nums text-ifx-gray-900">
                  {prog.claims_period.toLocaleString()}
                </p>
                <p className="text-[10px] text-ifx-gray-400">Claims YTD</p>
              </div>
              <div>
                <p className="text-base font-bold tabular-nums text-ifx-gray-900">
                  {prog.gtn_percent}%
                </p>
                <p className="text-[10px] text-ifx-gray-400">GTN</p>
              </div>
              <div>
                {prog.active_alerts > 0 ? (
                  <>
                    <p className="text-base font-bold tabular-nums text-red-500">
                      {prog.active_alerts}
                    </p>
                    <p className="text-[10px] text-ifx-gray-400">Alerts</p>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="h-5 w-5 text-green-500 mx-auto" />
                    <p className="text-[10px] text-ifx-gray-400">Healthy</p>
                  </>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

// ─── Quick Actions ─────────────────────────────────────────────────────────────

function QuickActions() {
  const actions = [
    {
      label: "Look Up Claim",
      href: "/claims",
      icon: <Search className="h-4 w-4" />,
    },
    {
      label: "Start Billing Cycle",
      href: "/accounting/cycles",
      icon: <RefreshCw className="h-4 w-4" />,
    },
    {
      label: "Create Investigation",
      href: "/reclaimrx/investigations",
      icon: <Plus className="h-4 w-4" />,
    },
    {
      label: "Generate Report",
      href: "/reporting/library",
      icon: <FileText className="h-4 w-4" />,
    },
  ];

  return (
    <div>
      <h2 className="mb-3 text-base font-bold text-ifx-gray-900">
        Quick Actions
      </h2>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <Link
            key={a.label}
            href={a.href}
            className="inline-flex items-center gap-2 rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue hover:text-ifx-blue transition-colors ifx-card-shadow"
            aria-label={a.label}
          >
            {a.icon}
            {a.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

// ─── Onboarding checklist ─────────────────────────────────────────────────────

function OnboardingChecklist({
  userId,
  onDismiss,
}: {
  userId: string;
  onDismiss: () => void;
}) {
  const [completed, setCompleted] = useState<Set<string>>(new Set());
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const _uid = userId;

  const steps = [
    {
      id: "mfa",
      label: "Set up MFA (required)",
      link: "/settings/profile#mfa",
      required: true,
    },
    {
      id: "layout",
      label: "Choose your dashboard preset",
      link: null,
      required: false,
    },
    {
      id: "tutorial",
      label: "Review the billing workflow tutorial",
      link: "/accounting/cycles",
      required: false,
    },
    {
      id: "cmdK",
      label: "Explore the command palette (Cmd+K)",
      link: null,
      required: false,
    },
  ];

  function toggle(id: string) {
    setCompleted((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="mb-6 rounded-lg border border-ifx-gray-100 bg-white ifx-card-shadow p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-bold text-base text-ifx-gray-900">
            Welcome to InfinityRx ICP!
          </h2>
          <p className="text-sm text-ifx-gray-400 mt-0.5">
            Complete these steps to get started.
          </p>
        </div>
        <button
          onClick={onDismiss}
          aria-label="Dismiss onboarding checklist"
          className="text-ifx-gray-400 hover:text-ifx-gray-700"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="space-y-2">
        {steps.map((step) => (
          <label
            key={step.id}
            className="flex cursor-pointer items-center gap-3 rounded-md p-2 hover:bg-[var(--ifx-lavender)] transition-colors"
          >
            <input
              type="checkbox"
              checked={completed.has(step.id)}
              onChange={() => toggle(step.id)}
              className="h-4 w-4 accent-[var(--ifx-navy)] cursor-pointer"
            />
            <span
              className={cn(
                "flex-1 text-sm",
                completed.has(step.id) && "line-through text-ifx-gray-400"
              )}
            >
              {step.label}
              {step.required && (
                <span className="ml-1 text-xs text-red-500">*</span>
              )}
            </span>
            {step.link && (
              <Link
                href={step.link}
                className="text-xs text-ifx-blue hover:underline shrink-0"
                onClick={(e) => e.stopPropagation()}
              >
                Start →
              </Link>
            )}
          </label>
        ))}
      </div>
      <button
        onClick={onDismiss}
        className="mt-3 text-xs text-ifx-gray-400 hover:text-ifx-gray-700 underline"
      >
        Dismiss — I&apos;ll figure it out myself
      </button>
    </div>
  );
}

// ─── Main Dashboard Page ───────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const [selectedPreset, setSelectedPreset] = useState<PresetId>("overview");
  const [showOnboarding, setShowOnboarding] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem(PRESET_STORAGE_KEY) as PresetId | null;
    if (saved && PRESETS.some((p) => p.id === saved)) {
      setSelectedPreset(saved);
    }
    const userId = user?.id ?? "default";
    if (!localStorage.getItem(`${ONBOARDING_FLAG}-${userId}`)) {
      setShowOnboarding(true);
    }
  }, [user?.id]);

  function handlePresetChange(preset: PresetId) {
    setSelectedPreset(preset);
    localStorage.setItem(PRESET_STORAGE_KEY, preset);
  }

  function dismissOnboarding() {
    const userId = user?.id ?? "default";
    localStorage.setItem(`${ONBOARDING_FLAG}-${userId}`, "true");
    setShowOnboarding(false);
  }

  const { data: kpiData, isLoading: kpiLoading } = useQuery({
    queryKey: ["dashboard-kpi"],
    queryFn: () => apiGet<DashboardKpi>("/api/v1/dashboard/kpi"),
    staleTime: 60_000,
  });

  // B11 w2.x — honest unavailable rendering. If the BFF reports a field
  // in unavailable_fields, show "Unavailable" instead of "0" so an
  // operator can distinguish "real zero" from "data not yet wired".
  // Removes the pre-w2 lie that the dashboard always rendered zeros
  // alongside hardcoded fake-trend subtext.
  const unavailable = new Set(kpiData?.unavailable_fields ?? []);
  const isUnavailable = (field: string) => unavailable.has(field);

  const kpiCards = [
    {
      label: "Active Programs",
      value: kpiData?.active_programs ?? 0,
      format: "number" as const,
      href: "/programs",
      accentColor: "var(--ifx-navy)",
      icon: <Layers className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("active_programs"),
    },
    {
      label: "Total Claims YTD",
      value: kpiData?.total_claims_ytd ?? 0,
      format: "number" as const,
      href: "/claims",
      accentColor: "var(--ifx-blue)",
      icon: <ClipboardList className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("total_claims_ytd"),
    },
    {
      label: "Total Copay Spend",
      value: kpiData?.total_copay_spend_ytd ?? "0.00",
      format: "currency-compact" as const,
      href: "/accounting/cycles",
      accentColor: "var(--ifx-success)",
      icon: <CreditCard className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("total_copay_spend_ytd"),
    },
    {
      label: "GTN Ratio",
      value: kpiData?.gtn_ratio ? parseFloat(kpiData.gtn_ratio) : 0,
      format: "percent" as const,
      href: "/reclaimrx",
      accentColor: "var(--ifx-pink)",
      icon: <TrendingUp className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("gtn_ratio"),
      // B11 w2.x: removed hardcoded trend={value:1.4, direction:"down",
      // label:"vs last month"}. That subtext was a fabricated "compared
      // to nothing" lie. Real trend computation belongs to a backend
      // aggregation slice; until that exists, show no trend rather than
      // a fake one.
    },
    {
      label: "Active Investigations",
      value: kpiData?.active_investigations ?? 0,
      format: "number" as const,
      href: "/reclaimrx/investigations",
      accentColor: "var(--ifx-warning)",
      icon: <AlertCircle className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("active_investigations"),
    },
    {
      label: "Pending Payments",
      value: kpiData?.pending_payments ?? 0,
      format: "number" as const,
      href: "/accounting/payments",
      accentColor: "var(--ifx-error)",
      icon: <LayoutDashboard className="h-4 w-4" />,
      loading: kpiLoading,
      unavailable: isUnavailable("pending_payments"),
    },
  ];

  return (
    <div className="mx-auto max-w-7xl">
      {showOnboarding && user && (
        <OnboardingChecklist userId={user.id} onDismiss={dismissOnboarding} />
      )}

      {/* Page header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ifx-gray-900">Dashboard</h1>
          <p className="text-sm text-ifx-gray-400">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""}
          </p>
        </div>

        {/* Preset selector tabs */}
        <div className="flex items-center gap-1.5 flex-wrap" role="tablist" aria-label="Dashboard preset">
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              role="tab"
              aria-selected={selectedPreset === preset.id}
              onClick={() => handlePresetChange(preset.id)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                selectedPreset === preset.id
                  ? "bg-[var(--ifx-navy)] text-white"
                  : "border border-ifx-gray-100 hover:border-ifx-blue text-ifx-gray-400 hover:text-ifx-blue bg-white"
              )}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI cards — ALL have href, zero display-only */}
      <section aria-label="Key performance indicators" className="mb-6">
        <KpiCardRow cards={kpiCards} columns={6} />
      </section>

      {/* Program Health */}
      <section aria-label="Program health" className="mb-6">
        <ProgramHealthSection />
      </section>

      {/* 2-column: activity feed + alerts */}
      <section aria-label="Activity and alerts" className="mb-6">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ActivityFeedSection />
          <AlertsSection />
        </div>
      </section>

      {/* Quick Actions */}
      <section aria-label="Quick actions">
        <QuickActions />
      </section>
    </div>
  );
}
