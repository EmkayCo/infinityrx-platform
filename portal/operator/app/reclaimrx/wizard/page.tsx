"use client";

import React, { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Wizard, useWizard } from "@shared/components/wizard/index-component";
import type { LeakageCategory } from "@shared/types/reclaimrx";
import { cn } from "@shared/lib/format";

// ─── Step 1: Category ─────────────────────────────────────────────────────────

const CATEGORIES: { value: LeakageCategory; label: string; description: string }[] = [
  { value: "pharmacy_misuse", label: "Pharmacy Misuse", description: "Duplicate claims, override abuse, fake patients, copay exceeding drug cost" },
  { value: "accumulator", label: "Accumulator Programs", description: "Payer plans excluding copay assistance from patient deductible" },
  { value: "maximizer", label: "Maximizer Programs", description: "Payer plans reclassifying drug as non-essential to extract copay value" },
  { value: "three_forty_b_overlap", label: "340B Overlap", description: "Claims where 340B pricing and copay assistance both applied" },
  { value: "alternative_funding", label: "Alternative Funding", description: "Patients redirected to charity foundations away from copay programs" },
  { value: "prescriber_anomaly", label: "Prescriber Anomaly", description: "Prescribers with outlier patterns — volume, specialty mismatch, linked pharmacies" },
  { value: "patient_anomaly", label: "Patient Anomaly", description: "Suspicious enrollment or fill patterns at the patient level" },
];

function StepCategory({
  value,
  onChange,
}: {
  value: LeakageCategory | "";
  onChange: (v: LeakageCategory) => void;
}) {
  return (
    <div className="space-y-3">
      <h3 className="text-base font-semibold text-ifx-gray-900">Select Leakage Category</h3>
      <p className="text-sm text-ifx-gray-400">
        Choose the category that best describes the leakage pattern you are investigating.
      </p>
      <div className="grid grid-cols-1 gap-2 mt-4">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => onChange(cat.value)}
            className={cn(
              "text-left p-4 rounded-lg border transition-all",
              value === cat.value
                ? "border-ifx-blue bg-ifx-lavender"
                : "border-ifx-gray-100 bg-white hover:border-ifx-blue hover:bg-ifx-lavender/50"
            )}
          >
            <div className="flex items-start gap-3">
              <span
                className={cn(
                  "w-5 h-5 rounded-full border-2 flex-shrink-0 mt-0.5 flex items-center justify-center",
                  value === cat.value ? "border-ifx-blue bg-ifx-blue" : "border-ifx-gray-300"
                )}
              >
                {value === cat.value && (
                  <span className="w-2 h-2 rounded-full bg-white" />
                )}
              </span>
              <div>
                <p className="text-sm font-medium text-ifx-gray-900">{cat.label}</p>
                <p className="text-xs text-ifx-gray-400 mt-0.5">{cat.description}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Step 2: Subject Entity ───────────────────────────────────────────────────

const MOCK_ENTITIES = [
  { id: "e001", type: "pharmacy", name: "QuickScript Pharmacy", npi: "1080000001" },
  { id: "e002", type: "pharmacy", name: "BestRx Express", npi: "1080000002" },
  { id: "e003", type: "prescriber", name: "Dr. James Wilson", npi: "1234567890" },
  { id: "e004", type: "prescriber", name: "Dr. Karen O'Brien", npi: "9876543210" },
  { id: "e005", type: "patient", name: "M*** J*** (MBR-2026-0042)", npi: "" },
];

function StepSubject({
  entityId,
  onChange,
}: {
  entityId: string;
  onChange: (id: string, name: string) => void;
}) {
  const [search, setSearch] = useState("");
  const filtered = MOCK_ENTITIES.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.npi.includes(search)
  );

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Identify Subject Entity</h3>
      <input
        type="text"
        placeholder="Search by name or NPI…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full border border-ifx-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ifx-blue"
      />
      <div className="space-y-2">
        {filtered.map((entity) => (
          <button
            key={entity.id}
            onClick={() => onChange(entity.id, entity.name)}
            className={cn(
              "w-full text-left p-3 rounded-lg border transition-all",
              entityId === entity.id
                ? "border-ifx-blue bg-ifx-lavender"
                : "border-ifx-gray-100 hover:border-ifx-blue hover:bg-ifx-lavender/50"
            )}
          >
            <div className="flex items-center gap-3">
              <span className="text-xs px-2 py-0.5 rounded bg-ifx-gray-100 text-ifx-gray-400 capitalize">
                {entity.type}
              </span>
              <span className="text-sm font-medium text-ifx-gray-900">{entity.name}</span>
              {entity.npi && (
                <span className="text-xs font-mono text-ifx-gray-400">NPI {entity.npi}</span>
              )}
            </div>
          </button>
        ))}
        {filtered.length === 0 && (
          <p className="text-sm text-ifx-gray-400 text-center py-4">
            No entities match your search.
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Step 3: Flagged Claims ───────────────────────────────────────────────────

const MOCK_CLAIMS = [
  { id: "CLM-2026-0001", date: "2026-03-15", drug: "Heliozar 100mg", amount: "4200.00" },
  { id: "CLM-2026-0002", date: "2026-03-01", drug: "Heliozar 100mg", amount: "4200.00" },
  { id: "CLM-2026-0003", date: "2026-02-15", drug: "Heliozar 100mg", amount: "4150.00" },
  { id: "CLM-2026-0004", date: "2026-02-01", drug: "Nuvectra 50mg", amount: "1850.00" },
];

function StepClaims({
  selected,
  onToggle,
}: {
  selected: Set<string>;
  onToggle: (id: string) => void;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Select Flagged Claims</h3>
      <p className="text-sm text-ifx-gray-400">
        Select the claims to include as evidence in this investigation.
      </p>
      <div className="space-y-2">
        {MOCK_CLAIMS.map((claim) => (
          <label
            key={claim.id}
            className={cn(
              "flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all",
              selected.has(claim.id)
                ? "border-ifx-blue bg-ifx-lavender"
                : "border-ifx-gray-100 hover:bg-ifx-gray-50"
            )}
          >
            <input
              type="checkbox"
              checked={selected.has(claim.id)}
              onChange={() => onToggle(claim.id)}
              className="rounded border-ifx-gray-300 text-ifx-blue focus:ring-ifx-blue"
            />
            <span className="font-mono text-xs text-ifx-blue">{claim.id}</span>
            <span className="text-sm text-ifx-gray-700">{claim.drug}</span>
            <span className="text-xs text-ifx-gray-400">{claim.date}</span>
            <span className="ml-auto text-sm font-semibold text-ifx-gray-900">
              ${claim.amount}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}

// ─── Step 4: Estimate Leakage ────────────────────────────────────────────────

function StepEstimate({
  amount,
  onChange,
}: {
  amount: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Estimate Leakage Amount</h3>
      <p className="text-sm text-ifx-gray-400">
        Enter the estimated dollar amount of leakage for this investigation. Use the selected
        claims as a reference.
      </p>
      <div className="max-w-xs">
        <label className="block text-sm font-medium text-ifx-gray-700 mb-1">
          Estimated Leakage ($)
        </label>
        <div className="relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-ifx-gray-400">$</span>
          <input
            type="number"
            min="0"
            step="0.01"
            value={amount}
            onChange={(e) => onChange(e.target.value)}
            placeholder="0.00"
            className="w-full border border-ifx-gray-100 rounded-lg pl-8 pr-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ifx-blue"
          />
        </div>
      </div>
    </div>
  );
}

// ─── Step 5: Assign Analyst ───────────────────────────────────────────────────

const ANALYSTS = [
  "Priya Nair",
  "James Okafor",
  "Elena Vasquez",
  "Thomas Becker",
  "Michelle Park",
  "David Santos",
];

function StepAssign({
  analyst,
  onChange,
}: {
  analyst: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Assign Analyst</h3>
      <div className="grid grid-cols-2 gap-2">
        {ANALYSTS.map((a) => (
          <button
            key={a}
            onClick={() => onChange(a)}
            className={cn(
              "text-left p-3 rounded-lg border transition-all",
              analyst === a
                ? "border-ifx-blue bg-ifx-lavender"
                : "border-ifx-gray-100 hover:border-ifx-blue"
            )}
          >
            <p className="text-sm font-medium text-ifx-gray-700">{a}</p>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Step 6: Notes ────────────────────────────────────────────────────────────

function StepNotes({
  notes,
  onChange,
}: {
  notes: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Add Initial Notes</h3>
      <textarea
        value={notes}
        onChange={(e) => onChange(e.target.value)}
        rows={8}
        placeholder="Describe the anomaly pattern, relevant context, and any initial findings…"
        className="w-full border border-ifx-gray-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ifx-blue resize-none"
      />
    </div>
  );
}

// ─── Step 7: Review ───────────────────────────────────────────────────────────

interface ReviewData {
  category: LeakageCategory | "";
  entityName: string;
  claimCount: number;
  estimatedAmount: string;
  analyst: string;
  notes: string;
}

function StepReview({ data }: { data: ReviewData }) {
  const label = CATEGORIES.find((c) => c.value === data.category)?.label ?? data.category;

  return (
    <div className="space-y-4">
      <h3 className="text-base font-semibold text-ifx-gray-900">Review & Create</h3>
      <div className="rounded-lg border border-ifx-gray-100 divide-y divide-ifx-gray-100">
        {[
          { label: "Category", value: label },
          { label: "Subject Entity", value: data.entityName || "Not selected" },
          { label: "Claims Included", value: `${data.claimCount} claim(s)` },
          { label: "Estimated Leakage", value: data.estimatedAmount ? `$${parseFloat(data.estimatedAmount).toFixed(2)}` : "Not set" },
          { label: "Assigned To", value: data.analyst || "Unassigned" },
          { label: "Notes", value: data.notes || "None" },
        ].map(({ label: rowLabel, value }) => (
          <div key={rowLabel} className="flex gap-4 px-4 py-3">
            <span className="text-sm text-ifx-gray-400 w-40 flex-shrink-0">{rowLabel}</span>
            <span className="text-sm text-ifx-gray-700">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Wizard Page ─────────────────────────────────────────────────────────

const WIZARD_STEPS = [
  { id: "category", title: "Category", description: "Select leakage type" },
  { id: "subject", title: "Subject Entity", description: "Pharmacy, prescriber, or patient" },
  { id: "claims", title: "Flagged Claims", description: "Select evidence claims" },
  { id: "estimate", title: "Estimate Leakage", description: "Dollar impact" },
  { id: "assign", title: "Assign Analyst", description: "Who will investigate" },
  { id: "notes", title: "Initial Notes", description: "Context and findings" },
  { id: "review", title: "Review & Create", description: "Confirm and submit" },
];

export default function CaseWizardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCategory = (searchParams.get("category") as LeakageCategory | null) ?? "";

  const { currentStep, setStep, isLastStep } = useWizard(
    WIZARD_STEPS.length,
    "case-wizard"
  );

  const [category, setCategory] = useState<LeakageCategory | "">(initialCategory);
  const [entityId, setEntityId] = useState("");
  const [entityName, setEntityName] = useState("");
  const [selectedClaims, setSelectedClaims] = useState<Set<string>>(new Set());
  const [estimatedAmount, setEstimatedAmount] = useState("");
  const [analyst, setAnalyst] = useState("");
  const [notes, setNotes] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const isNextDisabled =
    (currentStep === 0 && !category) ||
    (currentStep === 1 && !entityId) ||
    (currentStep === 2 && selectedClaims.size === 0) ||
    (currentStep === 3 && !estimatedAmount);

  const handleToggleClaim = (id: string) => {
    setSelectedClaims((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSubmit = async () => {
    // In production, this would POST to the API
    await new Promise((resolve) => setTimeout(resolve, 800));
    setSubmitted(true);
    return true;
  };

  if (submitted) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-12 space-y-6">
        <CheckCircle2 className="w-16 h-16 text-green-500" />
        <h2 className="text-2xl font-bold text-ifx-gray-900">Investigation Created</h2>
        <p className="text-ifx-gray-400 text-center max-w-md">
          Your case has been opened and assigned. The analyst will be notified and the
          investigation is now in the queue.
        </p>
        <div className="flex gap-3">
          <button
            onClick={() => router.push("/reclaimrx/investigations")}
            className="px-5 py-2 rounded-lg bg-ifx-navy text-white text-sm font-medium hover:bg-ifx-navy-dark transition-colors"
          >
            View Investigations
          </button>
          <button
            onClick={() => router.push("/reclaimrx")}
            className="px-5 py-2 rounded-lg border border-ifx-gray-100 text-sm text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 h-full">
      <Wizard
        steps={WIZARD_STEPS}
        currentStep={currentStep}
        onStepChange={setStep}
        title="New Investigation — Case Wizard"
        onClose={() => router.push("/reclaimrx/investigations")}
        isNextDisabled={isNextDisabled}
        isLastStep={isLastStep}
        nextLabel={isLastStep ? "Create Investigation" : undefined}
        onNext={isLastStep ? handleSubmit : undefined}
      >
        {currentStep === 0 && (
          <StepCategory value={category} onChange={setCategory} />
        )}
        {currentStep === 1 && (
          <StepSubject
            entityId={entityId}
            onChange={(id, name) => {
              setEntityId(id);
              setEntityName(name);
            }}
          />
        )}
        {currentStep === 2 && (
          <StepClaims selected={selectedClaims} onToggle={handleToggleClaim} />
        )}
        {currentStep === 3 && (
          <StepEstimate amount={estimatedAmount} onChange={setEstimatedAmount} />
        )}
        {currentStep === 4 && (
          <StepAssign analyst={analyst} onChange={setAnalyst} />
        )}
        {currentStep === 5 && (
          <StepNotes notes={notes} onChange={setNotes} />
        )}
        {currentStep === 6 && (
          <StepReview
            data={{
              category,
              entityName,
              claimCount: selectedClaims.size,
              estimatedAmount,
              analyst,
              notes,
            }}
          />
        )}
      </Wizard>
    </div>
  );
}
