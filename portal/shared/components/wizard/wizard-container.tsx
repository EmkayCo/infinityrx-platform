// T2: Wizard container — step sidebar + navigation bar.
"use client";

import React from "react";
import { CheckCircle2, Circle, Clock } from "lucide-react";
import { WizardConfig } from "./types";
import { UseWizardReturn } from "./use-wizard";
import { cn } from "@shared/lib/format";

interface WizardContainerProps<T> {
  config: WizardConfig<T>;
  wizard: UseWizardReturn<T>;
  children: React.ReactNode;
  /** Override footer buttons (e.g. final step has different actions) */
  footerOverride?: React.ReactNode;
}

export function WizardContainer<T>({
  config,
  wizard,
  children,
  footerOverride,
}: WizardContainerProps<T>) {
  const { currentStep, completedSteps, canGoNext, canGoBack, goNext, goBack, isSubmitting } =
    wizard;

  const isLastStep = currentStep === config.steps.length - 1;

  return (
    <div className="flex h-full min-h-[600px] bg-ifx-surface-light dark:bg-ifx-surface-dark rounded-lg border border-ifx-border-light dark:border-ifx-border-dark overflow-hidden">
      {/* Step sidebar */}
      <nav
        className="w-56 shrink-0 bg-navy-900 text-white p-4 flex flex-col gap-1"
        aria-label="Wizard steps"
      >
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 px-2">
          {config.title}
        </h2>
        {config.steps.map((step, index) => {
          const isDone = completedSteps.has(index);
          const isCurrent = index === currentStep;
          const isFuture = !isDone && !isCurrent;

          return (
            <button
              key={step.id}
              onClick={() => wizard.goToStep(index)}
              disabled={isFuture}
              aria-current={isCurrent ? "step" : undefined}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-md text-sm text-left transition-colors",
                isCurrent && "bg-teal-500/20 text-teal-400 font-medium",
                isDone && "text-slate-300 hover:bg-white/10 cursor-pointer",
                isFuture && "text-slate-600 cursor-not-allowed"
              )}
            >
              <span className="shrink-0 w-5 h-5 flex items-center justify-center">
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-teal-400" aria-hidden />
                ) : isCurrent ? (
                  <Clock className="w-4 h-4 text-teal-400" aria-hidden />
                ) : (
                  <Circle className="w-4 h-4 text-slate-600" aria-hidden />
                )}
              </span>
              <span className="truncate">{step.title}</span>
            </button>
          );
        })}
      </nav>

      {/* Step content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Step header */}
        <div className="px-6 py-4 border-b border-ifx-border-light dark:border-ifx-border-dark">
          <p className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">
            Step {currentStep + 1} of {config.steps.length}
          </p>
          <h3 className="text-lg font-semibold text-ifx-text-primary dark:text-ifx-text-primary-dark">
            {config.steps[currentStep]?.title}
          </h3>
          {config.steps[currentStep]?.description && (
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {config.steps[currentStep].description}
            </p>
          )}
        </div>

        {/* Draft resume banner */}
        {wizard.hasDraft && (
          <div className="px-6 py-3 bg-ifx-info/10 border-b border-ifx-info/20 flex items-center justify-between gap-4">
            <span className="text-sm text-blue-600 dark:text-blue-400">
              You have a saved draft for this wizard.
            </span>
            <div className="flex gap-2">
              <button
                onClick={wizard.resumeDraft}
                className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
              >
                Resume draft
              </button>
              <span className="text-slate-400">·</span>
              <button
                onClick={wizard.discardDraft}
                className="text-sm text-slate-500 hover:underline"
              >
                Start fresh
              </button>
            </div>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 overflow-y-auto p-6">{children}</div>

        {/* Footer nav */}
        <div className="px-6 py-4 border-t border-ifx-border-light dark:border-ifx-border-dark flex items-center justify-between gap-3">
          {footerOverride ?? (
            <>
              <button
                onClick={goBack}
                disabled={!canGoBack}
                className="px-4 py-2 text-sm font-medium rounded-md border border-ifx-border-light dark:border-ifx-border-dark text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                ← Back
              </button>

              <div className="flex items-center gap-3">
                {config.steps[currentStep]?.optional && (
                  <button
                    onClick={goNext}
                    className="text-sm text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                  >
                    Skip
                  </button>
                )}
                <button
                  onClick={() => {
                    wizard.save?.();
                  }}
                  className="px-4 py-2 text-sm font-medium rounded-md border border-teal-500/40 text-teal-600 dark:text-teal-400 hover:bg-teal-500/10 transition-colors"
                >
                  Save Draft
                </button>
                {!isLastStep ? (
                  <button
                    onClick={goNext}
                    disabled={!canGoNext}
                    className="px-5 py-2 text-sm font-medium rounded-md bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    Next →
                  </button>
                ) : (
                  <button
                    onClick={wizard.submit}
                    disabled={!canGoNext || isSubmitting}
                    className="px-5 py-2 text-sm font-medium rounded-md bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSubmitting ? "Processing…" : "Confirm and Execute"}
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
