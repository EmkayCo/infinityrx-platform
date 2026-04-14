// T2: Wizard framework types.
import { ReactNode } from "react";

export interface WizardStepConfig<T = unknown> {
  id: string;
  title: string;
  description?: string;
  optional?: boolean;
  /** Render the step content, receiving the current form data and a setter */
  render: (props: {
    data: T;
    onChange: (partial: Partial<T>) => void;
    onNext: () => void;
    onBack: () => void;
  }) => ReactNode;
  /** Return true if the step is valid and Next can be enabled */
  isValid?: (data: T) => boolean;
}

export interface WizardConfig<T = unknown> {
  id: string; // used as localStorage draft key
  title: string;
  steps: WizardStepConfig<T>[];
  initialData: T;
  /** Called when the wizard is fully completed */
  onComplete: (data: T) => void | Promise<void>;
  /** Called when the wizard is closed/cancelled */
  onCancel?: () => void;
  /** Approval threshold in dollars (string). If final amount exceeds this, show approval flow */
  approvalThreshold?: string;
  /** The field in T that holds the dollar amount to check against threshold */
  amountField?: keyof T;
}
