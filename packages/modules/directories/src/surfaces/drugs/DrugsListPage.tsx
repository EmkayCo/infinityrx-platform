// src/surfaces/drugs/DrugsListPage.tsx
// Drug database list page — migrated from portal/operator/app/directories/drugs/page.tsx.
// Adds FreshnessChip for fda_ndc source.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface DrugsListPageProps {
  onNavigate?: (href: string) => void;
  /** ISO date of last fda_ndc ingestion run */
  fda_ndc_last_run_at?: string | null;
  drugDatabaseUrl?: string;
}

interface DrugSearchHit {
  ndc: string;
  proprietary_name?: string | null;
  nonproprietary_name?: string | null;
  strength?: string | null;
  dosage_form?: string | null;
  therapeutic_class?: string | null;
}

export function DrugsListPage({
  onNavigate,
  fda_ndc_last_run_at,
  drugDatabaseUrl = "http://localhost:8011",
}: DrugsListPageProps) {
  const [search, setSearch] = useState("");

  const { data: drugs = [], isLoading } = useQuery<DrugSearchHit[]>({
    queryKey: ["drugs", search],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("q", search);
      const url = `${drugDatabaseUrl}/api/v1/drugs/search?${params.toString()}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`drugs search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: DrugSearchHit[] };
      return data.results ?? [];
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="drugs-list-page">
      <div data-testid="freshness-wrapper">
        <FreshnessChip sourceKey="fda_ndc" lastRunAt={fda_ndc_last_run_at ?? null} />
      </div>
      <div>
        <input
          type="search"
          aria-label="Search drugs"
          placeholder="Search NDC, drug name, therapeutic class..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="drugs-search-input"
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      <ul data-testid="drugs-list">
        {drugs.map((d) => (
          <li key={d.ndc} data-testid="drug-row">
            <button onClick={() => onNavigate?.(`/directories/drugs/${d.ndc}`)}>
              {d.proprietary_name ?? d.nonproprietary_name ?? d.ndc} — NDC: {d.ndc}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
