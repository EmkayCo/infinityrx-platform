"use client";

import React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Wizard, useWizard, type WizardStep } from "@shared/components/wizard";
import { DollarDisplay, DollarInput } from "@shared/components/dollar-display";
import { apiGet, apiPatch, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Investigation, EvidenceItem } from "@shared/types/reclaimrx";
import { cn } from "@shared/lib/format";
import { Check, RefreshCw, Eye } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

const STEPS: WizardStep[] = [
  { id: "review", title: "Review Flag", description: "Flag evidence & narrative" },
  { id: "assign", title: "Assign Investigator", description: "Select team member" },
  { id: "evidence", title: "Evidence Collection", description: "Checklist & uploads" },
  { id: "demand", title: "Demand Letter", description: "AI-drafted & editable" },
  { id: "resolution", title: "Resolution", description: "Recovery & closure" },
];

// ── Step 1: Review Flag ───────────────────────────────────────────────────────
function ReviewFlagStep({ investigation }: { investigation: Investigation }) {
  const { flag } = investigation;
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/60 p-5">
        <div className="grid grid-cols-2 gap-4 text-sm mb-4">
          <div>
            <p className="text-slate-400 text-xs mb-1">Entity</p>
            <p className="text-white font-medium">{flag.entity_name}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs mb-1">Flag Type</p>
            <p className="text-white capitalize">{flag.flag_type.replace(/_/g, " ")}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs mb-1">Severity</p>
            <p className="text-white capitalize">{flag.severity}</p>
          </div>
          <div>
            <p className="text-slate-400 text-xs mb-1">Estimated Recovery</p>
            <DollarDisplay amount={investigation.estimated_recovery} size="md" />
          </div>
          <div>
            <p className="text-slate-400 text-xs mb-1">Claims Analyzed</p>
            <p className="text-white">{flag.claim_count}</p>
          </div>
        </div>
        <div>
          <p className="text-slate-400 text-xs mb-2">Anomaly Narrative</p>
          <p className="text-slate-200 text-sm leading-relaxed bg-navy-900/80 rounded p-3 border border-ifx-border-dark">
            {flag.anomaly_narrative || "No narrative available."}
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Step 2: Assign Investigator ───────────────────────────────────────────────
interface Investigator {
  id: string;
  name: string;
  email: string;
  active_cases: number;
  role: string;
}

function AssignInvestigatorStep({
  investigation,
  onUpdate,
}: {
  investigation: Investigation;
  onUpdate: (data: Record<string, unknown>) => void;
}) {
  const [investigators, setInvestigators] = React.useState<Investigator[]>([]);
  const [selected, setSelected] = React.useState(investigation.assigned_to ?? "");

  React.useEffect(() => {
    apiGet<Investigator[]>(buildUrl(`${API_URLS.corePlatform}/api/v1/users`, { role: "fwa_investigator" }))
      .then(setInvestigators)
      .catch(() => {/* graceful degradation */});
  }, []);

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Select the investigator who will own this case.
      </p>
      <div className="space-y-2">
        {investigators.length === 0 && (
          <p className="text-sm text-slate-500 italic">Loading investigators...</p>
        )}
        {investigators.map((inv) => (
          <label
            key={inv.id}
            className={cn(
              "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors",
              selected === inv.id
                ? "border-teal-500/60 bg-teal-900/10"
                : "border-ifx-border-dark hover:border-teal-600/40"
            )}
          >
            <input
              type="radio"
              name="investigator"
              value={inv.id}
              checked={selected === inv.id}
              onChange={() => {
                setSelected(inv.id);
                onUpdate({ investigator_id: inv.id });
              }}
              className="sr-only"
            />
            <div
              className={cn(
                "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                selected === inv.id ? "border-teal-500 bg-teal-500" : "border-slate-500"
              )}
            >
              {selected === inv.id && <span className="w-2 h-2 rounded-full bg-white" />}
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-white">{inv.name}</p>
              <p className="text-xs text-slate-400">
                {inv.role} · {inv.active_cases} active cases
              </p>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}

// ── Step 3: Evidence Collection ───────────────────────────────────────────────
function EvidenceCollectionStep({
  investigation,
  onUpdate,
}: {
  investigation: Investigation;
  onUpdate: (data: Record<string, unknown>) => void;
}) {
  const [items, setItems] = React.useState<EvidenceItem[]>(investigation.evidence_items ?? []);

  function toggle(id: string) {
    const updated = items.map((item) =>
      item.id === id ? { ...item, completed: !item.completed } : item
    );
    setItems(updated);
    onUpdate({ evidence_items: updated });
  }

  const done = items.filter((i) => i.completed).length;
  const required = items.filter((i) => i.required);
  const requiredDone = required.filter((i) => i.completed).length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400">
          {done} / {items.length} completed
        </span>
        <span className={cn("text-xs", requiredDone === required.length ? "text-green-400" : "text-yellow-400")}>
          {requiredDone}/{required.length} required
        </span>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-slate-500 italic">No evidence items configured for this investigation type.</p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-3 p-3 rounded-lg border border-ifx-border-dark hover:bg-navy-700/20 transition-colors"
            >
              <button
                onClick={() => toggle(item.id)}
                className={cn(
                  "flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors mt-0.5",
                  item.completed
                    ? "bg-teal-500 border-teal-500"
                    : "border-slate-500 hover:border-teal-500"
                )}
              >
                {item.completed && <Check className="w-3 h-3 text-white" />}
              </button>
              <div className="flex-1">
                <p className={cn("text-sm", item.completed ? "line-through text-slate-500" : "text-white")}>
                  {item.label}
                  {item.required && <span className="text-red-400 ml-1">*</span>}
                </p>
                {item.description && (
                  <p className="text-xs text-slate-500 mt-0.5">{item.description}</p>
                )}
              </div>
              {item.file_url && (
                <a
                  href={item.file_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-teal-400 hover:text-teal-300"
                >
                  <Eye className="w-4 h-4" />
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Step 4: Generate Demand Letter ────────────────────────────────────────────
function GenerateDemandLetterStep({
  investigation,
  onUpdate,
}: {
  investigation: Investigation;
  onUpdate: (data: Record<string, unknown>) => void;
}) {
  const [letter, setLetter] = React.useState(investigation.demand_letter ?? "");
  const [isRegenerating, setIsRegenerating] = React.useState(false);
  const [showPreview, setShowPreview] = React.useState(false);

  React.useEffect(() => {
    if (!investigation.demand_letter) {
      setIsRegenerating(true);
      apiPost<{ letter: string }>(
        `${API_URLS.reclaimrx}/api/v1/investigations/${investigation.id}/generate-demand-letter`,
        {}
      )
        .then((res) => {
          setLetter(res.letter);
          onUpdate({ demand_letter: res.letter });
        })
        .catch(() => {/* no-op */})
        .finally(() => setIsRegenerating(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [investigation.id]);

  async function regenerate() {
    setIsRegenerating(true);
    try {
      const res = await apiPost<{ letter: string }>(
        `${API_URLS.reclaimrx}/api/v1/investigations/${investigation.id}/generate-demand-letter`,
        { regenerate: true }
      );
      setLetter(res.letter);
      onUpdate({ demand_letter: res.letter });
    } catch { /* no-op */ }
    finally { setIsRegenerating(false); }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-400">
          AI-drafted demand letter. Edit as needed.
        </p>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
          >
            <Eye className="w-3.5 h-3.5" />
            {showPreview ? "Edit" : "Preview"}
          </button>
          <button
            onClick={() => void regenerate()}
            disabled={isRegenerating}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-teal-600/40 text-teal-400 hover:bg-teal-900/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isRegenerating && "animate-spin")} />
            Regenerate
          </button>
        </div>
      </div>

      {showPreview ? (
        <div className="rounded-lg border border-ifx-border-dark bg-white/5 p-5 text-sm text-slate-200 whitespace-pre-wrap leading-relaxed min-h-64">
          {letter || "No letter content."}
        </div>
      ) : (
        <textarea
          value={isRegenerating ? "Generating..." : letter}
          onChange={(e) => {
            setLetter(e.target.value);
            onUpdate({ demand_letter: e.target.value });
          }}
          disabled={isRegenerating}
          rows={16}
          className="w-full rounded-lg border border-ifx-border-dark bg-navy-900/60 text-slate-200 text-sm p-4 resize-y focus:outline-none focus:ring-2 focus:ring-teal-500/40 font-mono disabled:opacity-50"
          placeholder="Generating demand letter..."
        />
      )}
    </div>
  );
}

// ── Step 5: Resolution ────────────────────────────────────────────────────────
const resolutionSchema = z.object({
  collected_amount: z.string().min(1, "Enter recovery amount"),
  corrective_action_plan: z.string().min(10, "Describe corrective action plan"),
});

type ResolutionForm = z.infer<typeof resolutionSchema>;

function ResolutionStep({
  investigation,
  onUpdate,
}: {
  investigation: Investigation;
  onUpdate: (data: Record<string, unknown>) => void;
}) {
  const {
    register,
    formState: { errors },
    watch,
    setValue,
  } = useForm<ResolutionForm>({
    resolver: zodResolver(resolutionSchema),
    defaultValues: {
      collected_amount: investigation.collected_amount ?? "",
      corrective_action_plan: investigation.corrective_action_plan ?? "",
    },
  });

  const watchedAmount = watch("collected_amount");
  React.useEffect(() => {
    onUpdate({ collected_amount: watchedAmount });
  }, [watchedAmount, onUpdate]);

  const watchedPlan = watch("corrective_action_plan");
  React.useEffect(() => {
    onUpdate({ corrective_action_plan: watchedPlan });
  }, [watchedPlan, onUpdate]);

  return (
    <div className="space-y-5">
      <div>
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Recovery Amount Collected
        </label>
        <DollarInput
          value={watchedAmount}
          onChange={(v) => setValue("collected_amount", v)}
          placeholder="0.00"
        />
        {errors.collected_amount && (
          <p className="text-xs text-red-400 mt-1">{errors.collected_amount.message}</p>
        )}
        <p className="text-xs text-slate-500 mt-1">
          Estimated: <DollarDisplay amount={investigation.estimated_recovery} size="sm" showScale={false} />
          {investigation.demanded_amount && (
            <> · Demanded: <DollarDisplay amount={investigation.demanded_amount} size="sm" showScale={false} /></>
          )}
        </p>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-300 mb-2">
          Corrective Action Plan
        </label>
        <textarea
          {...register("corrective_action_plan")}
          rows={6}
          className="w-full rounded-lg border border-ifx-border-dark bg-navy-900/60 text-slate-200 text-sm p-3 resize-y focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          placeholder="Describe the corrective actions taken or required..."
        />
        {errors.corrective_action_plan && (
          <p className="text-xs text-red-400 mt-1">{errors.corrective_action_plan.message}</p>
        )}
      </div>

      <div className="rounded-lg border border-teal-600/20 bg-teal-900/10 p-4">
        <p className="text-sm text-teal-300 font-medium mb-1">Case Closure Summary</p>
        <p className="text-xs text-slate-400">
          Submitting this step will mark the investigation as{" "}
          <span className="text-green-400 font-medium">Resolved</span> and close the case.
        </p>
      </div>
    </div>
  );
}

// ── Main Wizard Component ────────────────────────────────────────────────────
interface InvestigationWizardProps {
  investigation: Investigation;
  onClose?: () => void;
  onComplete?: () => void;
}

export function InvestigationWizard({
  investigation,
  onClose,
  onComplete,
}: InvestigationWizardProps) {
  const queryClient = useQueryClient();
  const { currentStep, setStep, data, updateData, isLastStep } = useWizard(
    STEPS.length,
    `investigation_${investigation.id}`
  );
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  async function handleNext(): Promise<boolean> {
    if (isLastStep) {
      setIsSubmitting(true);
      try {
        await apiPatch(
          `${API_URLS.reclaimrx}/api/v1/investigations/${investigation.id}/resolve`,
          {
            collected_amount: data.collected_amount,
            corrective_action_plan: data.corrective_action_plan,
            demand_letter: data.demand_letter,
          }
        );
        void queryClient.invalidateQueries({ queryKey: ["investigations"] });
        void queryClient.invalidateQueries({ queryKey: ["investigation", investigation.id] });
        onComplete?.();
        return true;
      } catch {
        return false;
      } finally {
        setIsSubmitting(false);
      }
    }

    // Save intermediate steps
    if (currentStep === 1 && data.investigator_id) {
      try {
        await apiPatch(
          `${API_URLS.reclaimrx}/api/v1/investigations/${investigation.id}`,
          { assigned_to: data.investigator_id }
        );
      } catch { /* non-blocking */ }
    }
    return true;
  }

  const stepContent = [
    <ReviewFlagStep key="review" investigation={investigation} />,
    <AssignInvestigatorStep key="assign" investigation={investigation} onUpdate={updateData} />,
    <EvidenceCollectionStep key="evidence" investigation={investigation} onUpdate={updateData} />,
    <GenerateDemandLetterStep key="demand" investigation={investigation} onUpdate={updateData} />,
    <ResolutionStep key="resolution" investigation={investigation} onUpdate={updateData} />,
  ];

  return (
    <Wizard
      steps={STEPS}
      currentStep={currentStep}
      onStepChange={setStep}
      onClose={onClose}
      title={`Investigation: ${investigation.flag.entity_name}`}
      onNext={handleNext}
      onSaveDraft={() => updateData({})}
      isSubmitting={isSubmitting}
      isLastStep={isLastStep}
      nextLabel={isLastStep ? "Close Case" : undefined}
    >
      {stepContent[currentStep]}
    </Wizard>
  );
}
