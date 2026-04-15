"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, X, CheckCircle } from "lucide-react";
import { apiPost } from "@shared/lib/api-client";

interface FormSection {
  id: string;
  title: string;
}

const SECTIONS: FormSection[] = [
  { id: "patient", title: "Patient Information" },
  { id: "provider", title: "Provider Information" },
  { id: "claim", title: "Claim Information" },
  { id: "financial", title: "Financial Information" },
];

interface FieldProps {
  label: string;
  id: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
  span?: boolean;
  value: string;
  onChange: (v: string) => void;
  options?: { value: string; label: string }[];
}

function Field({ label, id, type = "text", required, placeholder, span, value, onChange, options }: FieldProps) {
  return (
    <div className={span ? "sm:col-span-2" : ""}>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-ifx-gray-700">
        {label}
        {required && <span className="ml-0.5 text-ifx-error">*</span>}
      </label>
      {options ? (
        <select
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full rounded-md border border-ifx-gray-100 bg-white px-3 py-2 text-sm text-ifx-gray-700 focus:border-ifx-blue focus:outline-none focus:ring-2 focus:ring-ifx-blue/20"
        >
          <option value="">— Select —</option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          id={id}
          type={type}
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          required={required}
          className="w-full rounded-md border border-ifx-gray-100 bg-white px-3 py-2 text-sm text-ifx-gray-700 placeholder:text-ifx-gray-400 focus:border-ifx-blue focus:outline-none focus:ring-2 focus:ring-ifx-blue/20"
        />
      )}
    </div>
  );
}

type FormData = Record<string, string>;

const INITIAL_FORM: FormData = {
  // Patient
  cardholder_id: "",
  first_name: "",
  last_name: "",
  dob: "",
  sex: "",
  address: "",
  city: "",
  state: "",
  zip: "",
  phone: "",
  email: "",
  mrn: "",
  // Provider
  billing_npi: "",
  tax_id: "",
  billing_name: "",
  billing_address: "",
  billing_phone: "",
  billing_fax: "",
  billing_email: "",
  service_npi: "",
  service_name: "",
  service_address: "",
  // Claim
  rx_number: "",
  claim_type: "pharmacy",
  occ: "",
  group_id: "",
  bin: "",
  insurance_type: "",
  insured_id: "",
  policy_group: "",
  plan_name: "",
  fill_number: "",
  date_of_service: "",
  place_of_service: "",
  emergency_indicator: "no",
  ndc: "",
  drug_name: "",
  cpt_code: "",
  diagnosis_codes: "",
  units: "",
  days_supply: "",
  quantity: "",
  // Financial
  ingredient_cost: "",
  dispensing_fee: "",
  sales_tax: "",
  copay: "",
  patient_paid: "",
  plan_paid: "",
  pos_adjustment: "",
  debit_card_amount: "",
  transaction_fee: "",
  incentive_fee: "",
};

export default function ManualClaimsPage() {
  const router = useRouter();
  const [activeSection, setActiveSection] = useState("patient");
  const [formData, setFormData] = useState<FormData>(INITIAL_FORM);
  const [attachments, setAttachments] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setField(key: string, value: string) {
    setFormData((prev) => ({ ...prev, [key]: value }));
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) {
      setAttachments((prev) => [...prev, ...Array.from(e.target.files!)]);
    }
  }

  function removeAttachment(index: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== index));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiPost("/api/v1/claims/manual", { ...formData, attachments: attachments.map((f) => f.name) });
      setSubmitted(true);
    } catch {
      setError("Failed to submit claim. Please check required fields and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div className="flex flex-col gap-6">
        <header>
          <h1 className="text-2xl font-bold text-ifx-gray-900">Manual Claims</h1>
        </header>
        <div className="flex flex-col items-center gap-4 rounded-lg bg-white ifx-card-shadow p-12 text-center">
          <CheckCircle className="h-12 w-12 text-ifx-success" />
          <h2 className="text-lg font-bold text-ifx-gray-900">Claim Submitted</h2>
          <p className="text-sm text-ifx-gray-400">
            The manual claim has been submitted for processing. It will appear in the Claims Explorer shortly.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => { setFormData(INITIAL_FORM); setAttachments([]); setSubmitted(false); }}
              className="rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
            >
              Enter Another Claim
            </button>
            <button
              type="button"
              onClick={() => router.push("/claims")}
              className="rounded-md bg-ifx-navy px-4 py-2 text-sm font-medium text-white hover:bg-ifx-navy-dark transition-colors"
            >
              Back to Claims Explorer
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
            Claims
          </span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Manual Claims</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">
            Enter a manual claim with full patient, provider, and financial information.
          </p>
        </div>
      </header>

      <div className="flex gap-6">
        {/* Section nav */}
        <nav className="hidden w-40 shrink-0 md:block">
          <ul className="sticky top-4 space-y-1">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  onClick={() => setActiveSection(s.id)}
                  className={[
                    "w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
                    activeSection === s.id
                      ? "bg-ifx-navy text-white"
                      : "text-ifx-gray-700 hover:bg-ifx-gray-50",
                  ].join(" ")}
                >
                  {s.title}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex min-w-0 flex-1 flex-col gap-6">
          {/* Patient Information */}
          <div id="patient" className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <header className="border-b border-ifx-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">Patient Information</h2>
            </header>
            <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
              <Field label="Cardholder ID" id="cardholder_id" required placeholder="CHD-0001" value={formData.cardholder_id} onChange={(v) => setField("cardholder_id", v)} />
              <Field label="MRN / Account #" id="mrn" placeholder="MRN-12345" value={formData.mrn} onChange={(v) => setField("mrn", v)} />
              <Field label="First Name" id="first_name" required value={formData.first_name} onChange={(v) => setField("first_name", v)} />
              <Field label="Last Name" id="last_name" required value={formData.last_name} onChange={(v) => setField("last_name", v)} />
              <Field label="Date of Birth" id="dob" type="date" required value={formData.dob} onChange={(v) => setField("dob", v)} />
              <Field label="Sex" id="sex" options={[{ value: "M", label: "Male" }, { value: "F", label: "Female" }, { value: "U", label: "Unknown" }]} value={formData.sex} onChange={(v) => setField("sex", v)} />
              <Field label="Address" id="address" span placeholder="123 Main St" value={formData.address} onChange={(v) => setField("address", v)} />
              <Field label="City" id="city" value={formData.city} onChange={(v) => setField("city", v)} />
              <Field label="State" id="state" placeholder="TX" value={formData.state} onChange={(v) => setField("state", v)} />
              <Field label="ZIP" id="zip" placeholder="78701" value={formData.zip} onChange={(v) => setField("zip", v)} />
              <Field label="Phone" id="phone" type="tel" placeholder="(512) 555-0100" value={formData.phone} onChange={(v) => setField("phone", v)} />
              <Field label="Email" id="email" type="email" value={formData.email} onChange={(v) => setField("email", v)} />
            </div>
          </div>

          {/* Provider Information */}
          <div id="provider" className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <header className="border-b border-ifx-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">Provider Information</h2>
            </header>
            <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
              <Field label="Billing Provider NPI" id="billing_npi" required placeholder="1234567890" value={formData.billing_npi} onChange={(v) => setField("billing_npi", v)} />
              <Field label="Federal Tax ID" id="tax_id" placeholder="12-3456789" value={formData.tax_id} onChange={(v) => setField("tax_id", v)} />
              <Field label="Billing Provider Name" id="billing_name" span value={formData.billing_name} onChange={(v) => setField("billing_name", v)} />
              <Field label="Billing Address" id="billing_address" span value={formData.billing_address} onChange={(v) => setField("billing_address", v)} />
              <Field label="Billing Phone" id="billing_phone" type="tel" value={formData.billing_phone} onChange={(v) => setField("billing_phone", v)} />
              <Field label="Billing Fax" id="billing_fax" type="tel" value={formData.billing_fax} onChange={(v) => setField("billing_fax", v)} />
              <Field label="Billing Email" id="billing_email" type="email" span value={formData.billing_email} onChange={(v) => setField("billing_email", v)} />
              <Field label="Service Provider NPI" id="service_npi" placeholder="0987654321" value={formData.service_npi} onChange={(v) => setField("service_npi", v)} />
              <Field label="Service Provider Name" id="service_name" value={formData.service_name} onChange={(v) => setField("service_name", v)} />
              <Field label="Service Provider Address" id="service_address" span value={formData.service_address} onChange={(v) => setField("service_address", v)} />
            </div>
          </div>

          {/* Claim Information */}
          <div id="claim" className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <header className="border-b border-ifx-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">Claim Information</h2>
            </header>
            <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
              <Field label="Rx Number" id="rx_number" required placeholder="7890123" value={formData.rx_number} onChange={(v) => setField("rx_number", v)} />
              <Field label="Claim Type" id="claim_type" options={[{ value: "pharmacy", label: "Pharmacy" }, { value: "medical", label: "Medical" }, { value: "compound", label: "Compound" }]} value={formData.claim_type} onChange={(v) => setField("claim_type", v)} />
              <Field label="Other Coverage Code (OCC)" id="occ" options={[{ value: "00", label: "00 - Not Specified" }, { value: "01", label: "01 - Carrier" }, { value: "02", label: "02 - Medicare" }, { value: "03", label: "03 - Medicaid" }]} value={formData.occ} onChange={(v) => setField("occ", v)} />
              <Field label="IFX Group ID" id="group_id" placeholder="GRP-4821" value={formData.group_id} onChange={(v) => setField("group_id", v)} />
              <Field label="BIN / Other Payer ID" id="bin" placeholder="610415" value={formData.bin} onChange={(v) => setField("bin", v)} />
              <Field label="Insurance Type" id="insurance_type" options={[{ value: "commercial", label: "Commercial" }, { value: "medicare", label: "Medicare" }, { value: "medicaid", label: "Medicaid" }, { value: "self", label: "Self-Pay" }]} value={formData.insurance_type} onChange={(v) => setField("insurance_type", v)} />
              <Field label="Insured&apos;s ID" id="insured_id" value={formData.insured_id} onChange={(v) => setField("insured_id", v)} />
              <Field label="Policy Group" id="policy_group" value={formData.policy_group} onChange={(v) => setField("policy_group", v)} />
              <Field label="Plan Name" id="plan_name" span value={formData.plan_name} onChange={(v) => setField("plan_name", v)} />
              <Field label="Fill Number" id="fill_number" type="number" placeholder="1" value={formData.fill_number} onChange={(v) => setField("fill_number", v)} />
              <Field label="Date of Service" id="date_of_service" type="date" required value={formData.date_of_service} onChange={(v) => setField("date_of_service", v)} />
              <Field label="Place of Service" id="place_of_service" options={[{ value: "01", label: "01 - Pharmacy" }, { value: "11", label: "11 - Office" }, { value: "21", label: "21 - Inpatient Hospital" }, { value: "22", label: "22 - Outpatient Hospital" }]} value={formData.place_of_service} onChange={(v) => setField("place_of_service", v)} />
              <Field label="Emergency Indicator" id="emergency_indicator" options={[{ value: "no", label: "No" }, { value: "yes", label: "Yes" }]} value={formData.emergency_indicator} onChange={(v) => setField("emergency_indicator", v)} />
              <Field label="NDC" id="ndc" required placeholder="00069-0260-68" value={formData.ndc} onChange={(v) => setField("ndc", v)} />
              <Field label="Drug Name" id="drug_name" required span value={formData.drug_name} onChange={(v) => setField("drug_name", v)} />
              <Field label="CPT / HCPCS / JCode" id="cpt_code" placeholder="J0000" value={formData.cpt_code} onChange={(v) => setField("cpt_code", v)} />
              <Field label="Diagnosis Codes" id="diagnosis_codes" placeholder="I10, E11.9" value={formData.diagnosis_codes} onChange={(v) => setField("diagnosis_codes", v)} />
              <Field label="Units" id="units" type="number" placeholder="1" value={formData.units} onChange={(v) => setField("units", v)} />
              <Field label="Days Supply" id="days_supply" type="number" required placeholder="30" value={formData.days_supply} onChange={(v) => setField("days_supply", v)} />
              <Field label="Quantity" id="quantity" type="number" required placeholder="30" value={formData.quantity} onChange={(v) => setField("quantity", v)} />
            </div>
          </div>

          {/* Financial Information */}
          <div id="financial" className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <header className="border-b border-ifx-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">Financial Information</h2>
            </header>
            <div className="grid grid-cols-1 gap-4 p-4 sm:grid-cols-2">
              <Field label="Ingredient Cost" id="ingredient_cost" type="number" placeholder="0.00" value={formData.ingredient_cost} onChange={(v) => setField("ingredient_cost", v)} />
              <Field label="Dispensing Fee" id="dispensing_fee" type="number" placeholder="0.00" value={formData.dispensing_fee} onChange={(v) => setField("dispensing_fee", v)} />
              <Field label="Sales Tax" id="sales_tax" type="number" placeholder="0.00" value={formData.sales_tax} onChange={(v) => setField("sales_tax", v)} />
              <Field label="Copay Amount" id="copay" type="number" placeholder="0.00" value={formData.copay} onChange={(v) => setField("copay", v)} />
              <Field label="Patient Paid" id="patient_paid" type="number" placeholder="0.00" value={formData.patient_paid} onChange={(v) => setField("patient_paid", v)} />
              <Field label="Plan Paid" id="plan_paid" type="number" placeholder="0.00" value={formData.plan_paid} onChange={(v) => setField("plan_paid", v)} />
              <Field label="POS Adjustment" id="pos_adjustment" type="number" placeholder="0.00" value={formData.pos_adjustment} onChange={(v) => setField("pos_adjustment", v)} />
              <Field label="Debit Card Amount" id="debit_card_amount" type="number" placeholder="0.00" value={formData.debit_card_amount} onChange={(v) => setField("debit_card_amount", v)} />
              <Field label="Transaction Fee" id="transaction_fee" type="number" placeholder="0.00" value={formData.transaction_fee} onChange={(v) => setField("transaction_fee", v)} />
              <Field label="Incentive Fee" id="incentive_fee" type="number" placeholder="0.00" value={formData.incentive_fee} onChange={(v) => setField("incentive_fee", v)} />
            </div>
          </div>

          {/* Attachments */}
          <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <header className="border-b border-ifx-gray-100 px-4 py-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">Attachments</h2>
            </header>
            <div className="p-4">
              <label
                htmlFor="attachments"
                className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-ifx-gray-100 p-8 text-center hover:border-ifx-blue/40 hover:bg-ifx-lavender/30 transition-colors"
              >
                <Upload className="h-8 w-8 text-ifx-gray-400" />
                <span className="text-sm font-medium text-ifx-gray-700">
                  Click to upload or drag and drop
                </span>
                <span className="text-xs text-ifx-gray-400">PDF, JPEG, PNG up to 10 MB</span>
                <input
                  id="attachments"
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </label>

              {attachments.length > 0 && (
                <ul className="mt-3 divide-y divide-ifx-gray-100">
                  {attachments.map((file, i) => (
                    <li key={`${file.name}-${i}`} className="flex items-center gap-3 py-2 text-sm">
                      <span className="flex-1 truncate text-ifx-gray-700">{file.name}</span>
                      <span className="text-ifx-gray-400">{(file.size / 1024).toFixed(0)} KB</span>
                      <button
                        type="button"
                        onClick={() => removeAttachment(i)}
                        className="text-ifx-gray-400 hover:text-ifx-error transition-colors"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-md border border-ifx-error/20 bg-ifx-error-light px-4 py-3 text-sm text-ifx-error-text">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => router.push("/claims")}
              className="rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-ifx-navy px-6 py-2 text-sm font-medium text-white hover:bg-ifx-navy-dark disabled:opacity-50 transition-colors"
            >
              {submitting ? "Submitting…" : "Submit Claim"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
