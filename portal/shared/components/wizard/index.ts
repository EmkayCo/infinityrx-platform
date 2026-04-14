// Wizard framework — shared across billing, payment, and other wizard workflows.

// T2 config-driven wizard (WizardContainer + WizardConfig-based useWizard)
export { WizardContainer } from "./wizard-container";
export { useWizard as useWizardConfig } from "./use-wizard";
export type { WizardStepConfig, WizardConfig } from "./types";
export type { UseWizardReturn } from "./use-wizard";

// Simple step-based Wizard component (used by investigation-wizard, report-wizard, etc.)
// WizardStep here is the simple {id, title, description} type (no render function required)
export { Wizard, useWizard } from "./index-component";
export type { WizardStep } from "./index-component";
