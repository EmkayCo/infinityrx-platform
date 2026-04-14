// Billing Cycle Wizard — 6-step guided workflow.
// PRD 7.2. Each step auto-saves to localStorage.
"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { WizardContainer } from "@shared/components/wizard/wizard-container";
import { useWizard } from "@shared/components/wizard/use-wizard";
import { WizardConfig } from "@shared/components/wizard/types";
import { approveCycle } from "@shared/lib/billing-api";
import { isMockEnabled } from "@shared/lib/mock-data";
import { UploadStep } from "./step1-upload";
import { MapFieldsStep } from "./step2-map-fields";
import { ValidateStep } from "./step3-validate";
import { PreviewStep } from "./step4-preview";
import { ApproveStep } from "./step5-approve";
import { GenerateStep } from "./step6-generate";
import { BillingCycleWizardData, INITIAL_WIZARD_DATA } from "./types";

// 63-column headers from InfinityRX_20260401_1618.txt (pipe-delimited)
const IFX_HEADERS_63 = [
  "Client Provided Unique ID","Paid / Reversal Status Code","BIN","PCN","Date of Service",
  "Date Written","Group Number","Cardholder ID","LastName","FirstName","DOB","Person Code",
  "Service Provider ID","NDC","Rx Number","Quantity","Days Supply","Compound Code","DAW",
  "Submitted Ingredient Cost","Submitted Dispensing Fee","Usual and Customary",
  "Submitted Gross Amount Due","Submitted Tax","Prescriber NPI","Copay","Patient Pay Amount",
  "Amount Applied to Deductible","Amount Applied to Out of Pocket","Pharmacy Total Paid",
  "Pharmacy Ingredient Cost Paid","Pharmacy Dispensing Fee Paid","Pharmacy Tax Paid",
  "Sell Ingredient Cost","Sell Dispensing Fee","Sell Tax","Total Client Billed",
  "Other Coverage Code","Process Date / Time","Price Source","Keyed Claim Indicator",
  "Selfpay Indicator","Is Billable","Historical","Test Claim","Location Code","ScriptTag",
  "DrugTier","BrandGeneric","IsPreferred","SenderID","Network Reimbursement ID",
  "Amount Applied to Benefit Cap","Claim Processing Fee","Transaction Fees",
  "Reversal Auth Reference","Statement Flag","Bank Routing Number","Bank Account Number",
  "Bank Account Type","Primary Chain Code","Debit Card Amount","POS Adjustment",
];

const MOCK_UPLOAD_ID = "mock-ifx-bc-2026-sm-08";

function getMockInitialData(): BillingCycleWizardData {
  return {
    ...INITIAL_WIZARD_DATA,
    upload_id: MOCK_UPLOAD_ID,
    upload_filename: "InfinityRX_20260401_1618.txt",
    upload_size_bytes: 29706745,
    upload_estimated_rows: 89231,
    detected_columns: IFX_HEADERS_63,
    is_duplicate: false,
    mapping_template_id: null,
    field_mappings: [],
    validation_result: {
      upload_id: MOCK_UPLOAD_ID,
      total_rows: 89231,
      valid_count: 89231,
      warning_count: 0,
      error_count: 0,
      errors: [],
      warnings: [],
    },
    proceed_with_valid_only: false,
    total_claims: 89231,
    total_ap_amount: "23868600.79",
    total_ar_amount: "23868600.79",
    total_fee_amount: "212090.20",
  };
}

export function BillingCycleWizard() {
  const router = useRouter();
  const [approveError, setApproveError] = React.useState<string | null>(null);

  const initialData = isMockEnabled() ? getMockInitialData() : INITIAL_WIZARD_DATA;

  const config: WizardConfig<BillingCycleWizardData> = {
    id: "billing-cycle-new",
    title: "New Billing Cycle",
    initialData,
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
