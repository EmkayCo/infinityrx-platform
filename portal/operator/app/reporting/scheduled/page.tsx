"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Pause, Play, Trash2, Edit } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, apiPatch, apiDelete, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ScheduledReport } from "@shared/types/reporting";
import { cn, formatDate, formatDateTime } from "@shared/lib/format";

const columns: ColDef<ScheduledReport>[] = [
  {
    accessorKey: "template_name",
    header: "Report",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "frequency",
    header: "Schedule",
    cell: (c) => {
      const row = c.row.original;
      const freq = c.getValue() as string;
      const details =
        freq === "weekly"
          ? `Weekly (Day ${row.day_of_week ?? 1})`
          : freq === "monthly"
          ? `Monthly (Day ${row.day_of_month ?? 1})`
          : "Daily";
      const time = `${String(row.hour).padStart(2, "0")}:${String(row.minute).padStart(2, "0")}`;
      return <span className="text-slate-300 text-sm">{details} at {time}</span>;
    },
  },
  {
    accessorKey: "format",
    header: "Format",
    cell: (c) => (
      <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-300 uppercase">
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "is_active",
    header: "Status",
    cell: (c) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded",
          c.getValue() ? "bg-green-900/40 text-green-300" : "bg-slate-700 text-slate-400"
        )}
      >
        {c.getValue() ? "Active" : "Paused"}
      </span>
    ),
  },
  {
    accessorKey: "last_run",
    header: "Last Run",
    cell: (c) => (
      <span className="text-xs text-slate-400">
        {c.getValue() ? formatDate(c.getValue() as string) : "Never"}
      </span>
    ),
  },
  {
    accessorKey: "next_run",
    header: "Next Run",
    cell: (c) => (
      <span className="text-xs text-slate-400">
        {c.getValue() ? formatDateTime(c.getValue() as string) : "—"}
      </span>
    ),
  },
  {
    accessorKey: "recipients",
    header: "Recipients",
    cell: (c) => {
      const recips = c.getValue() as string[];
      return (
        <span className="text-xs text-slate-400">
          {recips.length} recipient{recips.length !== 1 ? "s" : ""}
        </span>
      );
    },
  },
];

function CreateScheduleModal({
  onClose,
  onSave,
}: {
  onClose: () => void;
  onSave: (data: Partial<ScheduledReport>) => void;
}) {
  const [form, setForm] = useState<Partial<ScheduledReport>>({
    frequency: "daily",
    hour: 8,
    minute: 0,
    format: "pdf",
    recipients: [],
    is_active: true,
  });
  const [recipientInput, setRecipientInput] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-lg rounded-xl border border-ifx-border-dark bg-navy-900 p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-5">Create Scheduled Report</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Frequency</label>
            <div className="flex gap-2">
              {(["daily", "weekly", "monthly"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setForm((prev) => ({ ...prev, frequency: f }))}
                  className={cn(
                    "flex-1 py-2 rounded-lg border text-sm capitalize transition-colors",
                    form.frequency === f
                      ? "border-teal-500 bg-teal-900/20 text-teal-300"
                      : "border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Hour (UTC)</label>
              <input
                type="number"
                min={0}
                max={23}
                value={form.hour ?? 8}
                onChange={(e) => setForm((prev) => ({ ...prev, hour: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">Minute</label>
              <input
                type="number"
                min={0}
                max={59}
                value={form.minute ?? 0}
                onChange={(e) => setForm((prev) => ({ ...prev, minute: parseInt(e.target.value) }))}
                className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Format</label>
            <select
              value={form.format ?? "pdf"}
              onChange={(e) => setForm((prev) => ({ ...prev, format: e.target.value as "pdf" | "excel" | "csv" }))}
              className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
            >
              {["pdf", "excel", "csv", "html"].map((f) => (
                <option key={f} value={f}>{f.toUpperCase()}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Recipients</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={recipientInput}
                onChange={(e) => setRecipientInput(e.target.value)}
                placeholder="email@example.com"
                className="flex-1 px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
              <button
                onClick={() => {
                  if (recipientInput) {
                    setForm((prev) => ({
                      ...prev,
                      recipients: [...(prev.recipients ?? []), recipientInput],
                    }));
                    setRecipientInput("");
                  }
                }}
                className="px-3 py-2 rounded-lg bg-navy-700 hover:bg-navy-500 text-slate-200 text-sm transition-colors"
              >
                Add
              </button>
            </div>
            {(form.recipients ?? []).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {(form.recipients ?? []).map((r) => (
                  <span
                    key={r}
                    className="text-xs px-2 py-0.5 rounded-full bg-navy-700 text-slate-300 flex items-center gap-1"
                  >
                    {r}
                    <button
                      onClick={() =>
                        setForm((prev) => ({
                          ...prev,
                          recipients: (prev.recipients ?? []).filter((x) => x !== r),
                        }))
                      }
                      className="text-slate-500 hover:text-red-400"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => { onSave(form); onClose(); }}
            className="px-4 py-2 text-sm rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium transition-colors"
          >
            Create Schedule
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ScheduledReportsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);

  const { data: schedules = [], isLoading } = useQuery<ScheduledReport[]>({
    queryKey: ["scheduled-reports"],
    queryFn: () =>
      apiGet<ScheduledReport[]>(buildUrl(`${API_URLS.reporting}/api/v1/reports/scheduled`)),
    staleTime: 60_000,
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      apiPatch(`${API_URLS.reporting}/api/v1/reports/scheduled/${id}`, { is_active: active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scheduled-reports"] });
    },
  });

  const deleteSchedule = useMutation({
    mutationFn: (id: string) =>
      apiDelete(`${API_URLS.reporting}/api/v1/reports/scheduled/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["scheduled-reports"] });
    },
  });

  const actionColumns: ColDef<ScheduledReport>[] = [
    ...columns,
    {
      id: "actions",
      header: "Actions",
      cell: (c) => {
        const row = c.row.original;
        return (
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); toggleActive.mutate({ id: row.id, active: !row.is_active }); }}
              className="p-1.5 rounded hover:bg-navy-700 text-slate-400 hover:text-slate-200 transition-colors"
              title={row.is_active ? "Pause" : "Resume"}
            >
              {row.is_active ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); /* edit */ }}
              className="p-1.5 rounded hover:bg-navy-700 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <Edit className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (confirm("Delete this scheduled report?")) deleteSchedule.mutate(row.id);
              }}
              className="p-1.5 rounded hover:bg-red-900/20 text-slate-400 hover:text-red-400 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="p-6 space-y-6">
      {showCreate && (
        <CreateScheduleModal
          onClose={() => setShowCreate(false)}
          onSave={() => {/* save logic via mutation */}}
        />
      )}

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Scheduled Reports</h1>
          <p className="text-slate-400 text-sm mt-1">
            {schedules.length} active schedules
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Schedule
        </button>
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={actionColumns}
            data={schedules}
            isLoading={isLoading}
            emptyTitle="No scheduled reports"
            emptyDescription="Create a schedule to automatically generate and deliver reports."
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
