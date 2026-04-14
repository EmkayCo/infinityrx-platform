"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, AlertCircle, XCircle, RefreshCw, Activity } from "lucide-react";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { DashboardWidgetSkeleton } from "@shared/components/skeleton";
import { formatRelative } from "@shared/lib/format";
import { cn } from "@shared/lib/format";
import type { ServiceHealth } from "@shared/types/common";

interface SystemHealthData {
  services: ServiceHealth[];
  dlq_depth: number;
  event_bus_healthy: boolean;
  database_healthy: boolean;
  redis_healthy: boolean;
  checked_at: string;
}

function StatusIcon({ status }: { status: "healthy" | "degraded" | "unhealthy" }) {
  if (status === "healthy") return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  if (status === "degraded") return <AlertCircle className="h-5 w-5 text-amber-500" />;
  return <XCircle className="h-5 w-5 text-red-500" />;
}

const STATUS_LABELS = {
  healthy: "Healthy",
  degraded: "Degraded",
  unhealthy: "Unhealthy",
} as const;

const STATUS_BADGE = {
  healthy: "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400",
  degraded: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
  unhealthy: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400",
} as const;

export default function SystemHealthPage() {
  const { data, isLoading, refetch, dataUpdatedAt } = useQuery({
    queryKey: ["system-health-full"],
    queryFn: () =>
      apiGet<SystemHealthData>(`${API_URLS.corePlatform}/health/detailed`),
    refetchInterval: 30_000,
    retry: 1,
  });

  const overallStatus = data
    ? data.services.some((s) => s.status === "unhealthy")
      ? "unhealthy"
      : data.services.some((s) => s.status === "degraded")
      ? "degraded"
      : "healthy"
    : null;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">System Health</h1>
          <p className="text-sm text-muted-foreground">
            Real-time status of all platform services
          </p>
        </div>
        <div className="flex items-center gap-3">
          {dataUpdatedAt && (
            <span className="text-xs text-muted-foreground">
              Updated {formatRelative(new Date(dataUpdatedAt))}
            </span>
          )}
          <button
            onClick={() => refetch()}
            disabled={isLoading}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs hover:bg-muted transition-colors",
              isLoading && "opacity-50"
            )}
            aria-label="Refresh health status"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isLoading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <DashboardWidgetSkeleton key={i} />
          ))}
        </div>
      ) : data ? (
        <div className="space-y-6">
          {/* Overall status banner */}
          <div
            className={cn(
              "flex items-center gap-3 rounded-lg border p-4",
              overallStatus === "healthy" && "border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30",
              overallStatus === "degraded" && "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30",
              overallStatus === "unhealthy" && "border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30"
            )}
          >
            {overallStatus && <StatusIcon status={overallStatus} />}
            <div>
              <p className="font-semibold text-sm">
                Platform Status: {overallStatus ? STATUS_LABELS[overallStatus] : "Unknown"}
              </p>
              <p className="text-xs text-muted-foreground">
                {data.services.length} services monitored
              </p>
            </div>
          </div>

          {/* Infrastructure status */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              { label: "Database", healthy: data.database_healthy },
              { label: "Redis Cache", healthy: data.redis_healthy },
              { label: "Event Bus", healthy: data.event_bus_healthy },
            ].map(({ label, healthy }) => (
              <div key={label} className="flex items-center gap-3 rounded-lg border bg-card p-4">
                {healthy ? (
                  <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                ) : (
                  <XCircle className="h-5 w-5 text-red-500 shrink-0" />
                )}
                <div>
                  <p className="font-medium text-sm">{label}</p>
                  <p className={cn("text-xs", healthy ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400")}>
                    {healthy ? "Healthy" : "Unhealthy"}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* DLQ depth */}
          {(() => {
            const dlqDepth = data.dlq_depth ?? 0;
            return (
              <div className={cn(
                "flex items-center gap-3 rounded-lg border p-4",
                dlqDepth > 0 ? "border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/30" : "bg-card"
              )}>
                <Activity className={cn("h-5 w-5 shrink-0", dlqDepth > 0 ? "text-amber-500" : "text-green-500")} />
                <div className="flex-1">
                  <p className="font-medium text-sm">Dead Letter Queue</p>
                  <p className="text-xs text-muted-foreground">
                    {dlqDepth === 0 ? "No messages in DLQ" : `${dlqDepth} messages pending review`}
                  </p>
                </div>
                <span
                  className={cn(
                    "text-lg font-bold tabular-nums",
                    dlqDepth > 0 ? "text-amber-600 dark:text-amber-400" : "text-green-600 dark:text-green-400"
                  )}
                >
                  {dlqDepth}
                </span>
              </div>
            );
          })()}

          {/* Service list */}
          <div>
            <h2 className="mb-3 font-semibold text-base">Services</h2>
            <div className="overflow-hidden rounded-lg border bg-card">
              <table className="w-full text-sm" aria-label="Service health table">
                <thead className="border-b bg-muted/50">
                  <tr>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Service</th>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Status</th>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Latency</th>
                    <th scope="col" className="px-4 py-3 text-left font-medium">Last Checked</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {data.services.map((service) => (
                    <tr key={service.service} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-medium">{service.service}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <StatusIcon status={service.status} />
                          <span
                            className={cn(
                              "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                              STATUS_BADGE[service.status]
                            )}
                          >
                            {STATUS_LABELS[service.status]}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {service.latency_ms != null ? (
                          <span className={cn(
                            "font-mono text-xs",
                            service.latency_ms > 1000 ? "text-red-500" :
                            service.latency_ms > 500 ? "text-amber-500" : "text-green-600 dark:text-green-400"
                          )}>
                            {service.latency_ms}ms
                          </span>
                        ) : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">
                        {formatRelative(service.last_checked)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center">
          <XCircle className="mx-auto h-10 w-10 text-red-500 mb-3" />
          <p className="font-medium">Health check unavailable</p>
          <p className="text-sm text-muted-foreground mt-1">
            Could not reach the core platform service.
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 rounded-md bg-teal-500 px-4 py-2 text-sm text-white hover:bg-teal-600 transition-colors"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
