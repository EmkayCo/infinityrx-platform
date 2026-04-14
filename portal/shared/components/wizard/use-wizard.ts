// T2: Core wizard state hook.
"use client";

import { useCallback, useState, useEffect } from "react";
import { WizardConfig } from "./types";
import { useAutoSave } from "@shared/hooks/use-auto-save";

export interface WizardState<T> {
  currentStep: number;
  data: T;
  completedSteps: number[];
}

export interface UseWizardReturn<T> {
  currentStep: number;
  data: T;
  completedSteps: Set<number>;
  isSubmitting: boolean;
  hasDraft: boolean;
  canGoNext: boolean;
  canGoBack: boolean;
  goNext: () => void;
  goBack: () => void;
  goToStep: (index: number) => void;
  onChange: (partial: Partial<T>) => void;
  submit: () => Promise<void>;
  resumeDraft: () => void;
  discardDraft: () => void;
  save: () => void;
}

export function useWizard<T>(config: WizardConfig<T>): UseWizardReturn<T> {
  const draftKey = `wizard_draft_${config.id}`;

  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<T>(config.initialData);
  const [completedSteps, setCompletedSteps] = useState<Set<number>>(new Set());
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [draftLoaded, setDraftLoaded] = useState(false);

  const autoSave = useAutoSave<WizardState<T>>({ storageKey: draftKey });

  // Check for draft on mount
  useEffect(() => {
    if (!draftLoaded && autoSave.hasDraft && autoSave.draft) {
      setDraftLoaded(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSave.hasDraft]);

  const hasDraft =
    autoSave.hasDraft &&
    autoSave.draft != null &&
    (autoSave.draft.currentStep ?? 0) > 0;

  const currentStepConfig = config.steps[currentStep];
  const canGoNext =
    !isSubmitting &&
    (!currentStepConfig?.isValid || currentStepConfig.isValid(data));
  const canGoBack = currentStep > 0 && !isSubmitting;

  const save = useCallback(() => {
    autoSave.save({
      currentStep,
      data,
      completedSteps: Array.from(completedSteps),
    });
  }, [autoSave, currentStep, data, completedSteps]);

  const onChange = useCallback((partial: Partial<T>) => {
    setData((prev) => ({ ...prev, ...partial }));
  }, []);

  const goNext = useCallback(() => {
    setCompletedSteps((prev) => {
      const next = new Set(prev);
      next.add(currentStep);
      return next;
    });
    setCurrentStep((prev) => Math.min(prev + 1, config.steps.length - 1));
    // Save after step transition
    setTimeout(() => {
      autoSave.save({
        currentStep: Math.min(currentStep + 1, config.steps.length - 1),
        data,
        completedSteps: Array.from(completedSteps).concat(currentStep),
      });
    }, 0);
  }, [currentStep, config.steps.length, autoSave, data, completedSteps]);

  const goBack = useCallback(() => {
    setCurrentStep((prev) => Math.max(prev - 1, 0));
  }, []);

  const goToStep = useCallback(
    (index: number) => {
      if (index < 0 || index >= config.steps.length) return;
      if (!completedSteps.has(index) && index > currentStep) return;
      setCurrentStep(index);
    },
    [config.steps.length, completedSteps, currentStep]
  );

  const resumeDraft = useCallback(() => {
    if (autoSave.draft) {
      setCurrentStep(autoSave.draft.currentStep);
      setData(autoSave.draft.data);
      setCompletedSteps(new Set(autoSave.draft.completedSteps));
    }
  }, [autoSave.draft]);

  const discardDraft = useCallback(() => {
    autoSave.clear();
    setCurrentStep(0);
    setData(config.initialData);
    setCompletedSteps(new Set());
  }, [autoSave, config.initialData]);

  const submit = useCallback(async () => {
    setIsSubmitting(true);
    try {
      await config.onComplete(data);
      autoSave.clear();
    } finally {
      setIsSubmitting(false);
    }
  }, [config, data, autoSave]);

  return {
    currentStep,
    data,
    completedSteps,
    isSubmitting,
    hasDraft,
    canGoNext,
    canGoBack,
    goNext,
    goBack,
    goToStep,
    onChange,
    submit,
    resumeDraft,
    discardDraft,
    save,
  };
}
