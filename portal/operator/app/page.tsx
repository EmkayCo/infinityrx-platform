"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  FileText,
  RefreshCw,
  CheckCircle2,
  XCircle,
  X,
} from "lucide-react";
import { DashboardGrid, type WidgetConfig } from "@shared/components/widget-grid";
import { DashboardWidgetSkeleton } from "@shared/components/skeleton";
import { WidgetErrorBoundary } from "@shared/components/error-boundary";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ActivityFeed } from "@shared/components/activity-feed";

import { cn, formatRelative } from "@shared/lib/format";
import { API_URLS, DASHBOARD_PRESETS, type DashboardPreset } from "@shared/lib/constants";
import { useAuth } from "@shared/hooks/use-auth";
import { useSSE } from "@shared/hooks/use-sse";
import { apiGet } from "@shared/lib/api-client";
import type { ActivityEvent, ServiceHealth } from "@shared/types/common";

// ─── Dashboard preset layouts ───────────────────────────────────────────────

const PRESET_LAYOUTS: Record<DashboardPreset, WidgetConfig[]> = {
  billing_ops: [
    { id: "active-billing", size: "2x1" },
    { id: "payment-batches", size: "1x1" },
    { id: "ar-summary", size: "1x1" },
    { id: "activity-feed", size: "2x2" },
  ],
  fwa_investigation: [
    { id: "fwa-alerts", size: "2x1" },
    { id: "investigations", size: "1x1" },
    { id: "recovery-pipeline", size: "1x1" },
    { id: "activity-feed", size: "2x2" },
  ],
  executive: [
    { id: "claims-summary", size: "2x1" },
    { id: "system-health", size: "1x1" },
    { id: "recent-reports", size: "1x1" },
    { id: "activity-feed", size: "2x2" },
  ],
  system_admin: [
    { id: "system-health", size: "2x1" },
    { id: "active-sessions", size: "1x1" },
    { id: "audit-log-widget", size: "1x1" },
    { id: "activity-feed", size: "2x2" },
  ],
};

const PRESET_LABELS: Record<DashboardPreset, string> = {
  billing_ops: "Billing Operations",
  fwa_investigation: "FWA Investigation",
  executive: "Executive Overview",
  system_admin: "System Admin",
};

const LAYOUT_STORAGE_KEY_PREFIX = "ifx-dashboard-layout";
const PRESET_STORAGE_KEY = "ifx-dashboard-preset";
const ONBOARDING_FLAG = "ifx-onboarding-completed";

// ─── Widget implementations ──────────────────────────────────────────────────

function WidgetShell({
  title,
  children,
  lastUpdated,
  onRefresh,
  isLoading,
}: {
  title: string;
  children: React.ReactNode;
  lastUpdated?: Date | null;
  onRefresh?: () => void;
  isLoading?: boolean;
}) {
  return (
    <div className="flex h-full flex-col rounded-lg border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-semibold text-sm">{title}</h3>
        <div className="flex items-center gap-1">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground" aria-label={`Last updated ${formatRelative(lastUpdated)}`}>
              {formatRelative(lastUpdated)}
            </span>
          )}
          {onRefresh && (
            <button
              onClick={onRefresh}
              className={cn(
                "rounded p-1 text-muted-foreground hover:text-foreground transition-colors",
                isLoading && "animate-spin"
              )}
              aria-label="Refresh widget"
              disabled={isLoading}
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function ActiveBillingCyclesWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["billing-cycles-active"],
    queryFn: () =>
      apiGet<{ count: number; total_amount: string; next_action: string }>(
        `${API_URLS.billing}/billing-cycles/active`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Active Billing Cycles"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="space-y-3">
          <div>
            <p className="text-3xl font-bold tabular-nums">{data.count}</p>
            <p className="text-xs text-muted-foreground">active cycles</p>
          </div>
          <DollarDisplay amount={data.total_amount} size="lg" showScale />
          <p className="text-xs text-teal-600 dark:text-teal-400">{data.next_action}</p>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Service temporarily unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function PaymentBatchesPendingWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["payment-batches-pending"],
    queryFn: () =>
      apiGet<{ count: number; total_amount: string }>(
        `${API_URLS.payments}/payment-batches/pending`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Payment Batches Pending"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="space-y-3">
          <div>
            <p className="text-3xl font-bold tabular-nums">{data.count}</p>
            <p className="text-xs text-muted-foreground">awaiting approval</p>
          </div>
          <DollarDisplay amount={data.total_amount} size="lg" showScale />
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Service temporarily unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function FWAAlertsSummaryWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["fwa-alerts-summary"],
    queryFn: () =>
      apiGet<{ today: number; week: number; high_severity: number }>(
        `${API_URLS.reclaimrx}/flags/summary`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="FWA Alerts"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md bg-red-50 dark:bg-red-950/30 p-2 text-center">
            <p className="text-lg font-bold tabular-nums text-red-600 dark:text-red-400">
              {data.high_severity}
            </p>
            <p className="text-xs text-muted-foreground">High severity</p>
          </div>
          <div className="rounded-md bg-muted p-2 text-center">
            <p className="text-lg font-bold tabular-nums">{data.today}</p>
            <p className="text-xs text-muted-foreground">Today</p>
          </div>
          <div className="rounded-md bg-muted p-2 text-center">
            <p className="text-lg font-bold tabular-nums">{data.week}</p>
            <p className="text-xs text-muted-foreground">This week</p>
          </div>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Service temporarily unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function SystemHealthWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["system-health"],
    queryFn: () =>
      apiGet<{ services: ServiceHealth[] }>(`${API_URLS.corePlatform}/health`),
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="System Health"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="space-y-1.5">
          {data.services.map((service) => (
            <div key={service.service} className="flex items-center gap-2">
              {service.status === "healthy" ? (
                <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
              ) : service.status === "degraded" ? (
                <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-red-500 shrink-0" />
              )}
              <span className="text-sm flex-1">{service.service}</span>
              {service.latency_ms && (
                <span className="text-xs text-muted-foreground">{service.latency_ms}ms</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Health check unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function RecentReportsWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["recent-reports"],
    queryFn: () =>
      apiGet<{ reports: { id: string; name: string; generated_at: string }[] }>(
        `${API_URLS.reporting}/reports/recent`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Recent Reports"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data?.reports?.length ? (
        <div className="space-y-1.5">
          {data.reports.slice(0, 5).map((report) => (
            <div key={report.id} className="flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="flex-1 truncate text-sm">{report.name}</span>
              <span className="text-xs text-muted-foreground shrink-0">
                {formatRelative(report.generated_at)}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">No recent reports</p>
        </div>
      )}
    </WidgetShell>
  );
}

function ActivityFeedWidget() {
  const { events } = useSSE<ActivityEvent>({
    url: `${API_URLS.corePlatform}/activity/stream`,
  });

  const activityEvents = events.map((e) => e.data);

  return (
    <WidgetShell title="Activity Feed">
      <ActivityFeed events={activityEvents} />
    </WidgetShell>
  );
}

function ARSummaryWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["ar-summary"],
    queryFn: () =>
      apiGet<{ receivable: string; payable: string; net: string }>(
        `${API_URLS.billing}/ar/summary`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="AP/AR Summary"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Receivable</span>
            <DollarDisplay amount={data.receivable} size="sm" showScale />
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Payable</span>
            <DollarDisplay amount={data.payable} size="sm" showScale />
          </div>
          <div className="border-t pt-2 flex justify-between text-sm font-semibold">
            <span>Net</span>
            <DollarDisplay amount={data.net} size="sm" showScale />
          </div>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Service temporarily unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function ActiveSessionsWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["active-sessions"],
    queryFn: () =>
      apiGet<{ count: number; users: string[] }>(
        `${API_URLS.corePlatform}/admin/sessions/active`
      ),
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Active Sessions"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div>
          <p className="text-3xl font-bold tabular-nums">{data.count}</p>
          <p className="text-xs text-muted-foreground mt-1">active sessions</p>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function AuditLogWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["audit-log-recent"],
    queryFn: () =>
      apiGet<{ entries: { id: string; action: string; user: string; created_at: string }[] }>(
        `${API_URLS.corePlatform}/audit/recent?limit=5`
      ),
    retry: 1,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Recent Audit Entries"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data?.entries?.length ? (
        <div className="space-y-1.5">
          {data.entries.map((entry) => (
            <div key={entry.id} className="flex items-center gap-2 text-xs">
              <span className="truncate flex-1 text-muted-foreground">{entry.action}</span>
              <span className="shrink-0">{entry.user}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">No recent entries</p>
        </div>
      )}
    </WidgetShell>
  );
}

function InvestigationsWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["investigations-active"],
    queryFn: () =>
      apiGet<{ active: number; by_stage: Record<string, number> }>(
        `${API_URLS.reclaimrx}/investigations/summary`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Active Investigations"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div>
          <p className="text-3xl font-bold tabular-nums">{data.active}</p>
          <p className="text-xs text-muted-foreground mt-1">active investigations</p>
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function RecoveryPipelineWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["recovery-pipeline"],
    queryFn: () =>
      apiGet<{ estimated: string; demanded: string; collected: string }>(
        `${API_URLS.reclaimrx}/recovery/pipeline`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Recovery Pipeline"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="space-y-2">
          {[
            { label: "Estimated", amount: data.estimated },
            { label: "Demanded", amount: data.demanded },
            { label: "Collected", amount: data.collected },
          ].map(({ label, amount }) => (
            <div key={label} className="flex justify-between text-sm">
              <span className="text-muted-foreground">{label}</span>
              <DollarDisplay amount={amount} size="sm" showScale />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

function ClaimsSummaryWidget() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["claims-summary"],
    queryFn: () =>
      apiGet<{ today: number; mtd: number; ytd: number }>(
        `${API_URLS.billing}/claims/summary`
      ),
    retry: 2,
  });

  if (isLoading) return <DashboardWidgetSkeleton />;

  return (
    <WidgetShell
      title="Claims Processed"
      onRefresh={() => refetch()}
      isLoading={isLoading}
      lastUpdated={dataUpdatedAt ? new Date(dataUpdatedAt) : null}
    >
      {data ? (
        <div className="grid grid-cols-3 gap-2">
          {[
            { label: "Today", value: data.today },
            { label: "MTD", value: data.mtd },
            { label: "YTD", value: data.ytd },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-md bg-muted p-2 text-center">
              <p className="text-lg font-bold tabular-nums">
                {value?.toLocaleString() ?? "—"}
              </p>
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex h-full items-center justify-center">
          <p className="text-sm text-muted-foreground">Unavailable</p>
        </div>
      )}
    </WidgetShell>
  );
}

// ─── Widget renderer ─────────────────────────────────────────────────────────

function renderWidget(config: WidgetConfig) {
  const widgetMap: Record<string, React.ReactNode> = {
    "active-billing": (
      <WidgetErrorBoundary title="Active Billing Cycles">
        <ActiveBillingCyclesWidget />
      </WidgetErrorBoundary>
    ),
    "payment-batches": (
      <WidgetErrorBoundary title="Payment Batches Pending">
        <PaymentBatchesPendingWidget />
      </WidgetErrorBoundary>
    ),
    "fwa-alerts": (
      <WidgetErrorBoundary title="FWA Alerts">
        <FWAAlertsSummaryWidget />
      </WidgetErrorBoundary>
    ),
    "system-health": (
      <WidgetErrorBoundary title="System Health">
        <SystemHealthWidget />
      </WidgetErrorBoundary>
    ),
    "recent-reports": (
      <WidgetErrorBoundary title="Recent Reports">
        <RecentReportsWidget />
      </WidgetErrorBoundary>
    ),
    "activity-feed": (
      <WidgetErrorBoundary title="Activity Feed">
        <ActivityFeedWidget />
      </WidgetErrorBoundary>
    ),
    "ar-summary": (
      <WidgetErrorBoundary title="AP/AR Summary">
        <ARSummaryWidget />
      </WidgetErrorBoundary>
    ),
    "active-sessions": (
      <WidgetErrorBoundary title="Active Sessions">
        <ActiveSessionsWidget />
      </WidgetErrorBoundary>
    ),
    "audit-log-widget": (
      <WidgetErrorBoundary title="Recent Audit Entries">
        <AuditLogWidget />
      </WidgetErrorBoundary>
    ),
    "investigations": (
      <WidgetErrorBoundary title="Active Investigations">
        <InvestigationsWidget />
      </WidgetErrorBoundary>
    ),
    "recovery-pipeline": (
      <WidgetErrorBoundary title="Recovery Pipeline">
        <RecoveryPipelineWidget />
      </WidgetErrorBoundary>
    ),
    "claims-summary": (
      <WidgetErrorBoundary title="Claims Processed">
        <ClaimsSummaryWidget />
      </WidgetErrorBoundary>
    ),
  };

  return (
    widgetMap[config.id] ?? (
      <div className="flex h-full items-center justify-center rounded-lg border bg-card">
        <p className="text-sm text-muted-foreground">{config.id}</p>
      </div>
    )
  );
}

// ─── Onboarding checklist ─────────────────────────────────────────────────────

function OnboardingChecklist({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  userId: _userId,
  onDismiss,
}: {
  userId: string;
  onDismiss: () => void;
}) {
  const [completed, setCompleted] = useState<Set<string>>(new Set());

  const steps = [
    { id: "mfa", label: "Set up MFA (required)", link: "/settings/profile#mfa", required: true },
    { id: "layout", label: "Choose your dashboard layout", action: () => {}, required: false },
    { id: "tutorial", label: "Review the billing workflow tutorial", link: "/billing/tutorial", required: false },
    { id: "cmdK", label: "Explore the command palette (Cmd+K)", action: () => {}, required: false },
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
    <div className="mb-6 rounded-lg border bg-card p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-base">Welcome to InfinityRx!</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Complete these steps to get started.
          </p>
        </div>
        <button
          onClick={onDismiss}
          aria-label="Dismiss onboarding checklist"
          className="text-muted-foreground hover:text-foreground"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="space-y-2">
        {steps.map((step) => (
          <label
            key={step.id}
            className="flex cursor-pointer items-center gap-3 rounded-md p-2 hover:bg-muted transition-colors"
          >
            <input
              type="checkbox"
              checked={completed.has(step.id)}
              onChange={() => toggle(step.id)}
              className="h-4 w-4 accent-teal-500 cursor-pointer"
            />
            <span
              className={cn(
                "flex-1 text-sm",
                completed.has(step.id) && "line-through text-muted-foreground"
              )}
            >
              {step.label}
              {step.required && (
                <span className="ml-1 text-xs text-red-500">*</span>
              )}
            </span>
            {step.link && (
              <a
                href={step.link}
                className="text-xs text-teal-600 dark:text-teal-400 hover:underline shrink-0"
                onClick={(e) => e.stopPropagation()}
              >
                Start →
              </a>
            )}
          </label>
        ))}
      </div>
      <button
        onClick={onDismiss}
        className="mt-3 text-xs text-muted-foreground hover:text-foreground underline"
      >
        Dismiss — I&apos;ll figure it out myself
      </button>
    </div>
  );
}

// ─── Main dashboard page ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const { user } = useAuth();
  const [selectedPreset, setSelectedPreset] = useState<DashboardPreset>("billing_ops");
  const [showOnboarding, setShowOnboarding] = useState(false);

  // Load saved preset and check onboarding
  useEffect(() => {
    const savedPreset = localStorage.getItem(PRESET_STORAGE_KEY) as DashboardPreset | null;
    if (savedPreset && DASHBOARD_PRESETS.includes(savedPreset)) {
      setSelectedPreset(savedPreset);
    }

    const userId = user?.id ?? "default";
    const onboardingDone = localStorage.getItem(`${ONBOARDING_FLAG}-${userId}`);
    if (!onboardingDone) {
      setShowOnboarding(true);
    }
  }, [user?.id]);

  function handlePresetChange(preset: DashboardPreset) {
    setSelectedPreset(preset);
    localStorage.setItem(PRESET_STORAGE_KEY, preset);
    // Clear saved custom layout so preset applies fresh
    localStorage.removeItem(`${LAYOUT_STORAGE_KEY_PREFIX}-${preset}`);
  }

  function dismissOnboarding() {
    const userId = user?.id ?? "default";
    localStorage.setItem(`${ONBOARDING_FLAG}-${userId}`, "true");
    setShowOnboarding(false);
  }

  const currentWidgets = PRESET_LAYOUTS[selectedPreset];
  const storageKey = `${LAYOUT_STORAGE_KEY_PREFIX}-${selectedPreset}`;

  return (
    <div className="max-w-7xl mx-auto">
      {/* Onboarding checklist */}
      {showOnboarding && user && (
        <OnboardingChecklist userId={user.id} onDismiss={dismissOnboarding} />
      )}

      {/* Page header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Welcome back{user?.name ? `, ${user.name.split(" ")[0]}` : ""}
          </p>
        </div>

        {/* Preset selector */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground hidden sm:inline">Layout:</span>
          {DASHBOARD_PRESETS.map((preset) => (
            <button
              key={preset}
              onClick={() => handlePresetChange(preset)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                selectedPreset === preset
                  ? "bg-teal-500 text-white"
                  : "border hover:bg-muted text-muted-foreground"
              )}
              aria-pressed={selectedPreset === preset}
            >
              {PRESET_LABELS[preset]}
            </button>
          ))}
        </div>
      </div>

      {/* Widget grid */}
      <DashboardGrid
        widgets={currentWidgets}
        storageKey={storageKey}
        renderWidget={renderWidget}
      />
    </div>
  );
}
