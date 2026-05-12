"use client";

// Cycle close wizard — Wave 40 M1.
//
// Five-step wizard:
//   1. Pre-flight summary
//   2. Options (invoice cycles to close, override pending manual AP)
//   3. Review and confirm
//   4. In-progress with live step status
//   5. Result (success or failure with retry)
//
// Step status polled every 2s while the run is in_progress.

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import {
  ArrowLeft, ArrowRight, CheckCircle2, Loader2, PlayCircle,
  XCircle, AlertTriangle,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getCycle, listCycles, listManualAp,
  closeCycle, getCloseStatus,
  type Cycle, type CycleCloseRun, type CloseStepStatus,
} from "@shared/lib/paysync-api";

import { CycleStatusBadge } from "@/components/paysync/cycle-status-badge";
import { StatusTimeline, type TimelineStep } from "@/components/paysync/status-timeline";

interface PageParams { cycleId: string; }

const STEP_LABELS: Record<string, string> = {
  preflight: "Pre-flight",
  hold_detection: "Hold detection",
  manual_ap_recognition: "Manual AP recognition",
  carryover_ingestion: "Carryover ingestion",
  batch_generation: "Batch generation",
  nacha_generation: "NACHA generation",
  eight_thirty_five_generation: "835 generation",
  invoice_generation: "Invoice generation",
  reconciliation: "Reconciliation",
  finalization: "Finalization",
};

export default function CycleCloseWizardPage(
  { params }: { params: Promise<PageParams> },
) {
  const { cycleId } = use(params);
  const router = useRouter();

  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [openInvoiceCycles, setOpenInvoiceCycles] = useState<Cycle[]>([]);
  const [pendingManualApCount, setPendingManualApCount] = useState(0);

  const [selectedInvoiceCycleIds, setSelectedInvoiceCycleIds] = useState<string[]>([]);
  const [overridePendingManualAp, setOverridePendingManualAp] = useState(false);

  const [run, setRun] = useState<CycleCloseRun | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // Initial load
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getCycle(cycleId),
      listCycles({ cycle_type: "invoice_cycle", status: "open", page: 1, page_size: 50 }),
      listManualAp({ status: "pending", page: 1, page_size: 1 }),
      getCloseStatus(cycleId),
    ]).then(([c, invs, ap, existing]) => {
      if (cancelled) return;
      setCycle(c);
      setOpenInvoiceCycles(invs.items);
      setPendingManualApCount(ap.total);
      if (existing && existing.status === "in_progress") {
        setRun(existing);
        setStep(4);
      }
    }).catch((e: unknown) => {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Pre-flight load failed — ${msg}`);
    });
    return () => { cancelled = true; };
  }, [cycleId]);

  // Poll while running
  useEffect(() => {
    if (step !== 4 || !run || run.status !== "in_progress") return;
    const id = setInterval(async () => {
      try {
        const updated = await getCloseStatus(cycleId);
        if (updated) {
          setRun(updated);
          if (updated.status !== "in_progress") {
            clearInterval(id);
            setStep(5);
          }
        }
      } catch (e) {
        // poll failures are transient — surface only on stop
      }
    }, 2000);
    return () => clearInterval(id);
  }, [step, run, cycleId]);

  if (!cycle) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading cycle…
      </div>
    );
  }

  async function handleStart() {
    setSubmitting(true);
    try {
      const started = await closeCycle(cycleId, {
        invoice_cycle_ids: selectedInvoiceCycleIds.length > 0 ? selectedInvoiceCycleIds : undefined,
        override_pending_manual_ap: overridePendingManualAp,
      });
      setRun(started);
      setStep(4);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Cycle close failed to start — ${msg}`);
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href={`/admin/paysync/cycles/${cycleId}`}
              className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Cycle
        </Link>
        <span>/</span>
        <span className="text-foreground">Run close</span>
      </div>

      <header className="mb-6">
        <h1 className="text-2xl font-bold">Run cycle close</h1>
        <p className="text-sm text-muted-foreground">
          {cycle.cycle_label} · <CycleStatusBadge status={cycle.status} />
        </p>
      </header>

      <StepIndicator current={step} />

      <div className="mt-6 rounded-lg border bg-card p-6">
        {step === 1 && (
          <PreflightStep
            cycle={cycle}
            pendingManualApCount={pendingManualApCount}
            onNext={() => setStep(2)}
          />
        )}
        {step === 2 && (
          <OptionsStep
            cycle={cycle}
            openInvoiceCycles={openInvoiceCycles}
            selectedInvoiceCycleIds={selectedInvoiceCycleIds}
            setSelectedInvoiceCycleIds={setSelectedInvoiceCycleIds}
            pendingManualApCount={pendingManualApCount}
            overridePendingManualAp={overridePendingManualAp}
            setOverridePendingManualAp={setOverridePendingManualAp}
            onBack={() => setStep(1)}
            onNext={() => setStep(3)}
          />
        )}
        {step === 3 && (
          <ReviewStep
            cycle={cycle}
            selectedInvoiceCycleIds={selectedInvoiceCycleIds}
            openInvoiceCycles={openInvoiceCycles}
            overridePendingManualAp={overridePendingManualAp}
            pendingManualApCount={pendingManualApCount}
            submitting={submitting}
            onBack={() => setStep(2)}
            onConfirm={handleStart}
          />
        )}
        {step === 4 && run && (
          <RunningStep run={run} />
        )}
        {step === 5 && run && (
          <ResultStep
            run={run}
            cycleId={cycleId}
            onRetry={() => { setRun(null); setStep(3); }}
            onDone={() => router.push(`/admin/paysync/cycles/${cycleId}`)}
          />
        )}
      </div>
    </div>
  );
}

function StepIndicator({ current }: { current: number }) {
  const steps = ["Pre-flight", "Options", "Review", "Run", "Result"];
  return (
    <ol className="flex items-center gap-2">
      {steps.map((s, idx) => {
        const n = idx + 1;
        const state = n < current ? "done" : n === current ? "current" : "pending";
        return (
          <li key={s} className="flex items-center gap-2">
            <span className={
              "flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold " + (
                state === "done" ? "bg-emerald-500 text-white" :
                state === "current" ? "bg-amber-500 text-white" :
                "border bg-background text-muted-foreground"
              )
            }>
              {n}
            </span>
            <span className={state === "current" ? "text-sm font-medium" : "text-sm text-muted-foreground"}>
              {s}
            </span>
            {n < steps.length && <span className="h-px w-6 bg-border" />}
          </li>
        );
      })}
    </ol>
  );
}

// ─── Step 1 ─────────────────────────────────────────────────────

function PreflightStep({
  cycle, pendingManualApCount, onNext,
}: {
  cycle: Cycle;
  pendingManualApCount: number;
  onNext: () => void;
}) {
  return (
    <>
      <h2 className="mb-3 text-base font-semibold">Pre-flight summary</h2>
      <p className="mb-4 text-sm text-muted-foreground">
        Review the cycle inventory before running close. Cycle close runs
        a 10-step pipeline (preflight → holds → manual AP → carryovers →
        batch → NACHA → 835 → invoices → reconciliation → finalization).
      </p>
      <dl className="mb-6 grid grid-cols-2 gap-4 text-sm">
        <Stat label="Cycle period" value={`${cycle.period_start} → ${cycle.period_end}`} />
        <Stat label="Status" value={cycle.status} />
        <Stat label="Claims in cycle" value={cycle.claim_count.toLocaleString()} />
        <Stat label="Total pay" value={`$${Number(cycle.total_pay).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
        <Stat label="Pending manual AP (tenant-wide)"
              value={pendingManualApCount.toLocaleString()}
              tone={pendingManualApCount > 0 ? "warn" : "ok"} />
      </dl>
      <div className="flex justify-end">
        <button onClick={onNext}
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600">
          Continue <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </>
  );
}

// ─── Step 2 ─────────────────────────────────────────────────────

function OptionsStep({
  cycle, openInvoiceCycles, selectedInvoiceCycleIds, setSelectedInvoiceCycleIds,
  pendingManualApCount, overridePendingManualAp, setOverridePendingManualAp,
  onBack, onNext,
}: {
  cycle: Cycle;
  openInvoiceCycles: Cycle[];
  selectedInvoiceCycleIds: string[];
  setSelectedInvoiceCycleIds: (ids: string[]) => void;
  pendingManualApCount: number;
  overridePendingManualAp: boolean;
  setOverridePendingManualAp: (b: boolean) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  function toggle(id: string) {
    if (selectedInvoiceCycleIds.includes(id)) {
      setSelectedInvoiceCycleIds(selectedInvoiceCycleIds.filter(x => x !== id));
    } else {
      setSelectedInvoiceCycleIds([...selectedInvoiceCycleIds, id]);
    }
  }

  return (
    <>
      <h2 className="mb-3 text-base font-semibold">Options</h2>

      {cycle.cycle_type === "payment_cycle" && (
        <section className="mb-6">
          <h3 className="mb-2 text-sm font-medium">Invoice cycles to close alongside</h3>
          <p className="mb-3 text-xs text-muted-foreground">
            Closing payment + invoice cycles in the same run keeps three-way
            reconciliation against a consistent claim set.
          </p>
          {openInvoiceCycles.length === 0 ? (
            <p className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
              No open invoice cycles available.
            </p>
          ) : (
            <ul className="space-y-1 rounded-md border bg-background p-2">
              {openInvoiceCycles.map((c) => (
                <li key={c.id}>
                  <label className="flex items-center gap-2 rounded-md p-2 text-sm hover:bg-muted/30">
                    <input
                      type="checkbox"
                      checked={selectedInvoiceCycleIds.includes(c.id)}
                      onChange={() => toggle(c.id)}
                    />
                    <span className="font-mono">{c.cycle_label}</span>
                    <span className="text-xs text-muted-foreground">
                      {c.period_start} → {c.period_end}
                    </span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {pendingManualApCount > 0 && (
        <section className="mb-6 rounded-md border border-amber-500/50 bg-amber-500/5 p-3">
          <div className="mb-2 flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="font-medium">Pending manual AP records detected</p>
              <p className="text-xs text-muted-foreground">
                {pendingManualApCount} pending manual AP record(s) in the
                tenant. By default cycle close blocks until they are
                recognized or voided.
              </p>
            </div>
          </div>
          <label className="ml-6 flex items-center gap-2 text-sm">
            <input type="checkbox"
                   checked={overridePendingManualAp}
                   onChange={(e) => setOverridePendingManualAp(e.target.checked)} />
            <span>Override and proceed anyway</span>
          </label>
        </section>
      )}

      <div className="flex items-center justify-between">
        <button onClick={onBack}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          ← Back
        </button>
        <button onClick={onNext}
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-500 px-4 py-2 text-sm font-medium text-white hover:bg-teal-600">
          Continue <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </>
  );
}

// ─── Step 3 ─────────────────────────────────────────────────────

function ReviewStep({
  cycle, selectedInvoiceCycleIds, openInvoiceCycles,
  overridePendingManualAp, pendingManualApCount,
  submitting, onBack, onConfirm,
}: {
  cycle: Cycle;
  selectedInvoiceCycleIds: string[];
  openInvoiceCycles: Cycle[];
  overridePendingManualAp: boolean;
  pendingManualApCount: number;
  submitting: boolean;
  onBack: () => void;
  onConfirm: () => void;
}) {
  const selectedCycles = openInvoiceCycles.filter(c => selectedInvoiceCycleIds.includes(c.id));
  return (
    <>
      <h2 className="mb-3 text-base font-semibold">Review and confirm</h2>
      <dl className="mb-6 space-y-2 text-sm">
        <Stat label="Cycle" value={cycle.cycle_label} />
        <Stat label="Period" value={`${cycle.period_start} → ${cycle.period_end}`} />
        <Stat label="Claims" value={cycle.claim_count.toLocaleString()} />
        <Stat label="Linked invoice cycles"
              value={selectedCycles.length === 0 ? "none"
                : selectedCycles.map(c => c.cycle_label).join(", ")} />
        <Stat label="Override pending manual AP"
              value={overridePendingManualAp ? `yes (${pendingManualApCount} skipped)` : "no"} />
      </dl>
      <div className="rounded-md border border-amber-500/50 bg-amber-500/5 p-3 text-xs">
        <p className="font-medium">Cycle close is irreversible once finalized.</p>
        <p className="mt-1 text-muted-foreground">
          Mid-pipeline failures roll back to the failed step; you can resume
          or fail-back to a known-good state. After finalization, only a
          rollback (separate flow) can re-open a closed cycle.
        </p>
      </div>
      <div className="mt-6 flex items-center justify-between">
        <button onClick={onBack} disabled={submitting}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
          ← Back
        </button>
        <button onClick={onConfirm} disabled={submitting}
                className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
          {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      : <PlayCircle className="h-3.5 w-3.5" />}
          {submitting ? "Starting…" : "Start cycle close"}
        </button>
      </div>
    </>
  );
}

// ─── Step 4 ─────────────────────────────────────────────────────

function RunningStep({ run }: { run: CycleCloseRun }) {
  const orderedNames: string[] = [
    "preflight", "hold_detection", "manual_ap_recognition", "carryover_ingestion",
    "batch_generation", "nacha_generation", "eight_thirty_five_generation",
    "invoice_generation", "reconciliation", "finalization",
  ];
  const byName = new Map<string, CloseStepStatus>(run.step_status.map(s => [s.name, s]));

  const steps: TimelineStep[] = orderedNames.map((name) => {
    const s = byName.get(name);
    const state = !s ? "pending" :
      s.state === "succeeded" ? "completed" :
      s.state === "failed" ? "failed" :
      s.state === "skipped" ? "skipped" :
      s.state === "running" ? "current" :
      "pending";
    return {
      id: name,
      label: STEP_LABELS[name] ?? name,
      state,
      occurredAt: s?.finished_at ?? s?.started_at ?? null,
      description: s?.error_message ?? undefined,
    };
  });

  return (
    <>
      <h2 className="mb-3 text-base font-semibold">Cycle close in progress</h2>
      <p className="mb-6 text-sm text-muted-foreground">
        Pipeline running. This page polls every 2 seconds. You can leave
        and check progress in the cycle detail view.
      </p>
      <StatusTimeline steps={steps} />
    </>
  );
}

// ─── Step 5 ─────────────────────────────────────────────────────

function ResultStep({
  run, cycleId, onRetry, onDone,
}: {
  run: CycleCloseRun;
  cycleId: string;
  onRetry: () => void;
  onDone: () => void;
}) {
  const succeeded = run.status === "succeeded";

  return (
    <>
      <div className="mb-4 flex items-start gap-3">
        {succeeded
          ? <CheckCircle2 className="h-6 w-6 shrink-0 text-emerald-500" />
          : <XCircle className="h-6 w-6 shrink-0 text-rose-500" />}
        <div>
          <h2 className="text-base font-semibold">
            {succeeded ? "Cycle close succeeded" : "Cycle close failed"}
          </h2>
          <p className="text-sm text-muted-foreground">
            {succeeded
              ? "All 10 steps completed. Reconciliation and files are ready in the cycle detail view."
              : run.error_message ?? "One or more steps failed. Review the timeline and retry, or contact support."}
          </p>
        </div>
      </div>

      <RunningStep run={run} />

      <div className="mt-6 flex items-center justify-between">
        <button onClick={onDone}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          Open cycle detail
        </button>
        {!succeeded && (
          <button onClick={onRetry}
                  className="rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600">
            Retry from review
          </button>
        )}
        {succeeded && (
          <Link href={`/admin/paysync/cycles/${cycleId}/close-report`}
                className="rounded-md bg-teal-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-600">
            View close report
          </Link>
        )}
      </div>
    </>
  );
}

// ─── Local helpers ────────────────────────────────────────────

function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warn" }) {
  const valueClass =
    tone === "warn" ? "text-amber-600" :
    tone === "ok"   ? "text-emerald-500" : "";
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className={`mt-0.5 text-sm font-medium ${valueClass}`}>{value}</p>
    </div>
  );
}
