"use client";

// Config change-set workflow — Wave 28 Sub-wave 6.
//
// Operator UI for the Wave 27 SW3 admin endpoints. Flow:
//   1. Operator pastes the change_set_id (UUID from program_config's
//      draft → approved workflow).
//   2. Simulate runs recent claims through PRE-F harness at the
//      change set's effective_date and returns per-claim diffs.
//   3. Inspect flipped claims (PASS↔REJECT) + reject-code changes.
//   4. Apply promotes status approved → applied and terminates the
//      predecessor parameter rows at the change set's scope.
//
// Read-only until Apply; Apply is guarded by change_set_status ==
// "approved" on both client and server.

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowLeft,
  CheckCircle2,
  FlaskConical,
  Loader2,
  PlayCircle,
  ShieldAlert,
  Settings,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  applyChangeSet,
  simulateChangeSet,
  type ClaimDiff,
  type SimulateChangeSetResponse,
} from "@shared/lib/config-api";


function isUuidLike(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
    .test(s.trim());
}


export default function ChangeSetWorkflowPage() {
  const [changeSetId, setChangeSetId] = useState("");
  const [sampleSize, setSampleSize] = useState(100);
  const [daysBack, setDaysBack] = useState(30);

  const [simulating, setSimulating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [result, setResult] = useState<SimulateChangeSetResponse | null>(null);

  async function handleSimulate() {
    if (!isUuidLike(changeSetId)) {
      toast.error("change_set_id must be a UUID (8-4-4-4-12 hex).");
      return;
    }
    setSimulating(true);
    try {
      const resp = await simulateChangeSet({
        change_set_id: changeSetId.trim(),
        sample_size: sampleSize,
        days_back: daysBack,
      });
      setResult(resp);
      toast.success(
        `Evaluated ${resp.scenarios_evaluated} scenarios, ` +
        `${resp.flipped_count} flipped.`,
      );
    } catch (e) {
      const msg = e instanceof ApiClientError
        ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Simulate failed — ${msg}`);
    } finally {
      setSimulating(false);
    }
  }

  async function handleApply() {
    if (!result || result.change_set_status !== "approved") {
      toast.error(
        "Apply is only allowed on change sets in 'approved' status.",
      );
      return;
    }
    if (!confirm(
      "Applying this change set will TERMINATE predecessor parameter " +
      "rows at its scope and activate the new config at " +
      `${result.change_set_effective_date}. This cannot be undone — ` +
      "continue?",
    )) return;

    setApplying(true);
    try {
      const resp = await applyChangeSet({ change_set_id: changeSetId.trim() });
      toast.success(
        `Change set applied. ${resp.rows_terminated} predecessor ` +
        `row(s) terminated; new status: ${resp.new_status}.`,
      );
      // Reflect the new status in the local state so the Apply
      // button disables without a refetch.
      setResult({ ...result, change_set_status: resp.new_status });
    } catch (e) {
      const msg = e instanceof ApiClientError
        ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Apply failed — ${msg}`);
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/config"
          className="hover:text-foreground inline-flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" /> Configuration
        </Link>
        <span>/</span>
        <span className="text-foreground">Change-set workflow</span>
      </div>

      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-md bg-teal-500/10 p-2">
          <Settings className="h-5 w-5 text-teal-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Change-set workflow</h1>
          <p className="text-sm text-muted-foreground">
            Simulate a staged config change against recent claims before
            applying it. Flipped outcomes flag for review.
          </p>
        </div>
      </div>

      <section className="mb-6 rounded-lg border bg-card">
        <header className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">Inputs</h2>
        </header>
        <div className="grid gap-4 p-4 md:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs md:col-span-3">
            <span className="font-medium">Change set ID (UUID)</span>
            <input
              type="text" value={changeSetId}
              onChange={(e) => setChangeSetId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              className="rounded-md border bg-background px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">Sample size</span>
            <input
              type="number" min={1} max={10000} value={sampleSize}
              onChange={(e) => setSampleSize(Number(e.target.value))}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            />
            <span className="text-muted-foreground">
              Max 10,000 recent claims
            </span>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium">Days back</span>
            <input
              type="number" min={1} max={365} value={daysBack}
              onChange={(e) => setDaysBack(Number(e.target.value))}
              className="rounded-md border bg-background px-3 py-2 text-sm"
            />
            <span className="text-muted-foreground">
              Claims with DOS in last N days
            </span>
          </label>
          <div className="flex items-end">
            <button
              onClick={handleSimulate} disabled={simulating}
              className="inline-flex items-center gap-2 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:bg-teal-500/50"
            >
              {simulating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FlaskConical className="h-4 w-4" />
              )}
              {simulating ? "Simulating…" : "Simulate"}
            </button>
          </div>
        </div>
      </section>

      {result && (
        <>
          <section className="mb-6 rounded-lg border bg-card">
            <header className="flex items-center justify-between border-b px-4 py-3">
              <h2 className="text-sm font-semibold">Summary</h2>
              <StatusBadge status={result.change_set_status} />
            </header>
            <div className="grid grid-cols-2 gap-4 p-4 md:grid-cols-4">
              <Stat label="Effective date"
                value={result.change_set_effective_date} mono />
              <Stat label="Scenarios evaluated"
                value={String(result.scenarios_evaluated)} />
              <Stat label="Flipped"
                value={String(result.flipped_count)}
                tone={result.flipped_count > 0 ? "warn" : "ok"} />
              <Stat label="Unchanged"
                value={String(
                  result.scenarios_evaluated - result.flipped_count,
                )} />
            </div>

            {result.change_set_status === "approved" && (
              <div className="flex items-center justify-between border-t bg-amber-500/5 px-4 py-3">
                <div className="flex items-center gap-2 text-sm">
                  <ShieldAlert className="h-4 w-4 text-amber-500" />
                  <span>
                    Status is <span className="font-mono">approved</span>.
                    Applying is atomic and irreversible.
                  </span>
                </div>
                <button
                  onClick={handleApply} disabled={applying}
                  className="inline-flex items-center gap-2 rounded-md bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:bg-amber-600/50"
                >
                  {applying ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <PlayCircle className="h-4 w-4" />
                  )}
                  {applying ? "Applying…" : "Apply change set"}
                </button>
              </div>
            )}

            {result.change_set_status === "applied" && (
              <div className="flex items-center gap-2 border-t bg-emerald-500/5 px-4 py-3 text-sm">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                <span>Change set applied.</span>
              </div>
            )}
          </section>

          <FindingsTable findings={result.findings} />
        </>
      )}

      {!result && (
        <div className="rounded-lg border border-dashed bg-card/40 p-8 text-center text-sm text-muted-foreground">
          Enter a change set ID and click Simulate to compare recent
          claim outcomes under current vs. staged configuration.
        </div>
      )}
    </div>
  );
}


function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "applied" ? "bg-emerald-500/10 text-emerald-500" :
    status === "approved" ? "bg-amber-500/10 text-amber-600" :
    status === "draft" ? "bg-slate-500/10 text-slate-500" :
    "bg-muted text-muted-foreground";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      {status}
    </span>
  );
}


function Stat({
  label, value, tone, mono,
}: {
  label: string;
  value: string;
  tone?: "ok" | "warn";
  mono?: boolean;
}) {
  const valueClass =
    tone === "warn" ? "text-amber-600" :
    tone === "ok"   ? "text-emerald-500" : "";
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={`mt-0.5 text-lg font-medium ${valueClass} ${mono ? "font-mono" : ""}`}>
        {value}
      </p>
    </div>
  );
}


function FindingsTable({ findings }: { findings: ClaimDiff[] }) {
  if (findings.length === 0) {
    return (
      <section className="rounded-lg border bg-card">
        <header className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">Findings</h2>
        </header>
        <div className="p-8 text-center text-sm text-muted-foreground">
          No scenarios evaluated. Either no recent claims match the
          filter or the change set hasn't been configured.
        </div>
      </section>
    );
  }

  const flipped = findings.filter((f) => f.flipped);
  const changed = findings.filter((f) => !f.flipped && f.diff_keys.length > 0);
  const unchanged = findings.filter((f) => f.diff_keys.length === 0);

  return (
    <section className="rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">Findings</h2>
        <span className="text-xs text-muted-foreground">
          {flipped.length} flipped · {changed.length} changed · {unchanged.length} unchanged
        </span>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left">Claim</th>
              <th className="px-4 py-2 text-left">Current</th>
              <th className="px-4 py-2 text-left">Future</th>
              <th className="px-4 py-2 text-left">Diff</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {[...flipped, ...changed, ...unchanged].map((f) => (
              <tr
                key={f.claim_id}
                className={
                  f.flipped ? "bg-rose-500/5" :
                  f.diff_keys.length > 0 ? "bg-amber-500/5" : ""
                }
              >
                <td className="px-4 py-2 font-mono text-xs">
                  {f.claim_id.slice(0, 8)}…
                </td>
                <td className="px-4 py-2">
                  <OutcomeCell outcome={f.current_outcome}
                    code={f.current_reject_code} />
                </td>
                <td className="px-4 py-2">
                  <OutcomeCell outcome={f.future_outcome}
                    code={f.future_reject_code} />
                </td>
                <td className="px-4 py-2 text-xs">
                  {f.diff_keys.length === 0 ? (
                    <span className="text-muted-foreground">—</span>
                  ) : (
                    <span className="font-mono">
                      {f.diff_keys.join(", ")}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}


function OutcomeCell({
  outcome, code,
}: {
  outcome: "PASS" | "REJECT";
  code: string | null;
}) {
  if (outcome === "PASS") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-500">
        PASS
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-xs font-medium text-rose-500">
      REJECT{code ? ` · ${code}` : ""}
    </span>
  );
}
