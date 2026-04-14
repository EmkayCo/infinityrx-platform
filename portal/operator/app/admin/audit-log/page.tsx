"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { TableSkeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";
import { ErrorFallback } from "@shared/components/error-boundary";
import { ExportMenu } from "@shared/components/export-menu";
import { formatDateTime, cn } from "@shared/lib/format";
import { useExport } from "@shared/hooks/use-export";

interface AuditEntry {
  id: string;
  user_id: string;
  user_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  tenant_id: string;
  ip_address: string;
  created_at: string;
  before_state?: Record<string, unknown>;
  after_state?: Record<string, unknown>;
  hash: string;
}

const ACTION_COLORS: Record<string, string> = {
  create: "text-green-600 dark:text-green-400",
  update: "text-blue-600 dark:text-blue-400",
  delete: "text-red-600 dark:text-red-400",
  login: "text-slate-600 dark:text-slate-400",
  logout: "text-slate-600 dark:text-slate-400",
  phi_access: "text-amber-600 dark:text-amber-400",
  approve: "text-teal-600 dark:text-teal-400",
  reject: "text-red-600 dark:text-red-400",
};

export default function AuditLogPage() {
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["audit-log", page, search, dateFrom, dateTo, actionFilter],
    queryFn: () =>
      apiGet<{ entries: AuditEntry[]; total: number; page: number; page_size: number }>(
        buildUrl(`${API_URLS.corePlatform}/audit/entries`, {
          page,
          page_size: 50,
          search: search || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          action: actionFilter || undefined,
        })
      ),
    retry: 2,
  });

  const exportColumns = [
    { header: "Timestamp", accessor: "created_at", format: (v: unknown) => formatDateTime(v as string) },
    { header: "User", accessor: "user_name" },
    { header: "Action", accessor: "action" },
    { header: "Entity Type", accessor: "entity_type" },
    { header: "Entity ID", accessor: "entity_id" },
    { header: "IP Address", accessor: "ip_address" },
    { header: "Entry Hash", accessor: "hash" },
  ];

  const { exportData } = useExport({
    filename: "audit-log",
    title: "IFX Audit Log — CONFIDENTIAL",
    columns: exportColumns,
  });

  if (error) {
    return (
      <ErrorFallback
        error={error instanceof Error ? error : new Error("Failed to load audit log")}
        onRetry={() => refetch()}
      />
    );
  }

  const entries = data?.entries ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="max-w-7xl mx-auto">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Audit Log</h1>
          <p className="text-sm text-muted-foreground">
            Tamper-evident log of all system actions
          </p>
        </div>
        <ExportMenu
          onExport={(format) => exportData(entries as unknown as Record<string, unknown>[], format)}
          label="Export"
        />
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="search"
            placeholder="Search by user, action, entity..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full rounded-md border bg-card pl-9 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            aria-label="Search audit log"
          />
        </div>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
          className="rounded-md border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          aria-label="Date from"
        />
        <input
          type="date"
          value={dateTo}
          onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
          className="rounded-md border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          aria-label="Date to"
        />
        <select
          value={actionFilter}
          onChange={(e) => { setActionFilter(e.target.value); setPage(1); }}
          className="rounded-md border bg-card px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          aria-label="Filter by action"
        >
          <option value="">All actions</option>
          <option value="create">Create</option>
          <option value="update">Update</option>
          <option value="delete">Delete</option>
          <option value="login">Login</option>
          <option value="phi_access">PHI Access</option>
          <option value="approve">Approve</option>
          <option value="reject">Reject</option>
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <TableSkeleton rows={10} cols={6} />
      ) : entries.length === 0 ? (
        <EmptyState
          title="No audit entries found"
          description="Try adjusting your filters or date range."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Audit log table">
              <thead className="border-b bg-muted/50">
                <tr>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Timestamp</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">User</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Action</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Entity</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">IP</th>
                  <th scope="col" className="px-4 py-3 text-left font-medium">Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">
                      {formatDateTime(entry.created_at)}
                    </td>
                    <td className="px-4 py-3 font-medium">{entry.user_name}</td>
                    <td className="px-4 py-3">
                      <span className={cn("font-medium capitalize", ACTION_COLORS[entry.action] ?? "")}>
                        {entry.action.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      <span>{entry.entity_type}</span>
                      {entry.entity_id && (
                        <span className="ml-1 font-mono">{entry.entity_id.slice(0, 8)}…</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {entry.ip_address}
                    </td>
                    <td className="px-4 py-3 text-xs font-mono text-muted-foreground">
                      {entry.hash ? `${entry.hash.slice(0, 8)}…` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {total > 0 && (
        <div className="mt-4 flex items-center justify-between">
          <p className="text-xs text-muted-foreground">
            Showing {(page - 1) * 50 + 1}–{Math.min(page * 50, total)} of {total.toLocaleString()} entries
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50 hover:bg-muted transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={page * 50 >= total}
              className="rounded-md border px-3 py-1.5 text-xs disabled:opacity-50 hover:bg-muted transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
