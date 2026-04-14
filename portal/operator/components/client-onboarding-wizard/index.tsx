"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CheckCircle, ShieldCheck, AlertTriangle } from "lucide-react";
import { WizardContainer, useWizardConfig } from "@shared/components/wizard";
import type { WizardConfig, WizardStepConfig } from "@shared/components/wizard";
import { apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { cn } from "@shared/lib/format";

// ─── Schemas ────────────────────────────────────────────────────────────────

const clientDetailsSchema = z.object({
  legal_name: z.string().min(2, "Required"),
  dba_name: z.string().optional(),
  tax_id: z.string().regex(/^\d{2}-\d{7}$/, "EIN format: XX-XXXXXXX"),
  npi: z.string().regex(/^\d{10}$/, "NPI must be 10 digits").optional().or(z.literal("")),
  address_line1: z.string().min(2, "Required"),
  address_line2: z.string().optional(),
  city: z.string().min(2, "Required"),
  state: z.string().length(2, "2-letter state code"),
  zip: z.string().regex(/^\d{5}(-\d{4})?$/, "Valid ZIP required"),
  contact_name: z.string().min(2, "Required"),
  contact_email: z.string().email("Valid email required"),
  contact_phone: z.string().regex(/^\+1\d{10}$/, "E.164 format: +1XXXXXXXXXX"),
});

const bankingSchema = z.object({
  account_name: z.string().min(2, "Required"),
  routing_number: z.string().regex(/^\d{9}$/, "9-digit routing number"),
  account_number: z.string().regex(/^\d{4,17}$/, "4–17 digit account number"),
  account_type: z.enum(["checking", "savings"]),
  bank_name: z.string().min(2, "Required"),
});

const feeRulesSchema = z.object({
  admin_fee_pmpm: z.string().regex(/^\d+(\.\d{1,2})?$/, "Valid dollar amount"),
  dispensing_fee: z.string().regex(/^\d+(\.\d{1,2})?$/, "Valid dollar amount"),
  uc_cap_pct: z.string().regex(/^\d+(\.\d{1,2})?$/, "Percentage 0–100"),
  spread_retention_pct: z.string().regex(/^\d+(\.\d{1,2})?$/, "Percentage 0–100"),
  max_oop_annual: z.string().optional(),
});

// ─── Wizard Data Shape ────────────────────────────────────────────────────────

interface OnboardingData {
  legal_name: string;
  dba_name: string;
  tax_id: string;
  npi: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  zip: string;
  contact_name: string;
  contact_email: string;
  contact_phone: string;
  // Program Config
  pbm_enabled: boolean;
  medical_claims_enabled: boolean;
  fwa_enabled: boolean;
  edi_enabled: boolean;
  reporting_enabled: boolean;
  formulary_tiers: number;
  accumulators_enabled: boolean;
  split_billing_enabled: boolean;
  // Banking
  account_name: string;
  routing_number: string;
  account_number: string;
  account_type: "checking" | "savings";
  bank_name: string;
  // Fee Rules
  admin_fee_pmpm: string;
  dispensing_fee: string;
  uc_cap_pct: string;
  spread_retention_pct: string;
  max_oop_annual: string;
  // Outputs
  report_recipients: string;
  remittance_format: "835" | "ERA" | "paper";
  eligibility_feed: "834" | "api" | "manual";
  statement_delivery: "email" | "mail" | "portal";
  // Internal
  mfa_verified: boolean;
}

const DEFAULT_DATA: OnboardingData = {
  legal_name: "", dba_name: "", tax_id: "", npi: "",
  address_line1: "", address_line2: "", city: "", state: "", zip: "",
  contact_name: "", contact_email: "", contact_phone: "",
  pbm_enabled: true, medical_claims_enabled: false, fwa_enabled: true,
  edi_enabled: true, reporting_enabled: true, formulary_tiers: 4,
  accumulators_enabled: true, split_billing_enabled: false,
  account_name: "", routing_number: "", account_number: "",
  account_type: "checking", bank_name: "",
  admin_fee_pmpm: "5.00", dispensing_fee: "1.50",
  uc_cap_pct: "130", spread_retention_pct: "0", max_oop_annual: "",
  report_recipients: "", remittance_format: "835",
  eligibility_feed: "834", statement_delivery: "email",
  mfa_verified: false,
};

// ─── Step 1: Client Details ──────────────────────────────────────────────────

function ClientDetailsStep({
  data,
  onChange,
  onNext,
}: {
  data: OnboardingData;
  onChange: (partial: Partial<OnboardingData>) => void;
  onNext: () => void;
}) {
  type FormData = z.infer<typeof clientDetailsSchema>;
  const form = useForm<FormData>({
    resolver: zodResolver(clientDetailsSchema),
    defaultValues: {
      legal_name: data.legal_name,
      dba_name: data.dba_name,
      tax_id: data.tax_id,
      npi: data.npi,
      address_line1: data.address_line1,
      address_line2: data.address_line2,
      city: data.city,
      state: data.state,
      zip: data.zip,
      contact_name: data.contact_name,
      contact_email: data.contact_email,
      contact_phone: data.contact_phone,
    },
  });

  function submit(d: FormData) {
    onChange(d);
    onNext();
  }

  const Field = ({
    name,
    label,
    placeholder,
    half,
  }: {
    name: keyof FormData;
    label: string;
    placeholder?: string;
    half?: boolean;
  }) => (
    <div className={cn("flex flex-col gap-1", half ? "col-span-1" : "col-span-2")}>
      <label className="text-xs text-slate-400">{label}</label>
      <input
        {...form.register(name)}
        placeholder={placeholder}
        className="px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500 placeholder:text-slate-600"
      />
      {form.formState.errors[name] && (
        <p className="text-xs text-red-400">{form.formState.errors[name]?.message as string}</p>
      )}
    </div>
  );

  return (
    <form id="step-client-details" onSubmit={form.handleSubmit(submit)} className="grid grid-cols-2 gap-4">
      <Field name="legal_name" label="Legal Business Name *" placeholder="Acme Health Plan, Inc." />
      <Field name="dba_name" label="DBA Name" placeholder="Optional" />
      <Field name="tax_id" label="EIN / Tax ID *" placeholder="XX-XXXXXXX" half />
      <Field name="npi" label="NPI (if applicable)" placeholder="XXXXXXXXXX" half />
      <Field name="address_line1" label="Address Line 1 *" placeholder="123 Main Street" />
      <Field name="address_line2" label="Address Line 2" placeholder="Suite 400" />
      <Field name="city" label="City *" placeholder="Chicago" half />
      <Field name="state" label="State *" placeholder="IL" half />
      <Field name="zip" label="ZIP Code *" placeholder="60601" half />
      <div className="col-span-1" />
      <Field name="contact_name" label="Primary Contact Name *" placeholder="Jane Smith" />
      <Field name="contact_email" label="Contact Email *" placeholder="jane@acmehealth.com" half />
      <Field name="contact_phone" label="Contact Phone (E.164) *" placeholder="+13125550100" half />
      <button type="submit" className="hidden" />
    </form>
  );
}

// ─── Step 2: Program Config ──────────────────────────────────────────────────

function ProgramConfigStep({ data, onChange }: { data: OnboardingData; onChange: (p: Partial<OnboardingData>) => void }) {
  const toggles: Array<{ key: keyof OnboardingData; label: string; description: string }> = [
    { key: "pbm_enabled", label: "PBM / Pharmacy Benefit", description: "Pharmacy claims adjudication, formulary management" },
    { key: "medical_claims_enabled", label: "Medical Claims", description: "HCPCS/NDC crosswalk, site-of-care, 340B" },
    { key: "fwa_enabled", label: "FWA Detection (ReclaimRx)", description: "Fraud, waste & abuse investigation suite" },
    { key: "edi_enabled", label: "EDI Transactions", description: "835/837/270/271 etc. via AS2 or SFTP" },
    { key: "reporting_enabled", label: "Reporting & Analytics", description: "Standard and custom reports, dashboards" },
    { key: "accumulators_enabled", label: "Accumulators (Deductible/OOP)", description: "Real-time accumulator sync across channels" },
    { key: "split_billing_enabled", label: "Split Billing", description: "Coordinate pharmacy and medical benefits" },
  ];

  return (
    <div className="space-y-3">
      {toggles.map((t) => (
        <label key={t.key} className="flex items-start gap-4 p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40 hover:bg-navy-700/20 cursor-pointer transition-colors">
          <input
            type="checkbox"
            checked={data[t.key] as boolean}
            onChange={(e) => onChange({ [t.key]: e.target.checked } as Partial<OnboardingData>)}
            className="w-4 h-4 mt-0.5 accent-teal-500"
          />
          <div>
            <p className="text-sm font-medium text-white">{t.label}</p>
            <p className="text-xs text-slate-400 mt-0.5">{t.description}</p>
          </div>
        </label>
      ))}
      <div className="p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40">
        <label className="text-sm font-medium text-white block mb-2">Formulary Tiers</label>
        <select
          value={data.formulary_tiers}
          onChange={(e) => onChange({ formulary_tiers: parseInt(e.target.value, 10) })}
          className="px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
        >
          {[3, 4, 5, 6].map((n) => <option key={n} value={n}>{n} tiers</option>)}
        </select>
        <p className="text-xs text-slate-500 mt-1.5">Standard is 4 tiers (Generic / Preferred Brand / Non-preferred / Specialty)</p>
      </div>
    </div>
  );
}

// ─── Step 3: Banking ─────────────────────────────────────────────────────────

function BankingStep({
  data,
  onChange,
  onNext,
}: {
  data: OnboardingData;
  onChange: (p: Partial<OnboardingData>) => void;
  onNext: () => void;
}) {
  type FormData = z.infer<typeof bankingSchema>;
  const form = useForm<FormData>({
    resolver: zodResolver(bankingSchema),
    defaultValues: {
      account_name: data.account_name,
      routing_number: data.routing_number,
      account_number: data.account_number,
      account_type: data.account_type,
      bank_name: data.bank_name,
    },
  });

  function submit(d: FormData) {
    onChange(d);
    onNext();
  }

  return (
    <>
      <div className="rounded-lg border border-yellow-700/30 bg-yellow-900/10 p-3 mb-5 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
        <p className="text-xs text-yellow-300">
          Banking details are encrypted at rest and transmitted over TLS. Never share account details via unsecured channels.
        </p>
      </div>
      <form id="step-banking" onSubmit={form.handleSubmit(submit)} className="grid grid-cols-2 gap-4">
        {(
          [
            { name: "bank_name" as const, label: "Bank Name *", placeholder: "Chase Bank" },
            { name: "account_name" as const, label: "Account Name *", placeholder: "Acme Health Plan Operating" },
            { name: "routing_number" as const, label: "Routing Number *", placeholder: "XXXXXXXXX (9 digits)" },
            { name: "account_number" as const, label: "Account Number *", placeholder: "XXXXXXXXXXXXXXXXX" },
          ]
        ).map((f) => (
          <div key={f.name} className="flex flex-col gap-1">
            <label className="text-xs text-slate-400">{f.label}</label>
            <input
              {...form.register(f.name)}
              placeholder={f.placeholder}
              className="px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500 placeholder:text-slate-600"
            />
            {form.formState.errors[f.name] && (
              <p className="text-xs text-red-400">{form.formState.errors[f.name]?.message}</p>
            )}
          </div>
        ))}
        <div className="flex flex-col gap-1">
          <label className="text-xs text-slate-400">Account Type *</label>
          <select
            {...form.register("account_type")}
            className="px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
          >
            <option value="checking">Checking</option>
            <option value="savings">Savings</option>
          </select>
        </div>
        <button type="submit" className="hidden" />
      </form>
    </>
  );
}

// ─── Step 4: Fee Rules ───────────────────────────────────────────────────────

function FeeRulesStep({
  data,
  onChange,
  onNext,
}: {
  data: OnboardingData;
  onChange: (p: Partial<OnboardingData>) => void;
  onNext: () => void;
}) {
  type FormData = z.infer<typeof feeRulesSchema>;
  const form = useForm<FormData>({
    resolver: zodResolver(feeRulesSchema),
    defaultValues: {
      admin_fee_pmpm: data.admin_fee_pmpm,
      dispensing_fee: data.dispensing_fee,
      uc_cap_pct: data.uc_cap_pct,
      spread_retention_pct: data.spread_retention_pct,
      max_oop_annual: data.max_oop_annual,
    },
  });

  function submit(d: FormData) {
    onChange(d);
    onNext();
  }

  const FeeField = ({
    name,
    label,
    description,
    prefix = "$",
  }: {
    name: keyof FormData;
    label: string;
    description?: string;
    prefix?: string;
  }) => (
    <div className="p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40">
      <label className="text-sm font-medium text-white block mb-1">{label}</label>
      {description && <p className="text-xs text-slate-400 mb-2">{description}</p>}
      <div className="flex items-center gap-2">
        <span className="text-slate-400 text-sm">{prefix}</span>
        <input
          {...form.register(name)}
          className="w-32 px-3 py-1.5 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500"
        />
      </div>
      {form.formState.errors[name] && (
        <p className="text-xs text-red-400 mt-1">{form.formState.errors[name]?.message as string}</p>
      )}
    </div>
  );

  return (
    <form id="step-fees" onSubmit={form.handleSubmit(submit)} className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <FeeField name="admin_fee_pmpm" label="Admin Fee (PMPM)" description="Per-member-per-month administrative fee" />
      <FeeField name="dispensing_fee" label="Dispensing Fee" description="Per-claim dispensing fee added to drug cost" />
      <FeeField name="uc_cap_pct" label="U&C Cap %" description="Usual & customary price cap as % of AWP" prefix="%" />
      <FeeField name="spread_retention_pct" label="Spread Retention %" description="% of ingredient cost spread retained (0 = pass-through)" prefix="%" />
      <FeeField name="max_oop_annual" label="Annual OOP Maximum" description="Maximum out-of-pocket per member per year (optional)" />
      <button type="submit" className="hidden" />
    </form>
  );
}

// ─── Step 5: Outputs ─────────────────────────────────────────────────────────

function OutputConfigStep({ data, onChange }: { data: OnboardingData; onChange: (p: Partial<OnboardingData>) => void }) {
  return (
    <div className="space-y-4">
      <div className="p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40">
        <label className="text-sm font-medium text-white block mb-2">Report Recipients (comma-separated emails)</label>
        <input
          value={data.report_recipients}
          onChange={(e) => onChange({ report_recipients: e.target.value })}
          placeholder="reports@client.com, finance@client.com"
          className="w-full px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm focus:outline-none focus:ring-1 focus:ring-teal-500 placeholder:text-slate-600"
        />
      </div>

      {(
        [
          {
            key: "remittance_format" as const,
            label: "Remittance Format",
            options: [
              { value: "835", label: "835 Electronic Remittance Advice" },
              { value: "ERA", label: "ERA (PDF via portal)" },
              { value: "paper", label: "Paper / mail" },
            ] as const,
          },
          {
            key: "eligibility_feed" as const,
            label: "Eligibility Feed Method",
            options: [
              { value: "834", label: "834 EDI transaction" },
              { value: "api", label: "API integration (REST)" },
              { value: "manual", label: "Manual upload (CSV)" },
            ] as const,
          },
          {
            key: "statement_delivery" as const,
            label: "Statement Delivery",
            options: [
              { value: "email", label: "Email" },
              { value: "mail", label: "Physical mail" },
              { value: "portal", label: "Portal download only" },
            ] as const,
          },
        ]
      ).map(({ key, label, options }) => (
        <div key={key} className="p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40">
          <label className="text-sm font-medium text-white block mb-2">{label}</label>
          <div className="space-y-2">
            {options.map((opt) => (
              <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={key}
                  value={opt.value}
                  checked={data[key] === opt.value}
                  onChange={() => onChange({ [key]: opt.value } as Partial<OnboardingData>)}
                  className="accent-teal-500"
                />
                <span className="text-sm text-slate-300">{opt.label}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Step 6: Test ────────────────────────────────────────────────────────────

type TestStatus = "idle" | "running" | "pass" | "fail";

function TestValidateStep({ data }: { data: OnboardingData }) {
  const [eligibilityStatus, setEligibilityStatus] = useState<TestStatus>("idle");
  const [claimStatus, setClaimStatus] = useState<TestStatus>("idle");

  const runTest = useMutation({
    mutationFn: (type: "eligibility" | "claim") =>
      apiPost<{ passed: boolean }>(buildUrl(`${API_URLS.corePlatform}/api/v1/onboarding/test`), {
        test_type: type,
        legal_name: data.legal_name,
      }),
    onMutate: (type) => {
      if (type === "eligibility") setEligibilityStatus("running");
      else setClaimStatus("running");
    },
    onSuccess: (result, type) => {
      if (type === "eligibility") setEligibilityStatus(result.passed ? "pass" : "fail");
      else setClaimStatus(result.passed ? "pass" : "fail");
    },
    onError: (_err, type) => {
      if (type === "eligibility") setEligibilityStatus("fail");
      else setClaimStatus("fail");
    },
  });

  const allPassed = eligibilityStatus === "pass" && claimStatus === "pass";

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Run test transactions in sandbox mode before activating. Both tests must pass to proceed.
      </p>
      {(
        [
          { type: "eligibility" as const, label: "Eligibility Test (270/271)", desc: "Send test 270 inquiry; verify 271 response from payer simulator", status: eligibilityStatus },
          { type: "claim" as const, label: "Claim Test (837/835)", desc: "Submit test 837 claim; verify 835 remittance returned with zero errors", status: claimStatus },
        ]
      ).map(({ type, label, desc, status }) => (
        <div key={type} className="p-4 rounded-lg border border-ifx-border-dark bg-navy-900/40">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-3">
              {status === "running" && <span className="w-4 h-4 mt-0.5 rounded-full border-2 border-teal-400 border-t-transparent animate-spin inline-block flex-shrink-0" />}
              {status === "pass" && <CheckCircle className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />}
              {status === "fail" && <AlertTriangle className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />}
              {status === "idle" && <span className="w-4 h-4 mt-0.5 rounded-full bg-slate-700 inline-block flex-shrink-0" />}
              <div>
                <p className="text-sm font-medium text-white">{label}</p>
                <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
                {status === "fail" && <p className="text-xs text-red-400 mt-1">Test failed. Check configuration and retry.</p>}
              </div>
            </div>
            <button
              onClick={() => void runTest.mutate(type)}
              disabled={status === "running"}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                status === "pass"
                  ? "bg-green-700/20 text-green-300 border border-green-700/40"
                  : "bg-teal-600/20 text-teal-300 border border-teal-600/40 hover:bg-teal-600/30"
              )}
            >
              {status === "running" ? "Running…" : status === "pass" ? "Re-run" : "Run Test"}
            </button>
          </div>
        </div>
      ))}
      {allPassed && (
        <div className="rounded-lg border border-green-700/40 bg-green-900/10 p-3 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-green-400" />
          <p className="text-sm text-green-300">All tests passed. Ready to activate.</p>
        </div>
      )}
    </div>
  );
}

// ─── Step 7: Activate ────────────────────────────────────────────────────────

function ActivateStep({
  data,
  onChange,
}: {
  data: OnboardingData;
  onChange: (p: Partial<OnboardingData>) => void;
}) {
  const [totpCode, setTotpCode] = useState("");
  const [verifyError, setVerifyError] = useState("");

  const verifyMfa = useMutation({
    mutationFn: () =>
      apiPost<{ verified: boolean }>(buildUrl(`${API_URLS.corePlatform}/api/v1/auth/mfa/verify`), {
        code: totpCode,
      }),
    onSuccess: (result) => {
      if (result.verified) {
        onChange({ mfa_verified: true });
        setVerifyError("");
      } else {
        setVerifyError("Invalid code — try again");
      }
    },
    onError: () => setVerifyError("Verification failed"),
  });

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/40 p-4">
        <p className="text-sm font-semibold text-slate-200 mb-3">Configuration Summary</p>
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
          <div><span className="text-slate-400">Legal Name: </span><span className="text-slate-200">{data.legal_name || "—"}</span></div>
          <div><span className="text-slate-400">EIN: </span><span className="text-slate-200">{data.tax_id || "—"}</span></div>
          <div><span className="text-slate-400">Contact: </span><span className="text-slate-200">{data.contact_name || "—"}</span></div>
          <div><span className="text-slate-400">Formulary Tiers: </span><span className="text-slate-200">{data.formulary_tiers}</span></div>
          <div><span className="text-slate-400">Admin PMPM: </span><span className="text-slate-200">${data.admin_fee_pmpm}</span></div>
          <div><span className="text-slate-400">Remittance: </span><span className="text-slate-200">{data.remittance_format}</span></div>
        </div>
      </div>

      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/40 p-4">
        <div className="flex items-center gap-2 mb-3">
          <ShieldCheck className="w-4 h-4 text-teal-400" />
          <p className="text-sm font-semibold text-slate-200">MFA Verification Required</p>
        </div>
        <p className="text-xs text-slate-400 mb-4">
          Enter your TOTP code to authorize this client activation. This action provisions the tenant environment.
        </p>
        {data.mfa_verified ? (
          <div className="flex items-center gap-2 text-green-400 text-sm">
            <CheckCircle className="w-4 h-4" />
            MFA verified — submit to activate.
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="w-32 px-3 py-2 rounded-lg bg-navy-900 border border-ifx-border-dark text-white text-sm font-mono text-center focus:outline-none focus:ring-1 focus:ring-teal-500 tracking-widest"
            />
            <button
              onClick={() => void verifyMfa.mutate()}
              disabled={totpCode.length !== 6 || verifyMfa.isPending}
              className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium disabled:opacity-50 transition-colors"
            >
              {verifyMfa.isPending ? "Verifying…" : "Verify"}
            </button>
            {verifyError && <p className="text-xs text-red-400">{verifyError}</p>}
          </div>
        )}
      </div>

      {data.mfa_verified && (
        <div className="rounded-lg border border-yellow-700/30 bg-yellow-900/10 p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
          <p className="text-xs text-yellow-300">
            Activating will provision a live tenant environment for <strong>{data.legal_name}</strong>.
            All configured services will be enabled immediately.
          </p>
        </div>
      )}
    </div>
  );
}

// ─── Main Wizard ─────────────────────────────────────────────────────────────

export interface ClientOnboardingWizardProps {
  onClose?: () => void;
}

export function ClientOnboardingWizard({ onClose }: ClientOnboardingWizardProps) {
  const router = useRouter();

  const activate = useMutation({
    mutationFn: (data: OnboardingData) =>
      apiPost<{ tenant_id: string }>(buildUrl(`${API_URLS.corePlatform}/api/v1/onboarding/activate`), {
        client_details: {
          legal_name: data.legal_name, dba_name: data.dba_name, tax_id: data.tax_id, npi: data.npi,
          address_line1: data.address_line1, address_line2: data.address_line2,
          city: data.city, state: data.state, zip: data.zip,
          contact_name: data.contact_name, contact_email: data.contact_email, contact_phone: data.contact_phone,
        },
        program_config: {
          pbm_enabled: data.pbm_enabled, medical_claims_enabled: data.medical_claims_enabled,
          fwa_enabled: data.fwa_enabled, edi_enabled: data.edi_enabled, reporting_enabled: data.reporting_enabled,
          formulary_tiers: data.formulary_tiers, accumulators_enabled: data.accumulators_enabled,
          split_billing_enabled: data.split_billing_enabled,
        },
        banking: {
          account_name: data.account_name, routing_number: data.routing_number,
          account_number: data.account_number, account_type: data.account_type, bank_name: data.bank_name,
        },
        fee_rules: {
          admin_fee_pmpm: data.admin_fee_pmpm, dispensing_fee: data.dispensing_fee,
          uc_cap_pct: data.uc_cap_pct, spread_retention_pct: data.spread_retention_pct,
          max_oop_annual: data.max_oop_annual,
        },
        output_config: {
          report_recipients: data.report_recipients, remittance_format: data.remittance_format,
          eligibility_feed: data.eligibility_feed, statement_delivery: data.statement_delivery,
        },
      }),
    onSuccess: (result) => {
      router.push(`/admin/tenants/${result.tenant_id}`);
    },
  });

  const steps: WizardStepConfig<OnboardingData>[] = [
    {
      id: "client_details",
      title: "Client Details",
      description: "Legal info & contact",
      isValid: (d) => d.legal_name.length >= 2 && d.contact_email.includes("@"),
      render: ({ data, onChange, onNext }) => (
        <ClientDetailsStep data={data} onChange={onChange} onNext={onNext} />
      ),
    },
    {
      id: "program_config",
      title: "Program Config",
      description: "Enable services & features",
      render: ({ data, onChange }) => (
        <ProgramConfigStep data={data} onChange={onChange} />
      ),
    },
    {
      id: "banking",
      title: "Banking",
      description: "ACH & remittance setup",
      isValid: (d) => d.routing_number.length === 9 && d.account_number.length >= 4,
      render: ({ data, onChange, onNext }) => (
        <BankingStep data={data} onChange={onChange} onNext={onNext} />
      ),
    },
    {
      id: "fee_rules",
      title: "Fee Rules",
      description: "Admin fees & spread",
      isValid: (d) => d.admin_fee_pmpm.length > 0 && d.dispensing_fee.length > 0,
      render: ({ data, onChange, onNext }) => (
        <FeeRulesStep data={data} onChange={onChange} onNext={onNext} />
      ),
    },
    {
      id: "outputs",
      title: "Output Config",
      description: "Reports & EDI delivery",
      render: ({ data, onChange }) => (
        <OutputConfigStep data={data} onChange={onChange} />
      ),
    },
    {
      id: "test",
      title: "Test & Validate",
      description: "Eligibility & claim test",
      render: ({ data }) => <TestValidateStep data={data} />,
    },
    {
      id: "activate",
      title: "Activate",
      description: "MFA confirm & go live",
      isValid: (d) => d.mfa_verified,
      render: ({ data, onChange }) => (
        <ActivateStep data={data} onChange={onChange} />
      ),
    },
  ];

  const config: WizardConfig<OnboardingData> = {
    id: "client-onboarding",
    title: "New Client Onboarding",
    steps,
    initialData: DEFAULT_DATA,
    onComplete: (data) => void activate.mutateAsync(data),
    onCancel: onClose,
  };

  const wizard = useWizardConfig<OnboardingData>(config);

  const currentStepConfig = steps[wizard.currentStep];
  const children = currentStepConfig?.render({
    data: wizard.data,
    onChange: wizard.onChange,
    onNext: wizard.goNext,
    onBack: wizard.goBack,
  });

  return (
    <WizardContainer config={config} wizard={wizard}>
      {children}
    </WizardContainer>
  );
}
