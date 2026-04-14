// Payment Batch Wizard — 5-step guided workflow.
// PRD 7.3.
"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { WizardContainer } from "@shared/components/wizard/wizard-container";
import { useWizard } from "@shared/components/wizard/use-wizard";
import { WizardConfig } from "@shared/components/wizard/types";
import { approveBatch } from "@shared/lib/payments-api";
import { SelectClaimsStep } from "./step1-select-claims";
import { ReviewRoutingStep } from "./step2-review-routing";
import { GenerateFilesStep } from "./step3-generate-files";
import { ApproveBatchStep } from "./step4-approve";
import { TransmitStep } from "./step5-transmit";
import { PaymentBatchWizardData, INITIAL_BATCH_DATA } from "./types";

export function PaymentBatchWizard() {
  const router = useRouter();
  const [approveError, setApproveError] = React.useState<string | null>(null);

  const config: WizardConfig<PaymentBatchWizardData> = {
    id: "payment-batch-new",
    title: "New Payment Batch",
    initialData: INITIAL_BATCH_DATA,
    onComplete: async () => {
      router.push("/payments");
    },
    approvalThreshold: "500000.00",
    amountField: "selected_total",
    steps: [
      {
        id: "select-claims",
        title: "Select Claims",
        description: "Choose eligible claims to include in this payment batch.",
        isValid: (d) => d.selected_claim_ids.length > 0,
        render: ({ data, onChange }) => (
          <SelectClaimsStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "review-routing",
        title: "Review Routing",
        description: "Confirm vendor routing for each client.",
        isValid: () => true,
        render: ({ data, onChange }) => (
          <ReviewRoutingStep data={data} onChange={onChange} />
        ),
      },
      {
        id: "generate-files",
        title: "Generate Files",
        description: "Preview generated payment files before approval.",
        isValid: (d) => !!d.batch_id,
        render: ({ data, onChange }) => (
          <GenerateFilesStep data={data} onChange={onChange} />
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
            <ApproveBatchStep
              data={data}
              onChange={onChange}
              onApprove={async () => {
                setApproveError(null);
                try {
                  await approveBatch(
                    data.batch_id!,
                    data.approver_id ?? undefined,
                    data.approval_notes || undefined
                  );
                  onNext();
                } catch (err) {
                  setApproveError(
                    err instanceof Error ? err.message : "Failed to approve batch"
                  );
                }
              }}
            />
          </>
        ),
      },
      {
        id: "transmit",
        title: "Transmit",
        description: "Transmit payment files to vendors and track acknowledgment.",
        isValid: () => true,
        render: ({ data, onChange }) => (
          <TransmitStep data={data} onChange={onChange} />
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
