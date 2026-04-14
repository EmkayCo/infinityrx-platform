"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Edit, Save } from "lucide-react";
import { apiGet, apiPatch } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { TableSkeleton } from "@shared/components/skeleton";
import { ErrorFallback } from "@shared/components/error-boundary";
import { cn } from "@shared/lib/format";
import { toast } from "sonner";

interface TenantSettings {
  id: string;
  name: string;
  slug: string;
  mfa_required: boolean;
  max_concurrent_sessions: number;
  active: boolean;
  features: Record<string, boolean>;
}

export default function TenantsPage() {
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editBuffer, setEditBuffer] = useState<Partial<TenantSettings>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ["admin-tenants"],
    queryFn: () =>
      apiGet<{ tenants: TenantSettings[] }>(`${API_URLS.corePlatform}/admin/tenants`),
    retry: 2,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<TenantSettings> }) =>
      apiPatch(`${API_URLS.corePlatform}/admin/tenants/${id}`, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-tenants"] });
      setEditingId(null);
      setEditBuffer({});
      toast.success("Tenant settings saved");
    },
    onError: () => {
      toast.error("Failed to save tenant settings");
    },
  });

  if (error) {
    return (
      <ErrorFallback
        error={error instanceof Error ? error : new Error("Failed to load tenants")}
        onRetry={() => queryClient.invalidateQueries({ queryKey: ["admin-tenants"] })}
      />
    );
  }

  const tenants = data?.tenants ?? [];

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-bold">Tenant Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure per-tenant settings, MFA requirements, and feature flags
        </p>
      </div>

      {isLoading ? (
        <TableSkeleton rows={4} cols={5} />
      ) : (
        <div className="space-y-4">
          {tenants.map((tenant) => {
            const isEditing = editingId === tenant.id;
            const current = isEditing ? { ...tenant, ...editBuffer } : tenant;

            return (
              <div key={tenant.id} className="rounded-lg border bg-card p-5">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="font-semibold">{tenant.name}</h2>
                    <p className="text-sm text-muted-foreground font-mono">{tenant.slug}</p>
                  </div>
                  {!isEditing ? (
                    <button
                      onClick={() => { setEditingId(tenant.id); setEditBuffer({}); }}
                      className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                    >
                      <Edit className="h-3.5 w-3.5" />
                      Edit
                    </button>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={() => { setEditingId(null); setEditBuffer({}); }}
                        className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => updateMutation.mutate({ id: tenant.id, patch: editBuffer })}
                        disabled={updateMutation.isPending}
                        className="flex items-center gap-2 rounded-md bg-teal-500 px-3 py-1.5 text-sm text-white hover:bg-teal-600 disabled:opacity-50 transition-colors"
                      >
                        <Save className="h-3.5 w-3.5" />
                        Save
                      </button>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  {/* MFA Required */}
                  <div className="flex items-center justify-between rounded-md border p-3">
                    <span className="text-sm">MFA Required</span>
                    <button
                      role="switch"
                      aria-checked={current.mfa_required}
                      disabled={!isEditing}
                      onClick={() => isEditing && setEditBuffer((b) => ({ ...b, mfa_required: !current.mfa_required }))}
                      className={cn(
                        "relative inline-flex h-5 w-9 rounded-full border-2 border-transparent transition-colors",
                        current.mfa_required ? "bg-teal-500" : "bg-muted-foreground/30",
                        !isEditing && "cursor-not-allowed opacity-70"
                      )}
                      aria-label="Toggle MFA required"
                    >
                      <span
                        className={cn(
                          "inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200",
                          current.mfa_required && "translate-x-4"
                        )}
                      />
                    </button>
                  </div>

                  {/* Active */}
                  <div className="flex items-center justify-between rounded-md border p-3">
                    <span className="text-sm">Active</span>
                    <span className={cn(
                      "rounded-full px-2 py-0.5 text-xs font-medium",
                      tenant.active ? "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400" : "bg-muted text-muted-foreground"
                    )}>
                      {tenant.active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  {/* Max sessions */}
                  <div className="flex items-center justify-between rounded-md border p-3">
                    <span className="text-sm">Max Sessions</span>
                    {isEditing ? (
                      <input
                        type="number"
                        min={1}
                        max={20}
                        value={current.max_concurrent_sessions}
                        onChange={(e) => setEditBuffer((b) => ({ ...b, max_concurrent_sessions: parseInt(e.target.value) }))}
                        className="w-16 rounded border bg-card px-2 py-1 text-sm text-right focus:outline-none focus:ring-1 focus:ring-teal-500"
                        aria-label="Maximum concurrent sessions"
                      />
                    ) : (
                      <span className="font-mono text-sm">{tenant.max_concurrent_sessions}</span>
                    )}
                  </div>
                </div>

                {/* Feature flags */}
                {Object.keys(tenant.features).length > 0 && (
                  <div className="mt-4">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
                      Feature Flags
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(tenant.features).map(([flag, enabled]) => (
                        <button
                          key={flag}
                          role="switch"
                          aria-checked={isEditing ? (editBuffer.features?.[flag] ?? enabled) : enabled}
                          disabled={!isEditing}
                          onClick={() => {
                            if (!isEditing) return;
                            const current = editBuffer.features ?? { ...tenant.features };
                            setEditBuffer((b) => ({
                              ...b,
                              features: { ...current, [flag]: !current[flag] },
                            }));
                          }}
                          className={cn(
                            "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                            (isEditing ? (editBuffer.features?.[flag] ?? enabled) : enabled)
                              ? "bg-teal-100 text-teal-700 dark:bg-teal-950/50 dark:text-teal-400"
                              : "bg-muted text-muted-foreground",
                            !isEditing && "cursor-default"
                          )}
                        >
                          {flag.replace(/_/g, " ")}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
