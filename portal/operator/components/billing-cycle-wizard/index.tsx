// Billing Cycle Wizard — 6-step guided workflow.
// PRD 7.2. Each step auto-saves to localStorage.
"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { WizardContainer } from "@shared/components/wizard/wizard-container";
import { useWizard } from "@shared/components/wizard/use-wizard";
import { WizardConfig } from "@shared/components/wizard/types";
import { approveCycle } from "@shared/lib/billing-api";
import { UploadStep } from "./step1-upload";
import { MapFieldsStep } from "./step2-map-fields";
import { ValidateStep } from "./step3-validate";
import { PreviewStep } from "./step4-preview";
import { ApproveStep } from "./step5-approve";
import { GenerateStep } from "./step6-generate";
import { BillingCycleWizardData, INITIAL_WIZARD_DATA } from "./types";

export function BillingCycleWizard() {
  const router = useRouter();
  const [approveError, setApproveError] = React.useState<string | null>(null);

  const config: WizardConfig<BillingCycleWizardData> = {
    id: "billing-cycle-new",
    title: "New Billing Cycle",
    initialData: INITIAL_WIZARD_DATA,
    onComplete: async () => {
      router.push("/billing");
    },
    approvalThreshold: "1000000.00",
    amountField: "total_ap_amount",
    steps: [
      {
        id: "upload",
        title: "Upload Claims File",
        description: "Upload CSV, Excel, or pipe-delimited claims file.",
        isValid: (d) => !!d.upload_id,
        render: ({ data, onChange }) => (
          <UploadStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "map-fields",
        title: "Map Fields",
        description: "Map source columns to system fields.",
        optional: false,
        isValid: (d) => {
          const requiredFields = [
            "member_id", "pharmacy_npi", "drug_ndc", "fill_date",
            "days_supply", "quantity", "ingredient_cost", "dispensing_fee",
            "copay", "plan_paid",
          ];
          return requiredFields.every((f) =>
            d.field_mappings.some((m) => m.target_field === f)
          );
        },
        render: ({ data, onChange }) => (
          <MapFieldsStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "validate",
        title: "Validate",
        description: "Server-side validation of all records.",
        isValid: (d) => {
          if (!d.validation_result) return false;
          if (d.validation_result.error_count > 0 && !d.proceed_with_valid_only) return false;
          return d.validation_result.valid_count > 0;
        },
        render: ({ data, onChange }) => (
          <ValidateStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "preview",
        title: "Preview",
        description: "Review financial summary and anomaly flags.",
        isValid: () => true,
        render: ({ data, onChange }) => (
          <PreviewStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "approve",
        title: "Approve",
        description: "Confirm or submit for two-person approval.",
        isValid: () => true,
        render: ({ data, onChange, onNext }) => (
          <>
            {approveError && (
              <div className="rounded border border-red-500/30 bg-red-500/5 p-3 mb-4">
                <p className="text-sm text-red-400">{approveError}</p>
              </div>
            )}
            <ApproveStep
              data={data}
              onChange={onChange}
              onApprove={async () => {
                setApproveError(null);
                try {
                  const cycle = await approveCycle({
                    upload_id: data.upload_id!,
                    mapping_template_id: data.mapping_template_id ?? undefined,
                    mappings: data.field_mappings,
                    approver_id: data.approver_id ?? undefined,
                    notes: data.approval_notes || undefined,
                  });
                  onChange({ generated_cycle_id: cycle.id });
                  onNext();
                } catch (err) {
                  setApproveError(
                    err instanceof Error ? err.message : "Failed to approve cycle"
                  );
                }
              }}
            />
          </>
        ),
      },
      {
        id: "generate",
        title: "Generate & Transmit",
        description: "Download and transmit generated outputs.",
        isValid: () => true,
        render: ({ data, onChange }) => (
          <GenerateStep data={data} onChange={onChange} />
        ),
      },
    ],
  };

  const wizard = useWizard(config);

  return (
    <WizardContainer config={config} wizard={wizard}>
      {config.steps[wizard.currentStep]?.render({
        data: wizard.data,
        onChange: wizard.onChange,
        onNext: wizard.goNext,
        onBack: wizard.goBack,
      })}
    </WizardContainer>
  );
}
