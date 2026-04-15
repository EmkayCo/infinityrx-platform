"use client";

import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield,
  Search,
  Plus,
  Upload,
  Download,
  Edit,
  Trash2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { apiGet, apiPost, apiPut } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { TableSkeleton } from "@shared/components/skeleton";
import { EmptyState } from "@shared/components/empty-state";
import { ErrorFallback } from "@shared/components/error-boundary";
import { cn } from "@shared/lib/format";

const BASE = `${API_URLS.corePlatform}/government-programs`;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GovernmentBin {
  id: string;
  bin: string;
  pcn: string | null;
  group_number: string | null;
  plan_type: string;
  plan_subtype: string | null;
  pbm_name: string | null;
  plan_name: string | null;
  mco_name: string | null;
  state: string | null;
  government_flag: boolean;
  occ_codes: string | null;
  confidence: "HIGH" | "MEDIUM" | "LOW";
  source: string;
  source_date: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface CoverageReport {
  total_entries: number;
  by_plan_type: Record<string, number>;
  states_covered: number;
  medium_confidence_count: number;
  low_confidence_count: number;
}

interface CheckResult {
  is_government: boolean;
  confidence: string;
  match_type: string | null;
  plans: Array<{
    plan_type: string;
    plan_name: string | null;
    pbm_name: string | null;
    confidence: string;
    notes: string | null;
  }>;
}

interface CopayResult {
  eligible: boolean;
  status: "ELIGIBLE" | "BLOCKED" | "REVIEW";
  reason: string;
  government_check: CheckResult;
}

const PLAN_TYPES = [
  "MEDICARE_PART_D",
  "MEDICARE_ADVANTAGE",
  "MEDICAID_FFS",
  "MEDICAID_MCO",
  "TRICARE",
  "VA",
  "FEP",
  "IHS",
  "CHAMPVA",
] as const;

const PLAN_TYPE_LABELS: Record<string, string> = {
  MEDICARE_PART_D: "Medicare Part D",
  MEDICARE_ADVANTAGE: "Medicare Advantage",
  MEDICAID_FFS: "Medicaid FFS",
  MEDICAID_MCO: "Medicaid MCO",
  TRICARE: "TRICARE",
  VA: "VA",
  FEP: "FEP",
  IHS: "IHS",
  CHAMPVA: "CHAMPVA",
};

const CONFIDENCE_COLORS: Record<string, string> = {
  HIGH: "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400",
  MEDIUM: "bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400",
  LOW: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-400",
};

const COPAY_STATUS_COLORS: Record<string, string> = {
  ELIGIBLE: "text-green-600",
  BLOCKED: "text-red-600",
  REVIEW: "text-amber-600",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatsCard({
  label,
  value,
  sub,
  icon: Icon,
  iconClass,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  iconClass?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 flex gap-3 items-start">
      <div className={cn("mt-0.5 rounded-md p-2", iconClass ?? "bg-muted")}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xl font-semibold">{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        CONFIDENCE_COLORS[confidence] ?? "bg-muted text-muted-foreground"
      )}
    >
      {confidence}
    </span>
  );
}

function CheckResult({ result }: { result: CopayResult | null }) {
  if (!result) return null;
  const Icon =
    result.status === "ELIGIBLE"
      ? CheckCircle2
      : result.status === "BLOCKED"
      ? XCircle
      : AlertCircle;
  return (
    <div
      className={cn(
        "mt-3 rounded-md border p-3 text-sm",
        result.status === "ELIGIBLE"
          ? "border-green-200 bg-green-50 dark:bg-green-950/20"
          : result.status === "BLOCKED"
          ? "border-red-200 bg-red-50 dark:bg-red-950/20"
          : "border-amber-200 bg-amber-50 dark:bg-amber-950/20"
      )}
    >
      <div className="flex items-center gap-2 font-medium">
        <Icon
          className={cn("h-4 w-4", COPAY_STATUS_COLORS[result.status])}
        />
        <span className={COPAY_STATUS_COLORS[result.status]}>
          {result.status}
        </span>
      </div>
      <p className="mt-1 text-muted-foreground">{result.reason}</p>
      {result.government_check.plans.length > 0 && (
        <div className="mt-2 text-xs">
          <span className="font-medium">Matched plan: </span>
          {result.government_check.plans[0].plan_name ??
            result.government_check.plans[0].plan_type}{" "}
          via {result.government_check.plans[0].pbm_name ?? "—"}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function GovernmentProgramsPage() {
  const queryClient = useQueryClient();

  // Filters
  const [planTypeFilter, setPlanTypeFilter] = useState("");
  const [stateFilter, setStateFilter] = useState("");

  // BIN check tool
  const [checkBin, setCheckBin] = useState("");
  const [checkPcn, setCheckPcn] = useState("");
  const [checkGroup, setCheckGroup] = useState("");
  const [checkResult, setCheckResult] = useState<CopayResult | null>(null);
  const [checking, setChecking] = useState(false);

  // Add/Edit modal
  const [showModal, setShowModal] = useState(false);
  const [editEntry, setEditEntry] = useState<GovernmentBin | null>(null);

  // Delete confirm
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // CSV import
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ---------------------------------------------------------------------------
  // Queries
  // ---------------------------------------------------------------------------

  const { data: report } = useQuery({
    queryKey: ["gov-programs-report"],
    queryFn: () => apiGet<CoverageReport>(`${BASE}/coverage-report`),
  });

  const {
    data: bins,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["gov-programs-bins", planTypeFilter, stateFilter],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "500" });
      if (planTypeFilter) params.set("plan_type", planTypeFilter);
      if (stateFilter) params.set("state", stateFilter);
      return apiGet<GovernmentBin[]>(`${BASE}/bins?${params}`);
    },
  });

  // ---------------------------------------------------------------------------
  // Mutations
  // ---------------------------------------------------------------------------

  const deleteMutation = useMutation({
    mutationFn: (id: string) =>
      fetch(`${BASE}/bins/${id}`, { method: "DELETE" }).then((r) => {
        if (!r.ok) throw new Error("Delete failed");
      }),
    onSuccess: () => {
      toast.success("Entry deleted");
      setDeleteId(null);
      queryClient.invalidateQueries({ queryKey: ["gov-programs-bins"] });
      queryClient.invalidateQueries({ queryKey: ["gov-programs-report"] });
    },
    onError: () => toast.error("Delete failed"),
  });

  const importMutation = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      const r = await fetch(`${BASE}/import`, { method: "POST", body: fd });
      if (!r.ok) throw new Error("Import failed");
      return r.json();
    },
    onSuccess: (data) => {
      toast.success(
        `Import complete: ${data.rows_inserted} inserted, ${data.rows_updated} updated, ${data.rows_errored} errors`
      );
      queryClient.invalidateQueries({ queryKey: ["gov-programs-bins"] });
      queryClient.invalidateQueries({ queryKey: ["gov-programs-report"] });
    },
    onError: () => toast.error("Import failed"),
  });

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  async function handleCheck() {
    if (!checkBin.trim()) return;
    setChecking(true);
    try {
      const params = new URLSearchParams({ bin: checkBin.trim() });
      if (checkPcn.trim()) params.set("pcn", checkPcn.trim());
      if (checkGroup.trim()) params.set("group", checkGroup.trim());
      const result = await apiGet<CopayResult>(
        `${BASE}/copay-eligibility?${params}`
      );
      setCheckResult(result);
    } catch {
      toast.error("Check failed — verify the API is running");
    } finally {
      setChecking(false);
    }
  }

  function handleExportCsv() {
    const rows = bins ?? [];
    const header = [
      "bin",
      "pcn",
      "group_number",
      "plan_type",
      "plan_subtype",
      "pbm_name",
      "plan_name",
      "state",
      "confidence",
      "source",
      "notes",
    ].join(",");
    const body = rows
      .map((r) =>
        [
          r.bin,
          r.pcn ?? "",
          r.group_number ?? "",
          r.plan_type,
          r.plan_subtype ?? "",
          r.pbm_name ?? "",
          r.plan_name ?? "",
          r.state ?? "",
          r.confidence,
          `"${r.source.replace(/"/g, '""')}"`,
          `"${(r.notes ?? "").replace(/"/g, '""')}"`,
        ].join(",")
      )
      .join("\n");
    const blob = new Blob([header + "\n" + body], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "government_program_bins.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <Shield className="h-6 w-6 text-blue-600" />
            Government Programs
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Anti-Kickback Statute BIN/PCN reference table. Copay cards are
            blocked for all government payers.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
            disabled={importMutation.isPending}
          >
            <Upload className="h-4 w-4" />
            {importMutation.isPending ? "Importing..." : "Import CSV"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) importMutation.mutate(file);
              e.target.value = "";
            }}
          />
          <button
            onClick={() => {
              setEditEntry(null);
              setShowModal(true);
            }}
            className="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            Add Entry
          </button>
        </div>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatsCard
          label="Total Entries"
          value={report?.total_entries ?? "—"}
          icon={Shield}
          iconClass="bg-blue-100 text-blue-600"
        />
        <StatsCard
          label="States Covered"
          value={report ? `${report.states_covered}/56` : "—"}
          icon={CheckCircle2}
          iconClass="bg-green-100 text-green-600"
        />
        <StatsCard
          label="MEDIUM Confidence"
          value={report?.medium_confidence_count ?? "—"}
          sub="Require REVIEW"
          icon={AlertCircle}
          iconClass="bg-amber-100 text-amber-600"
        />
        <StatsCard
          label="Plan Types"
          value={report ? Object.keys(report.by_plan_type).length : "—"}
          sub={PLAN_TYPES.map((t) => PLAN_TYPE_LABELS[t]).join(", ")}
          icon={Shield}
          iconClass="bg-purple-100 text-purple-600"
        />
      </div>

      {/* Plan type breakdown */}
      {report && Object.keys(report.by_plan_type).length > 0 && (
        <div className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium mb-3">Entries by Plan Type</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(report.by_plan_type)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => (
                <div
                  key={type}
                  className="rounded-md border px-3 py-1.5 text-xs"
                >
                  <span className="font-medium">
                    {PLAN_TYPE_LABELS[type] ?? type}
                  </span>
                  <span className="ml-1.5 text-muted-foreground">{count}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* BIN Check Tool */}
      <div className="rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium mb-3 flex items-center gap-2">
          <Search className="h-4 w-4" />
          BIN Eligibility Check
        </h2>
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            placeholder="BIN (6 digits)"
            value={checkBin}
            onChange={(e) => setCheckBin(e.target.value)}
            maxLength={6}
            className="rounded-md border px-3 py-1.5 text-sm w-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="PCN (optional)"
            value={checkPcn}
            onChange={(e) => setCheckPcn(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="Group (optional)"
            value={checkGroup}
            onChange={(e) => setCheckGroup(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm w-36 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleCheck}
            disabled={!checkBin.trim() || checking}
            className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {checking ? "Checking..." : "Check"}
          </button>
        </div>
        <CheckResult result={checkResult} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <select
          value={planTypeFilter}
          onChange={(e) => setPlanTypeFilter(e.target.value)}
          className="rounded-md border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All plan types</option>
          {PLAN_TYPES.map((pt) => (
            <option key={pt} value={pt}>
              {PLAN_TYPE_LABELS[pt]}
            </option>
          ))}
        </select>
        <input
          type="text"
          placeholder="State (e.g. CA)"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value.toUpperCase())}
          maxLength={2}
          className="rounded-md border px-3 py-1.5 text-sm w-28 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {(planTypeFilter || stateFilter) && (
          <button
            onClick={() => {
              setPlanTypeFilter("");
              setStateFilter("");
            }}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Clear filters
          </button>
        )}
        <span className="ml-auto text-sm text-muted-foreground">
          {bins ? `${bins.length} entries` : ""}
        </span>
      </div>

      {/* Data table */}
      {isLoading ? (
        <TableSkeleton rows={8} cols={7} />
      ) : isError ? (
        <ErrorFallback
          error={new Error("Failed to load government program BINs")}
          onRetry={() => refetch()}
        />
      ) : !bins || bins.length === 0 ? (
        <EmptyState
          title="No entries found"
          description="No government program BINs match the current filters."
          action={
            <button
              onClick={() => {
                setPlanTypeFilter("");
                setStateFilter("");
              }}
              className="text-sm text-blue-600 hover:underline"
            >
              Clear filters
            </button>
          }
        />
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 border-b">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  BIN
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  PCN
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  Plan Type
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  PBM / Plan
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  State
                </th>
                <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">
                  Confidence
                </th>
                <th className="px-4 py-2.5 text-right font-medium text-muted-foreground">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {bins.map((row) => (
                <tr key={row.id} className="hover:bg-muted/30">
                  <td className="px-4 py-2.5 font-mono font-medium">
                    {row.bin}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-muted-foreground">
                    {row.pcn ?? "—"}
                    {row.group_number && (
                      <span className="ml-1 text-xs text-muted-foreground/70">
                        / {row.group_number}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-xs font-medium">
                      {PLAN_TYPE_LABELS[row.plan_type] ?? row.plan_type}
                    </span>
                    {row.plan_subtype && (
                      <div className="text-xs text-muted-foreground">
                        {row.plan_subtype}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <div>{row.pbm_name ?? "—"}</div>
                    {row.plan_name && (
                      <div className="text-xs text-muted-foreground truncate max-w-[200px]">
                        {row.plan_name}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {row.state ?? <span className="text-muted-foreground">Fed</span>}
                  </td>
                  <td className="px-4 py-2.5">
                    <ConfidenceBadge confidence={row.confidence} />
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex justify-end gap-1">
                      <button
                        onClick={() => {
                          setEditEntry(row);
                          setShowModal(true);
                        }}
                        className="rounded p-1 hover:bg-muted"
                        title="Edit"
                      >
                        <Edit className="h-4 w-4 text-muted-foreground" />
                      </button>
                      <button
                        onClick={() => setDeleteId(row.id)}
                        className="rounded p-1 hover:bg-muted"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="rounded-lg bg-background border p-6 w-full max-w-sm shadow-xl">
            <h3 className="font-semibold text-lg mb-2">Delete entry?</h3>
            <p className="text-sm text-muted-foreground mb-4">
              This action cannot be undone. The BIN entry will be permanently
              removed from the government exclusion table.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteId(null)}
                className="rounded-md border px-4 py-1.5 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(deleteId)}
                disabled={deleteMutation.isPending}
                className="rounded-md bg-red-600 px-4 py-1.5 text-sm text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add/Edit modal */}
      {showModal && (
        <BinModal
          entry={editEntry}
          onClose={() => {
            setShowModal(false);
            setEditEntry(null);
          }}
          onSaved={() => {
            queryClient.invalidateQueries({ queryKey: ["gov-programs-bins"] });
            queryClient.invalidateQueries({ queryKey: ["gov-programs-report"] });
            setShowModal(false);
            setEditEntry(null);
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add/Edit modal
// ---------------------------------------------------------------------------

interface BinModalProps {
  entry: GovernmentBin | null;
  onClose: () => void;
  onSaved: () => void;
}

function BinModal({ entry, onClose, onSaved }: BinModalProps) {
  const isEdit = !!entry;
  const [form, setForm] = useState({
    bin: entry?.bin ?? "",
    pcn: entry?.pcn ?? "",
    group_number: entry?.group_number ?? "",
    plan_type: entry?.plan_type ?? "MEDICARE_PART_D",
    plan_subtype: entry?.plan_subtype ?? "",
    pbm_name: entry?.pbm_name ?? "",
    plan_name: entry?.plan_name ?? "",
    mco_name: entry?.mco_name ?? "",
    state: entry?.state ?? "",
    occ_codes: entry?.occ_codes ?? "",
    confidence: entry?.confidence ?? "HIGH",
    source: entry?.source ?? "",
    notes: entry?.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const body = {
        bin: form.bin.padStart(6, "0"),
        pcn: form.pcn || null,
        group_number: form.group_number || null,
        plan_type: form.plan_type,
        plan_subtype: form.plan_subtype || null,
        pbm_name: form.pbm_name || null,
        plan_name: form.plan_name || null,
        mco_name: form.mco_name || null,
        state: form.state || null,
        occ_codes: form.occ_codes || null,
        confidence: form.confidence,
        source: form.source,
        notes: form.notes || null,
      };
      if (isEdit) {
        await apiPut(`${BASE}/bins/${entry.id}`, body);
        toast.success("Entry updated");
      } else {
        await apiPost(`${BASE}/bins`, body);
        toast.success("Entry added");
      }
      onSaved();
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Save failed — check the form";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  function field(
    label: string,
    key: keyof typeof form,
    opts?: { required?: boolean; placeholder?: string; maxLength?: number }
  ) {
    return (
      <label className="block">
        <span className="text-xs font-medium text-muted-foreground">
          {label}
          {opts?.required && <span className="text-red-500 ml-0.5">*</span>}
        </span>
        <input
          type="text"
          value={form[key]}
          onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={opts?.placeholder}
          maxLength={opts?.maxLength}
          className="mt-1 w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </label>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="rounded-lg bg-background border p-6 w-full max-w-lg shadow-xl overflow-y-auto max-h-[90vh]">
        <h3 className="font-semibold text-lg mb-4">
          {isEdit ? "Edit BIN Entry" : "Add BIN Entry"}
        </h3>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            {field("BIN", "bin", { required: true, placeholder: "003858", maxLength: 6 })}
            {field("PCN", "pcn", { placeholder: "optional" })}
            {field("Group Number", "group_number", { placeholder: "optional" })}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">
                Plan Type<span className="text-red-500 ml-0.5">*</span>
              </span>
              <select
                value={form.plan_type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, plan_type: e.target.value }))
                }
                className="mt-1 w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {PLAN_TYPES.map((pt) => (
                  <option key={pt} value={pt}>
                    {PLAN_TYPE_LABELS[pt]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">
                Confidence
              </span>
              <select
                value={form.confidence}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    confidence: e.target.value as "HIGH" | "MEDIUM" | "LOW",
                  }))
                }
                className="mt-1 w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {field("PBM Name", "pbm_name")}
            {field("MCO Name", "mco_name")}
          </div>
          {field("Plan Name", "plan_name")}
          {field("Plan Subtype", "plan_subtype")}
          <div className="grid grid-cols-2 gap-3">
            {field("State (2-letter)", "state", { maxLength: 2 })}
            {field("OCC Codes (pipe-delimited)", "occ_codes")}
          </div>
          {field("Source", "source", { required: true })}
          <label className="block">
            <span className="text-xs font-medium text-muted-foreground">
              Notes
            </span>
            <textarea
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              rows={2}
              className="mt-1 w-full rounded-md border px-2.5 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </label>
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border px-4 py-1.5 text-sm hover:bg-muted"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Saving..." : isEdit ? "Save changes" : "Add entry"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
