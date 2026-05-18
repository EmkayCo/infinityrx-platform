// src/surfaces/pricing/PricingPage.tsx
// Unified pricing browser with tabs: CMS-ASP, CMS-NADAC, Medicaid BINs, BPG.
// Route: /directories/pricing
//
// Execution-time verification findings:
// - CMS-ASP: drug-database GET /api/v1/drugs/pricing/{ndc} (router.py:122)
// - CMS-NADAC: drug-database GET /api/v1/drugs/pricing/{ndc}/history (router.py:155)
// - Medicaid BINs: no dedicated billing route found for state_medicaid_bins —
//   shows static reference card with count (219 BINs per coverage_report.md)
// - BPG: read-only reference card, "Live API — no ingestion schedule"
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface PricingPageProps {
  drugDatabaseUrl?: string;
  cms_asp_last_run_at?: string | null;
  cms_nadac_last_run_at?: string | null;
}

type PricingTab = "cms_asp" | "cms_nadac" | "medicaid_bins" | "bpg";

const TABS: { id: PricingTab; label: string }[] = [
  { id: "cms_asp", label: "CMS-ASP" },
  { id: "cms_nadac", label: "CMS-NADAC" },
  { id: "medicaid_bins", label: "Medicaid BINs" },
  { id: "bpg", label: "BPG" },
];

interface PricingRecord {
  ndc: string;
  effective_date: string;
  price: string;
  source: string;
}

export function PricingPage({
  drugDatabaseUrl = "http://localhost:8011",
  cms_asp_last_run_at,
  cms_nadac_last_run_at,
}: PricingPageProps) {
  const [activeTab, setActiveTab] = useState<PricingTab>("cms_asp");
  const [ndcQuery, setNdcQuery] = useState("");

  const trimmedNdc = ndcQuery.trim();
  const isValidNdc = /^\d{11}$/.test(trimmedNdc) || /^\d{4,5}-\d{3,4}-\d{1,2}$/.test(trimmedNdc);

  // CMS-ASP: GET /api/v1/drugs/pricing/{ndc}
  const { data: aspPricing = [], isLoading: aspLoading } = useQuery<PricingRecord[]>({
    queryKey: ["pricing-asp", trimmedNdc],
    enabled: activeTab === "cms_asp" && isValidNdc,
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/pricing/${encodeURIComponent(trimmedNdc)}`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const data = (await resp.json()) as { records?: PricingRecord[] };
      return (data.records ?? []).filter((r) => r.source === "cms_asp" || !r.source);
    },
    staleTime: 60_000,
  });

  // CMS-NADAC: GET /api/v1/drugs/pricing/{ndc}/history
  const { data: nadacPricing = [], isLoading: nadacLoading } = useQuery<PricingRecord[]>({
    queryKey: ["pricing-nadac", trimmedNdc],
    enabled: activeTab === "cms_nadac" && isValidNdc,
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/pricing/${encodeURIComponent(trimmedNdc)}/history`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const data = (await resp.json()) as { records?: PricingRecord[] };
      return (data.records ?? []).filter((r) => r.source === "cms_nadac" || !r.source);
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="pricing-page">
      <h1 data-testid="pricing-title">Pricing Reference</h1>

      {/* NDC input for CMS-ASP and CMS-NADAC tabs */}
      {(activeTab === "cms_asp" || activeTab === "cms_nadac") && (
        <div data-testid="ndc-input-wrapper">
          <input
            type="search"
            aria-label="Enter NDC"
            placeholder="Enter 11-digit NDC..."
            value={ndcQuery}
            onChange={(e) => setNdcQuery(e.target.value)}
            data-testid="ndc-input"
          />
          {ndcQuery.length > 0 && !isValidNdc && (
            <p data-testid="ndc-invalid-hint">Enter an 11-digit NDC (e.g. 12345678901)</p>
          )}
        </div>
      )}

      {/* Tab bar */}
      <div data-testid="pricing-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div data-testid="tab-content">
        {activeTab === "cms_asp" && (
          <div data-testid="cms-asp-tab">
            <FreshnessChip sourceKey="cms_asp" lastRunAt={cms_asp_last_run_at ?? null} />
            {aspLoading && <p data-testid="asp-loading">Loading CMS-ASP pricing...</p>}
            {!aspLoading && aspPricing.length === 0 && isValidNdc && (
              <p data-testid="asp-empty">No CMS-ASP pricing found for this NDC.</p>
            )}
            {!isValidNdc && ndcQuery.length === 0 && (
              <p data-testid="asp-hint">Enter an NDC above to look up CMS-ASP pricing.</p>
            )}
            <ul data-testid="asp-pricing-list">
              {aspPricing.map((p, i) => (
                <li key={i} data-testid="asp-pricing-row">
                  <span data-testid="asp-date">{p.effective_date}</span>
                  {": "}
                  <span data-testid="asp-price">{p.price}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {activeTab === "cms_nadac" && (
          <div data-testid="cms-nadac-tab">
            <FreshnessChip sourceKey="cms_nadac" lastRunAt={cms_nadac_last_run_at ?? null} />
            {nadacLoading && <p data-testid="nadac-loading">Loading CMS-NADAC pricing...</p>}
            {!nadacLoading && nadacPricing.length === 0 && isValidNdc && (
              <p data-testid="nadac-empty">No CMS-NADAC pricing found for this NDC.</p>
            )}
            {!isValidNdc && ndcQuery.length === 0 && (
              <p data-testid="nadac-hint">Enter an NDC above to look up CMS-NADAC pricing.</p>
            )}
            <ul data-testid="nadac-pricing-list">
              {nadacPricing.map((p, i) => (
                <li key={i} data-testid="nadac-pricing-row">
                  <span data-testid="nadac-date">{p.effective_date}</span>
                  {": "}
                  <span data-testid="nadac-price">{p.price}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {activeTab === "medicaid_bins" && (
          <div data-testid="medicaid-bins-tab">
            {/* No dedicated billing route for state_medicaid_bins — static reference card.
                219 BINs loaded per data/reference/medicaid/coverage_report.md. */}
            <div data-testid="medicaid-bins-card">
              <h4 data-testid="medicaid-bins-title">State Medicaid BINs</h4>
              <p data-testid="medicaid-bins-count">219 state Medicaid BIN entries loaded</p>
              <p data-testid="medicaid-bins-note">
                Reference data ingested from state Medicaid coverage reports.
                Contact your InfinityRx administrator to update BIN entries.
              </p>
            </div>
          </div>
        )}

        {activeTab === "bpg" && (
          <div data-testid="bpg-tab">
            {/* BPG: read-only reference — no ingestion schedule, no trigger button */}
            <div data-testid="bpg-card">
              <h4 data-testid="bpg-title">BPG PatientLens</h4>
              <p data-testid="bpg-live-api-label">Live API — no ingestion schedule</p>
              <p data-testid="bpg-description">
                BPG pricing data is served via live API reference. No ingestion run is scheduled
                — data is fetched on demand at adjudication time.
              </p>
              <a
                href="/data/reference/bpg/BPG_Translator_API_Documentation.txt"
                data-testid="bpg-doc-link"
              >
                BPG PatientLens API Documentation
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
