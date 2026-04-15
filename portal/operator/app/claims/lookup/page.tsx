"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Search, FileSearch } from "lucide-react";
import { apiGet } from "@shared/lib/api-client";
import { StatusBadge } from "@/components/ui/status-badge";

interface MockClaim {
  id: string;
  fill_date?: string;
  status?: string;
  pharmacy_name?: string;
  pharmacy_npi?: string;
  drug_name?: string;
  drug_ndc?: string;
  member_id?: string;
  auth_number?: string;
  rx_number?: string;
  ingredient_cost?: string;
  dispensing_fee?: string;
  copay?: string;
  plan_paid?: string;
  total_paid?: string;
  client_name?: string;
  program_name?: string;
}

type SearchField = "claim_id" | "auth_number" | "rx_number";

const SEARCH_FIELDS: { id: SearchField; label: string; placeholder: string }[] = [
  { id: "claim_id", label: "Claim ID", placeholder: "e.g. a1b2c3d4-e5f6-…" },
  { id: "auth_number", label: "Auth #", placeholder: "e.g. AUTH-20260001" },
  { id: "rx_number", label: "Rx #", placeholder: "e.g. 7890123" },
];

export default function ClaimLookupPage() {
  const router = useRouter();
  const [searchField, setSearchField] = useState<SearchField>("claim_id");
  const [searchValue, setSearchValue] = useState("");
  const [submittedValue, setSubmittedValue] = useState("");
  const [submittedField, setSubmittedField] = useState<SearchField>("claim_id");

  const { data: claim, isLoading, error } = useQuery<MockClaim>({
    queryKey: ["claim-lookup", submittedField, submittedValue],
    queryFn: () => apiGet<MockClaim>(`/billing/v1/claims/${encodeURIComponent(submittedValue)}`),
    enabled: !!submittedValue,
    retry: false,
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = searchValue.trim();
    if (!trimmed) return;
    setSubmittedValue(trimmed);
    setSubmittedField(searchField);
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          Claims
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Claim Lookup</h1>
        <p className="mt-1 text-sm text-ifx-gray-400">
          Find a specific claim by Claim ID, authorization number, or prescription number.
        </p>
      </header>

      {/* Search card */}
      <div className="rounded-lg bg-white ifx-card-shadow p-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          {/* Field selector */}
          <div className="flex gap-2">
            {SEARCH_FIELDS.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setSearchField(f.id)}
                className={[
                  "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                  searchField === f.id
                    ? "bg-ifx-navy text-white"
                    : "border border-ifx-gray-100 bg-white text-ifx-gray-700 hover:bg-ifx-gray-50",
                ].join(" ")}
              >
                Search by {f.label}
              </button>
            ))}
          </div>

          {/* Input + button */}
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ifx-gray-400" />
              <input
                type="text"
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                placeholder={
                  SEARCH_FIELDS.find((f) => f.id === searchField)?.placeholder ?? "Enter value"
                }
                className="w-full rounded-md border border-ifx-gray-100 bg-white py-2 pl-9 pr-3 text-sm text-ifx-gray-700 placeholder:text-ifx-gray-400 focus:border-ifx-blue focus:outline-none focus:ring-2 focus:ring-ifx-blue/20"
              />
            </div>
            <button
              type="submit"
              disabled={!searchValue.trim()}
              className="inline-flex items-center gap-2 rounded-md bg-ifx-navy px-4 py-2 text-sm font-medium text-white hover:bg-ifx-navy-dark disabled:opacity-40 transition-colors"
            >
              <FileSearch className="h-4 w-4" />
              Look Up
            </button>
          </div>
        </form>
      </div>

      {/* Results */}
      {isLoading && (
        <div className="h-32 rounded-lg bg-white ifx-card-shadow animate-pulse" />
      )}

      {error && submittedValue && (
        <div className="rounded-lg border border-ifx-error/20 bg-ifx-error-light p-4 text-sm text-ifx-error-text">
          No claim found matching {SEARCH_FIELDS.find((f) => f.id === submittedField)?.label}{" "}
          <span className="font-mono font-semibold">{submittedValue}</span>. Verify the value and try again.
        </div>
      )}

      {claim && !error && (
        <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
          <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-bold text-ifx-gray-900">
                {claim.auth_number ? `Auth #${claim.auth_number}` : `Claim #${claim.id.slice(0, 8)}`}
              </h2>
              {claim.status && <StatusBadge status={claim.status} />}
            </div>
            <button
              type="button"
              onClick={() => router.push(`/claims/${claim.id}`)}
              className="rounded-md bg-ifx-navy px-3 py-1.5 text-xs font-medium text-white hover:bg-ifx-navy-dark transition-colors"
            >
              View Full Detail
            </button>
          </header>

          <div className="grid grid-cols-2 gap-4 p-4 sm:grid-cols-3 lg:grid-cols-4">
            {[
              { label: "Member ID", value: claim.member_id },
              { label: "Drug", value: claim.drug_name },
              { label: "NDC", value: claim.drug_ndc },
              { label: "Pharmacy", value: claim.pharmacy_name },
              { label: "NPI", value: claim.pharmacy_npi },
              { label: "Fill Date", value: claim.fill_date ? new Date(claim.fill_date).toLocaleDateString("en-US") : "—" },
              { label: "Client", value: claim.client_name },
              { label: "Program", value: claim.program_name },
              { label: "Ingredient Cost", value: claim.ingredient_cost ? `$${Number(claim.ingredient_cost).toFixed(2)}` : "—" },
              { label: "Dispensing Fee", value: claim.dispensing_fee ? `$${Number(claim.dispensing_fee).toFixed(2)}` : "—" },
              { label: "Copay", value: claim.copay ? `$${Number(claim.copay).toFixed(2)}` : "—" },
              { label: "Plan Paid", value: claim.plan_paid ? `$${Number(claim.plan_paid).toFixed(2)}` : "—" },
            ].map(({ label, value }) => (
              <div key={label} className="flex flex-col gap-1">
                <span className="text-[11px] font-medium uppercase tracking-wider text-ifx-gray-400">
                  {label}
                </span>
                <span className="text-sm font-medium text-ifx-gray-900">{value ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick tips */}
      {!submittedValue && (
        <div className="rounded-lg border border-ifx-gray-100 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-ifx-gray-900">Tips</h3>
          <ul className="space-y-1 text-sm text-ifx-gray-400">
            <li>· Claim ID is the full UUID (e.g. <span className="font-mono">a1b2c3d4-…</span>)</li>
            <li>· Auth # is the authorization number assigned at adjudication</li>
            <li>· Rx # is the prescription number from the pharmacy system</li>
            <li>· For bulk search, use the <a href="/claims" className="text-ifx-blue hover:underline">Claims Explorer</a> with filters</li>
          </ul>
        </div>
      )}
    </div>
  );
}
