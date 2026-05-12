"use client";

// Echo Spec 400 operations page — Wave 41 M6.
//
// Lists Spec 400 runs with status, totals, sha256 hashes; provides
// a manual-trigger button for the daily candor pipeline; surfaces
// recent status file ingestions. Wired to the Wave 41 admin API.

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Banknote, PlayCircle, Loader2, RefreshCw } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listEchoRuns, listEchoIngestions, runEchoCandor,
  type EchoSpec400Run, type EchoSpec400ListQuery, type EchoRunStatus,
  type EchoStatusFileIngestion,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { StatusBadge } from "@/components/ui/status-badge";

const RUN_STATUS_VARIANTS = {
  pending_submission: "warning",
  submitted: "info",
  status_received: "success",
  reconciled: "success",
  failed: "error",
} as const;

export default function EchoSpec400Page() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "created_at", sort_dir: "desc",
  }), [params]);

  const status = (params.get("status") as EchoRunStatus | null) ?? undefined;

  const [rows, setRows] = useState<EchoSpec400Run[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ingestions, setIngestions] = useState<EchoStatusFileIngestion[]>([]);
  const [running, setRunning] = useState(false);

  function refresh() {
    setLoading(true);
    const q: EchoSpec400ListQuery = { ...pagination, status };
    Promise.all([listEchoRuns(q), listEchoIngestions()])
      .then(([runs, ings]) => {
        setRows(runs.items);
        setTotal(runs.total);
        setIngestions(ings.slice(0, 10));
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError
          ? `${e.code}: ${e.message}` : String(e);
        setError(msg);
        toast.error(`Failed to load Echo data — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [pagination, status]);

  async function handleRunCandor() {
    if (!confirm(
      "Run Echo candor now? This generates a Spec 400 file from " +
      "all eligible manual AP records and uploads it to Echo's SFTP. " +
      "Cannot be undone.",
    )) return;
    setRunning(true);
    try {
      const result = await runEchoCandor();
      if (result.skipped_reason) {
        toast.info(`Candor skipped: ${result.skipped_reason}`);
      } else {
        toast.success(
          `Candor complete: ${result.eligible_count} APs, ` +
          (result.generation
            ? `$${result.generation.total_amount} sent. `
            : "") +
          `${result.status_files_ingested} status files ingested.`,
        );
      }
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError
        ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Candor run failed — ${msg}`);
    } finally {
      setRunning(false);
    }
  }

  const columns: PaginatedColumn<EchoSpec400Run>[] = [
    {
      id: "run_date", header: "Run date", sortKey: "run_date",
      accessor: (row) => <span className="font-mono text-xs">{row.run_date}</span>,
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <StatusBadge status={row.status.replace(/_/g, " ")}
                                     variant={RUN_STATUS_VARIANTS[row.status]} />,
    },
    {
      id: "records", header: "Records", align: "right",
      accessor: (row) => row.record_count.toLocaleString(),
    },
    {
      id: "ap_count", header: "APs", align: "right",
      accessor: (row) => row.manual_ap_record_ids.length.toLocaleString(),
    },
    {
      id: "total", header: "Total amount", sortKey: "total_amount", align: "right",
      accessor: (row) => `$${Number(row.total_amount).toLocaleString(undefined, {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      })}`,
    },
    {
      id: "submitted", header: "Submitted",
      accessor: (row) => row.submitted_at
        ? <span className="text-xs">{new Date(row.submitted_at).toLocaleString()}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "status_received", header: "Status received",
      accessor: (row) => row.status_file_received_at
        ? <span className="text-xs">{new Date(row.status_file_received_at).toLocaleDateString()}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "sha", header: "SHA-256",
      accessor: (row) => row.file_sha256
        ? <span className="font-mono text-[10px] text-muted-foreground">
            {row.file_sha256.slice(0, 12)}…
          </span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-amber-500/10 p-2">
            <Banknote className="h-5 w-5 text-amber-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Echo Spec 400</h1>
            <p className="text-sm text-muted-foreground">
              Daily candor: eligible Echo-channel manual AP records →
              fixed-width Spec 400 file → Echo SFTP. Status responses
              ingest the Payment Status File and reconcile back to AP
              records. Failed payments auto-create we-owe-pharmacy
              carryovers.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={refresh}
                  className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted">
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button onClick={handleRunCandor} disabled={running}
                  className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
            {running
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <PlayCircle className="h-3.5 w-3.5" />}
            Run candor now
          </button>
        </div>
      </div>

      <PaginatedTable<EchoSpec400Run>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(r) => r.id}
        emptyTitle="No Spec 400 runs yet"
        emptyHint="Run candor manually to generate the first Spec 400 file, or wait for the scheduled daily job."
      />

      {ingestions.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-sm font-semibold">
            Recent status file ingestions
          </h2>
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">File</th>
                  <th className="px-3 py-2 text-left">Downloaded</th>
                  <th className="px-3 py-2 text-right">Records</th>
                  <th className="px-3 py-2 text-right">Matched</th>
                  <th className="px-3 py-2 text-right">Unmatched</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {ingestions.map((ing) => (
                  <tr key={ing.id}>
                    <td className="px-3 py-1.5 font-mono text-xs">
                      {ing.remote_filename}
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {new Date(ing.downloaded_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {ing.record_count ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {ing.records_matched ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {(ing.records_unmatched ?? 0) > 0
                        ? <span className="text-amber-500">{ing.records_unmatched}</span>
                        : (ing.records_unmatched ?? "—")}
                    </td>
                    <td className="px-3 py-1.5 text-xs">{ing.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
