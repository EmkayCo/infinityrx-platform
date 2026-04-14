"use client";

import React, { useState, useCallback } from "react";
import { Check, X } from "lucide-react";
import { cn } from "@shared/lib/format";

export interface WizardStep {
  id: string;
  title: string;
  description?: string;
  optional?: boolean;
}

interface WizardProps {
  steps: WizardStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  onClose?: () => void;
  title: string;
  children: React.ReactNode;
  onNext?: () => Promise<boolean> | boolean;
  onBack?: () => void;
  onSaveDraft?: () => void;
  isNextDisabled?: boolean;
  isSubmitting?: boolean;
  nextLabel?: string;
  isLastStep?: boolean;
}

export function Wizard({
  steps,
  currentStep,
  onStepChange,
  onClose,
  title,
  children,
  onNext,
  onBack,
  onSaveDraft,
  isNextDisabled,
  isSubmitting,
  nextLabel,
  isLastStep,
}: WizardProps) {
  const handleNext = useCallback(async () => {
    if (onNext) {
      const ok = await onNext();
      if (!ok) return;
    }
    if (!isLastStep) onStepChange(currentStep + 1);
  }, [onNext, isLastStep, currentStep, onStepChange]);

  const handleBack = useCallback(() => {
    onBack?.();
    if (currentStep > 0) onStepChange(currentStep - 1);
  }, [onBack, currentStep, onStepChange]);

  return (
    <div className="flex flex-col h-full bg-navy-900 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-ifx-border-dark">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {onClose && (
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-navy-700 text-slate-400 hover:text-white transition-colors"
            aria-label="Close wizard"
          >
            <X className="w-5 h-5" />
          </button>
        )}
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Step sidebar */}
        <div className="w-56 flex-shrink-0 border-r border-ifx-border-dark bg-navy-900/60 p-4">
          <nav aria-label="Wizard steps">
            <ol className="space-y-1">
              {steps.map((step, index) => {
                const isDone = index < currentStep;
                const isCurrent = index === currentStep;
                const isFuture = index > currentStep;
                return (
                  <li key={step.id}>
                    <button
                      onClick={() => isDone && onStepChange(index)}
                      disabled={isFuture}
                      className={cn(
                        "w-full flex items-start gap-3 px-3 py-2.5 rounded-lg text-left transition-colors",
                        isCurrent && "bg-teal-900/30 border border-teal-600/30",
                        isDone && "hover:bg-navy-700/50 cursor-pointer",
                        isFuture && "opacity-40 cursor-not-allowed"
                      )}
                      aria-current={isCurrent ? "step" : undefined}
                    >
                      <span
                        className={cn(
                          "flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold mt-0.5",
                          isDone && "bg-ifx-success text-white",
                          isCurrent && "bg-teal-500 text-white",
                          isFuture && "bg-navy-700 text-slate-500"
                        )}
                      >
                        {isDone ? <Check className="w-3.5 h-3.5" /> : index + 1}
                      </span>
                      <span className="flex flex-col">
                        <span className={cn(
                          "text-sm font-medium",
                          isCurrent ? "text-white" : isDone ? "text-slate-300" : "text-slate-500"
                        )}>
                          {step.title}
                        </span>
                        {step.description && (
                          <span className="text-xs text-slate-500 mt-0.5">{step.description}</span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>
        </div>

        {/* Step content */}
        <div className="flex-1 overflow-auto flex flex-col">
          <div className="flex-1 p-6 overflow-auto">
            {children}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-6 py-4 border-t border-ifx-border-dark bg-navy-900/40">
            <div className="flex items-center gap-2">
              {currentStep > 0 && (
                <button
                  onClick={handleBack}
                  className="px-4 py-2 text-sm rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
                >
                  ← Back
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              {onSaveDraft && (
                <button
                  onClick={onSaveDraft}
                  className="px-4 py-2 text-sm rounded-lg text-slate-400 hover:text-slate-200 transition-colors"
                >
                  Save Draft
                </button>
              )}
              <button
                onClick={handleNext}
                disabled={isNextDisabled || isSubmitting}
                className={cn(
                  "px-5 py-2 text-sm rounded-lg font-medium transition-colors",
                  "bg-teal-600 hover:bg-teal-500 text-white",
                  (isNextDisabled || isSubmitting) && "opacity-50 cursor-not-allowed"
                )}
              >
                {isSubmitting
                  ? "Processing..."
                  : isLastStep
                  ? (nextLabel ?? "Submit")
                  : (nextLabel ?? "Next →")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Hook to manage wizard state with draft auto-save */
export function useWizard(totalSteps: number, draftKey?: string) {
  const [currentStep, setCurrentStep] = useState<number>(() => {
    if (draftKey && typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(`wizard_step_${draftKey}`);
        return saved ? parseInt(saved, 10) : 0;
      } catch {
        return 0;
      }
    }
    return 0;
  });

  const [data, setData] = useState<Record<string, unknown>>(() => {
    if (draftKey && typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(`wizard_data_${draftKey}`);
        return saved ? (JSON.parse(saved) as Record<string, unknown>) : {};
      } catch {
        return {};
      }
    }
    return {};
  });

  const setStep = useCallback((step: number) => {
    const clamped = Math.max(0, Math.min(step, totalSteps - 1));
    setCurrentStep(clamped);
    if (draftKey) {
      try {
        localStorage.setItem(`wizard_step_${draftKey}`, String(clamped));
      } catch { /* ignore */ }
    }
  }, [totalSteps, draftKey]);

  const updateData = useCallback((partial: Record<string, unknown>) => {
    setData((prev) => {
      const next = { ...prev, ...partial };
      if (draftKey) {
        try {
          localStorage.setItem(`wizard_data_${draftKey}`, JSON.stringify(next));
        } catch { /* ignore */ }
      }
      return next;
    });
  }, [draftKey]);

  const clearDraft = useCallback(() => {
    if (draftKey) {
      try {
        localStorage.removeItem(`wizard_step_${draftKey}`);
        localStorage.removeItem(`wizard_data_${draftKey}`);
      } catch { /* ignore */ }
    }
    setCurrentStep(0);
    setData({});
  }, [draftKey]);

  const isLastStep = currentStep === totalSteps - 1;

  return { currentStep, setStep, data, updateData, clearDraft, isLastStep };
}
