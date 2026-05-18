// src/surfaces/drugs/DrugDetailPage.tsx
// Drug detail page — wraps existing portal detail with Plan A primitives.
// Tabs: Pricing (CMS-ASP + CMS-NADAC), REMS, Shortages, Interactions (B9 pending),
// Formulary (B9 pending), RxNorm cross-link.
// BPG pricing shown as static read-only "Live API — no ingestion schedule" label.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ProvenanceBadge } from "../../components/ProvenanceBadge.js";
import { FreshnessChip } from "../../components/FreshnessChip.js";
import { B9PendingBanner } from "../../components/B9PendingBanner.js";

export interface DrugDetailPageProps {
  ndc: string;
  drugDatabaseUrl?: string;
  /** ISO date of last fda_ndc ingestion run */
  fda_ndc_last_run_at?: string | null;
}

type DrugTab = "pricing" | "rems" | "shortages" | "interactions" | "formulary";

const TABS: { id: DrugTab; label: string }[] = [
  { id: "pricing", label: "Pricing" },
  { id: "rems", label: "REMS" },
  { id: "shortages", label: "Shortages" },
  { id: "interactions", label: "Interactions" },
  { id: "formulary", label: "Formulary" },
];

interface DrugRecord {
  ndc: string;
  proprietary_name?: string | null;
  nonproprietary_name?: string | null;
  strength?: string | null;
  dosage_form?: string | null;
  source_date?: string | null;
  run_id?: string | null;
  rems_program?: string | null;
}

interface PricingRecord {
  effective_date: string;
  price: string;
  source: string;
}

interface RemsRecord {
  program_name: string;
  required: boolean;
  description?: string | null;
}

interface ShortageRecord {
  status: string;
  reason?: string | null;
  updated_at?: string | null;
}

export function DrugDetailPage({
  ndc,
  drugDatabaseUrl = "http://localhost:8011",
  fda_ndc_last_run_at,
}: DrugDetailPageProps) {
  const [activeTab, setActiveTab] = useState<DrugTab>("pricing");

  const { data: drug, isLoading } = useQuery<DrugRecord>({
    queryKey: ["drug-detail", ndc],
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/lookup/${encodeURIComponent(ndc)}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`drug lookup failed: ${resp.status}`);
      return (await resp.json()) as DrugRecord;
    },
    staleTime: 60_000,
  });

  // Pricing: GET /api/v1/drugs/pricing/{ndc} (line 122 — CMS-ASP)
  const { data: pricing = [] } = useQuery<PricingRecord[]>({
    queryKey: ["drug-pricing", ndc],
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/pricing/${encodeURIComponent(ndc)}`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const data = (await resp.json()) as { records?: PricingRecord[] };
      return data.records ?? [];
    },
    enabled: activeTab === "pricing",
    staleTime: 60_000,
  });

  // REMS: GET /api/v1/drugs/rems/{ndc} (router.py line 307)
  const { data: rems } = useQuery<RemsRecord | null>({
    queryKey: ["drug-rems", ndc],
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/rems/${encodeURIComponent(ndc)}`;
      const resp = await fetch(url);
      if (!resp.ok) return null;
      return (await resp.json()) as RemsRecord;
    },
    enabled: activeTab === "rems",
    staleTime: 60_000,
  });

  // Shortages: GET /api/v1/drugs/shortages/{ndc} (router.py line 332)
  const { data: shortage } = useQuery<ShortageRecord | null>({
    queryKey: ["drug-shortage", ndc],
    queryFn: async () => {
      const url = `${drugDatabaseUrl}/api/v1/drugs/shortages/${encodeURIComponent(ndc)}`;
      const resp = await fetch(url);
      if (!resp.ok) return null;
      return (await resp.json()) as ShortageRecord;
    },
    enabled: activeTab === "shortages",
    staleTime: 60_000,
  });

  if (isLoading) {
    return <div data-testid="drug-detail-loading">Loading...</div>;
  }

  if (!drug) {
    return <div data-testid="drug-not-found">Drug not found.</div>;
  }

  const displayName = drug.proprietary_name ?? drug.nonproprietary_name ?? drug.ndc;

  return (
    <div data-testid="drug-detail-page">
      <div data-testid="drug-header">
        <h1 data-testid="drug-name">{displayName}</h1>
        <p data-testid="drug-ndc">NDC: {drug.ndc}</p>
        {drug.strength && <p data-testid="drug-strength">{drug.strength}</p>}
      </div>

      {/* Plan A primitives */}
      <ProvenanceBadge
        sourceKey="fda_ndc"
        runId={drug.run_id ?? null}
        sourceDate={drug.source_date ?? null}
      />
      <FreshnessChip
        sourceKey="fda_ndc"
        lastRunAt={fda_ndc_last_run_at ?? drug.source_date ?? null}
      />

      {/* Tab bar */}
      <div data-testid="drug-tabs">
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
        {activeTab === "pricing" && (
          <div data-testid="pricing-tab">
            {pricing.length > 0 ? (
              <ul data-testid="pricing-list">
                {pricing.map((p, i) => (
                  <li key={i} data-testid="pricing-row">
                    {p.source}: {p.price} (effective {p.effective_date})
                  </li>
                ))}
              </ul>
            ) : (
              <p data-testid="pricing-empty">No pricing data available.</p>
            )}
            {/* BPG: read-only reference, no ingestion schedule */}
            <div data-testid="bpg-pricing-section">
              <span data-testid="bpg-live-api-label">Live API — no ingestion schedule</span>
              <a
                href="/data/reference/bpg/BPG_Translator_API_Documentation.txt"
                data-testid="bpg-doc-link"
              >
                BPG PatientLens Documentation
              </a>
            </div>
          </div>
        )}

        {activeTab === "rems" && (
          <div data-testid="rems-tab">
            {rems ? (
              <div data-testid="rems-info">
                <p data-testid="rems-program">{rems.program_name}</p>
                <p data-testid="rems-required">Required: {String(rems.required)}</p>
                {rems.description && <p data-testid="rems-description">{rems.description}</p>}
              </div>
            ) : (
              <p data-testid="rems-empty">No REMS program for this NDC.</p>
            )}
          </div>
        )}

        {activeTab === "shortages" && (
          <div data-testid="shortages-tab">
            {shortage ? (
              <div data-testid="shortage-info">
                <p data-testid="shortage-status">{shortage.status}</p>
                {shortage.reason && <p data-testid="shortage-reason">{shortage.reason}</p>}
              </div>
            ) : (
              <p data-testid="shortage-empty">No active shortage for this NDC.</p>
            )}
          </div>
        )}

        {activeTab === "interactions" && (
          <div data-testid="interactions-tab">
            {/* B9 pending — drug interactions data not yet available */}
            <B9PendingBanner dataType="interactions" />
          </div>
        )}

        {activeTab === "formulary" && (
          <div data-testid="formulary-tab">
            {/* B9 pending — formulary data not yet available */}
            <B9PendingBanner dataType="formulary" />
          </div>
        )}
      </div>
    </div>
  );
}
