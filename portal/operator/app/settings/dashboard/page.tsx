"use client";

import { useState } from "react";
import { RotateCcw } from "lucide-react";
import { DASHBOARD_PRESETS, type DashboardPreset } from "@shared/lib/constants";
import { cn } from "@shared/lib/format";
import { resetDashboardLayout } from "@shared/components/widget-grid";
import { toast } from "sonner";

const PRESET_INFO: Record<DashboardPreset, { label: string; description: string }> = {
  billing_ops: {
    label: "Billing Operations",
    description: "Active billing cycles, payment batches, AP/AR summary, and activity feed.",
  },
  fwa_investigation: {
    label: "FWA Investigation",
    description: "New flags, active investigations, recovery pipeline, and activity feed.",
  },
  executive: {
    label: "Executive Overview",
    description: "Claims processed, system health, recent reports, and activity feed.",
  },
  system_admin: {
    label: "System Admin",
    description: "Service health, active sessions, recent audit entries, and activity feed.",
  },
};

const PRESET_STORAGE_KEY = "ifx-dashboard-preset";
const LAYOUT_STORAGE_KEY_PREFIX = "ifx-dashboard-layout";

export default function DashboardSettingsPage() {
  const [selected, setSelected] = useState<DashboardPreset>(() => {
    if (typeof window === "undefined") return "billing_ops";
    return (localStorage.getItem(PRESET_STORAGE_KEY) as DashboardPreset) ?? "billing_ops";
  });

  function selectPreset(preset: DashboardPreset) {
    setSelected(preset);
    localStorage.setItem(PRESET_STORAGE_KEY, preset);
    toast.success(`Switched to ${PRESET_INFO[preset].label} layout`);
  }

  function resetLayout() {
    resetDashboardLayout(`${LAYOUT_STORAGE_KEY_PREFIX}-${selected}`);
    toast.success("Dashboard layout reset to preset default");
  }

  return (
    <div>
      <h2 className="text-base font-semibold mb-2">Dashboard Layout</h2>
      <p className="text-sm text-muted-foreground mb-6">
        Choose your default dashboard preset. You can also customize widget positions by dragging on the dashboard.
      </p>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {DASHBOARD_PRESETS.map((preset) => {
          const info = PRESET_INFO[preset];
          return (
            <button
              key={preset}
              onClick={() => selectPreset(preset)}
              className={cn(
                "rounded-lg border p-4 text-left transition-all",
                selected === preset
                  ? "border-teal-500 bg-teal-50 dark:bg-teal-950/30"
                  : "border bg-card hover:border-teal-500/50"
              )}
              aria-pressed={selected === preset}
            >
              <div className="flex items-center justify-between mb-1">
                <p className="font-medium text-sm">{info.label}</p>
                {selected === preset && (
                  <span className="rounded-full bg-teal-500 px-2 py-0.5 text-xs text-white">
                    Active
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground">{info.description}</p>
            </button>
          );
        })}
      </div>

      <div className="mt-6 border-t pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-sm">Reset Layout</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Reset the current preset to its default widget arrangement.
            </p>
          </div>
          <button
            onClick={resetLayout}
            className="flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted transition-colors"
          >
            <RotateCcw className="h-4 w-4" />
            Reset to default
          </button>
        </div>
      </div>
    </div>
  );
}
