"use client";

import React, { useCallback } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Wizard, useWizard, type WizardStep } from "@shared/components/wizard";
import { apiGet, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ReportTemplate, ReportParameter, ReportFormat, ScheduleFrequency } from "@shared/types/reporting";
import { cn, formatDate } from "@shared/lib/format";
import { FileText, Clock, Download } from "lucide-react";
import { useRouter } from "next/navigation";

const STEPS: WizardStep[] = [
  { id: "select", title: "Select Template", description: "Choose report type" },
  { id: "configure", title: "Configure", description: "Set parameters" },
  { id: "preview", title: "Preview", description: "Review first page" },
  { id: "deliver", title: "Deliver", description: "Download or schedule" },
  { id: "confirm", title: "Confirm", description: "Summary & submit" },
];

// ── Step 1: Select Template ───────────────────────────────────────────────────
function SelectTemplateStep({
  selectedId,
  onSelect,
}: {
  selectedId?: string;
  onSelect: (template: ReportTemplate) => void;
}) {
  const [templates, setTemplates] = React.useState<ReportTemplate[]>([]);
  const [categoryFilter, setCategoryFilter] = React.useState<string>("all");

  React.useEffect(() => {
    apiGet<ReportTemplate[]>(buildUrl(`${API_URLS.reporting}/api/v1/reports/templates`))
      .then(setTemplates)
      .catch(() => {/* graceful */});
  }, []);

  const categories = ["all", ...Array.from(new Set(templates.map((t) => t.category)))];
  const filtered = templates.filter(
    (t) => categoryFilter === "all" || t.category === categoryFilter
  );

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {categories.map((c) => (
          <button
            key={c}
            onClick={() => setCategoryFilter(c)}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize",
              categoryFilter === c
                ? "bg-teal-900/30 border border-teal-600/30 text-teal-300"
                : "border border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
            )}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1">
        {filtered.map((t) => (
          <button
            key={t.id}
            onClick={() => onSelect(t)}
            className={cn(
              "text-left p-4 rounded-lg border transition-colors",
              selectedId === t.id
                ? "border-teal-500 bg-teal-900/20"
                : "border-ifx-border-dark hover:border-teal-600/40 hover:bg-navy-700/20"
            )}
          >
            <div className="flex items-start gap-2">
              <FileText className="w-4 h-4 text-teal-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-white">{t.name}</p>
                <p className="text-xs text-slate-400 mt-1 line-clamp-2">{t.description}</p>
                {t.last_generated && (
                  <p className="text-xs text-slate-500 mt-1">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {formatDate(t.last_generated)}
                  </p>
                )}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Step 2: Configure Parameters ─────────────────────────────────────────────
function buildDynamicSchema(params: ReportParameter[]) {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const p of params) {
    let field: z.ZodTypeAny;
    switch (p.type) {
      case "text":
        field = z.string();
        break;
      case "number":
        field = z.coerce.number();
        break;
      case "boolean":
        field = z.boolean();
        break;
      case "select":
      case "date":
        field = z.string();
        break;
      case "date_range":
        field = z.object({ start: z.string(), end: z.string() });
        break;
      case "multi_select":
        field = z.array(z.string());
        break;
      default:
        field = z.unknown();
    }
    shape[p.key] = p.required ? field : field.optional();
  }
  return z.object(shape);
}

function ConfigureParametersStep({
  template,
  onUpdate,
}: {
  template: ReportTemplate;
  onUpdate: (params: Record<string, unknown>) => void;
}) {
  const schema = React.useMemo(
    () => buildDynamicSchema(template.parameters),
    [template.parameters]
  );

  const { register, control, handleSubmit, watch } = useForm({
    resolver: zodResolver(schema),
  });

  const values = watch();
  React.useEffect(() => {
    onUpdate(values as Record<string, unknown>);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(values)]);

  if (template.parameters.length === 0) {
    return (
      <p className="text-sm text-slate-400 italic">
        This report has no configurable parameters.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {template.parameters.map((p) => (
        <div key={p.key}>
          <label className="block text-xs font-medium text-slate-300 mb-1.5">
            {p.label}
            {p.required && <span className="text-red-400 ml-1">*</span>}
          </label>

          {p.type === "date_range" ? (
            <div className="flex gap-3">
              <input
                type="date"
                {...register(`${p.key}.start`)}
                className="flex-1 px-3 py-2 rounded-lg border border-ifx-border-dark bg-navy-900 text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
              <span className="flex items-center text-slate-400 text-sm">to</span>
              <input
                type="date"
                {...register(`${p.key}.end`)}
                className="flex-1 px-3 py-2 rounded-lg border border-ifx-border-dark bg-navy-900 text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
            </div>
          ) : p.type === "select" ? (
            <select
              {...register(p.key)}
              className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
            >
              <option value="">{p.placeholder ?? "Select..."}</option>
              {(p.options ?? []).map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          ) : p.type === "boolean" ? (
            <Controller
              name={p.key}
              control={control}
              render={({ field }) => (
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!!field.value}
                    onChange={field.onChange}
                    className="accent-teal-500 w-4 h-4"
                  />
                  <span className="text-sm text-slate-300">Enabled</span>
                </label>
              )}
            />
          ) : (
            <input
              type={p.type === "number" ? "number" : p.type === "date" ? "date" : "text"}
              {...register(p.key)}
              placeholder={p.placeholder}
              className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
            />
          )}
        </div>
      ))}
      {/* satisfy eslint — handleSubmit is bound to form */}
      <form onSubmit={handleSubmit(() => { /* no-op, controlled by wizard */ })} />
    </div>
  );
}

// ── Step 3: Preview ────────────────────────────────────────────────────────────
function PreviewStep({
  template,
  params,
}: {
  template: ReportTemplate;
  params: Record<string, unknown>;
}) {
  const [previewUrl, setPreviewUrl] = React.useState<string | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);

  React.useEffect(() => {
    setIsLoading(true);
    apiPost<{ preview_url: string }>(
      `${API_URLS.reporting}/api/v1/reports/preview`,
      { template_id: template.id, parameters: params }
    )
      .then((res) => setPreviewUrl(res.preview_url))
      .catch(() => setPreviewUrl(null))
      .finally(() => setIsLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [template.id]);

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-400">First-page preview of the generated report.</p>
      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/60 overflow-hidden min-h-64">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-6 h-6 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : previewUrl ? (
          <iframe src={previewUrl} className="w-full h-64" title="Report preview" sandbox="allow-same-origin" />
        ) : (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <FileText className="w-10 h-10 text-slate-600" />
            <p className="text-sm text-slate-500">Preview not available for this report type</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Step 4: Deliver ───────────────────────────────────────────────────────────
type DeliveryMode = "now" | "schedule";

function DeliverStep({
  onUpdate,
}: {
  onUpdate: (data: Record<string, unknown>) => void;
}) {
  const [mode, setMode] = React.useState<DeliveryMode>("now");
  const [format, setFormat] = React.useState<ReportFormat>("pdf");
  const [frequency, setFrequency] = React.useState<ScheduleFrequency>("weekly");
  const [recipients, setRecipients] = React.useState<string[]>([]);
  const [recipientInput, setRecipientInput] = React.useState("");

  React.useEffect(() => {
    onUpdate({ delivery_mode: mode, format, frequency, recipients });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, format, frequency, JSON.stringify(recipients)]);

  return (
    <div className="space-y-5">
      <div className="flex gap-3">
        {(["now", "schedule"] as DeliveryMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={cn(
              "flex-1 flex flex-col items-center gap-1.5 p-4 rounded-lg border transition-colors",
              mode === m
                ? "border-teal-500 bg-teal-900/20"
                : "border-ifx-border-dark hover:border-teal-600/40"
            )}
          >
            {m === "now" ? <Download className="w-5 h-5 text-teal-400" /> : <Clock className="w-5 h-5 text-teal-400" />}
            <span className="text-sm font-medium text-white capitalize">
              {m === "now" ? "Generate Now" : "Schedule"}
            </span>
            <span className="text-xs text-slate-400">
              {m === "now" ? "Download immediately" : "Recurring delivery"}
            </span>
          </button>
        ))}
      </div>

      <div>
        <label className="block text-xs font-medium text-slate-300 mb-1.5">Format</label>
        <div className="flex gap-2">
          {(["pdf", "excel", "csv"] as ReportFormat[]).map((f) => (
            <button
              key={f}
              onClick={() => setFormat(f)}
              className={cn(
                "flex-1 py-2 rounded-lg border text-xs uppercase font-medium transition-colors",
                format === f
                  ? "border-teal-500 bg-teal-900/20 text-teal-300"
                  : "border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
              )}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {mode === "schedule" && (
        <>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Frequency</label>
            <div className="flex gap-2">
              {(["daily", "weekly", "monthly"] as ScheduleFrequency[]).map((f) => (
                <button
                  key={f}
                  onClick={() => setFrequency(f)}
                  className={cn(
                    "flex-1 py-2 rounded-lg border text-xs capitalize font-medium transition-colors",
                    frequency === f
                      ? "border-teal-500 bg-teal-900/20 text-teal-300"
                      : "border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">Email Recipients</label>
            <div className="flex gap-2">
              <input
                type="email"
                value={recipientInput}
                onChange={(e) => setRecipientInput(e.target.value)}
                placeholder="email@example.com"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && recipientInput) {
                    setRecipients((prev) => [...prev, recipientInput]);
                    setRecipientInput("");
                  }
                }}
                className="flex-1 px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              />
              <button
                onClick={() => {
                  if (recipientInput) {
                    setRecipients((prev) => [...prev, recipientInput]);
                    setRecipientInput("");
                  }
                }}
                className="px-3 py-2 rounded-lg bg-navy-700 hover:bg-navy-500 text-slate-200 text-sm transition-colors"
              >
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-1 mt-2">
              {recipients.map((r) => (
                <span key={r} className="text-xs px-2 py-0.5 rounded-full bg-navy-700 text-slate-300 flex items-center gap-1">
                  {r}
                  <button onClick={() => setRecipients((prev) => prev.filter((x) => x !== r))} className="text-slate-500 hover:text-red-400">×</button>
                </span>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Step 5: Confirm ───────────────────────────────────────────────────────────
function ConfirmStep({
  template,
  data,
}: {
  template: ReportTemplate;
  data: Record<string, unknown>;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/60 p-5 space-y-3 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Template</span>
          <span className="text-white font-medium">{template.name}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Format</span>
          <span className="text-white uppercase">{String(data.format ?? "pdf")}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Delivery</span>
          <span className="text-white capitalize">{data.delivery_mode === "now" ? "Generate Now" : `Scheduled (${String(data.frequency ?? "daily")})`}</span>
        </div>
        {!!data.recipients && (data.recipients as string[]).length > 0 && (
          <div className="flex justify-between">
            <span className="text-slate-400">Recipients</span>
            <span className="text-white">{(data.recipients as string[]).join(", ")}</span>
          </div>
        )}
      </div>
      <div className="rounded-lg border border-teal-600/20 bg-teal-900/10 p-4">
        <p className="text-sm text-teal-300">
          Click Submit to {data.delivery_mode === "now" ? "generate and download your report" : "create the schedule"}.
        </p>
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
interface ReportWizardProps {
  initialTemplateId?: string;
  onClose?: () => void;
}

export function ReportWizard({ initialTemplateId, onClose }: ReportWizardProps) {
  const router = useRouter();
  const { currentStep, setStep, data, updateData, isLastStep } = useWizard(
    STEPS.length,
    "report_wizard"
  );
  const [selectedTemplate, setSelectedTemplate] = React.useState<ReportTemplate | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  React.useEffect(() => {
    if (initialTemplateId) {
      apiGet<ReportTemplate>(`${API_URLS.reporting}/api/v1/reports/templates/${initialTemplateId}`)
        .then((t) => {
          setSelectedTemplate(t);
          updateData({ template_id: t.id });
        })
        .catch(() => {/* no-op */});
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTemplateId]);

  const handleNext = useCallback(async (): Promise<boolean> => {
    if (currentStep === 0 && !selectedTemplate) return false;

    if (isLastStep) {
      setIsSubmitting(true);
      try {
        if (data.delivery_mode === "now") {
          const res = await apiPost<{ report_id: string }>(
            `${API_URLS.reporting}/api/v1/reports/generate`,
            { template_id: selectedTemplate?.id, parameters: data.params, format: data.format }
          );
          router.push(`/reporting/viewer/${res.report_id}`);
        } else {
          await apiPost(`${API_URLS.reporting}/api/v1/reports/scheduled`, {
            template_id: selectedTemplate?.id,
            parameters: data.params,
            frequency: data.frequency,
            format: data.format,
            recipients: data.recipients,
            hour: 8,
            minute: 0,
            is_active: true,
          });
          router.push("/reporting/scheduled");
        }
        onClose?.();
        return true;
      } catch {
        return false;
      } finally {
        setIsSubmitting(false);
      }
    }
    return true;
  }, [currentStep, selectedTemplate, isLastStep, data, router, onClose]);

  const stepContent = [
    <SelectTemplateStep
      key="select"
      selectedId={selectedTemplate?.id}
      onSelect={(t) => { setSelectedTemplate(t); updateData({ template_id: t.id }); }}
    />,
    selectedTemplate ? (
      <ConfigureParametersStep
        key="configure"
        template={selectedTemplate}
        onUpdate={(params) => updateData({ params })}
      />
    ) : <p key="no-template" className="text-sm text-slate-400">Please select a template first.</p>,
    selectedTemplate ? (
      <PreviewStep
        key="preview"
        template={selectedTemplate}
        params={(data.params as Record<string, unknown>) ?? {}}
      />
    ) : <p key="no-template-prev" className="text-sm text-slate-400">Please select a template first.</p>,
    <DeliverStep key="deliver" onUpdate={(d) => updateData(d)} />,
    selectedTemplate ? (
      <ConfirmStep key="confirm" template={selectedTemplate} data={data} />
    ) : <p key="no-template-conf" className="text-sm text-slate-400">Please select a template first.</p>,
  ];

  return (
    <Wizard
      steps={STEPS}
      currentStep={currentStep}
      onStepChange={setStep}
      onClose={onClose}
      title="Generate Report"
      onNext={handleNext}
      isNextDisabled={currentStep === 0 && !selectedTemplate}
      isSubmitting={isSubmitting}
      isLastStep={isLastStep}
      nextLabel={isLastStep ? "Submit" : undefined}
      onSaveDraft={() => updateData({})}
    >
      {stepContent[currentStep]}
    </Wizard>
  );
}
