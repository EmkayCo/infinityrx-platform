// src/surfaces/pharmacies/PharmaciesListPage.tsx
// Pharmacy directory list page — migrated from portal/operator/app/directories/pharmacies/page.tsx.
// Adds freshness indicator for ncpdp source.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface PharmaciesListPageProps {
  onNavigate?: (href: string) => void;
  /** ISO date of last ncpdp ingestion run */
  ncpdp_last_run_at?: string | null;
  pharmacyDirectoryUrl?: string;
}

interface PharmacySearchHit {
  npi: string;
  name: string;
  city?: string | null;
  state?: string | null;
  pharmacy_type?: string | null;
  network_status?: string | null;
  credentialing_status?: string | null;
}

export function PharmaciesListPage({
  onNavigate,
  ncpdp_last_run_at,
  pharmacyDirectoryUrl = "http://localhost:8009",
}: PharmaciesListPageProps) {
  const [search, setSearch] = useState("");

  const { data: pharmacies = [], isLoading } = useQuery<PharmacySearchHit[]>({
    queryKey: ["pharmacies", search],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("q", search);
      const url = `${pharmacyDirectoryUrl}/api/v1/pharmacies/search?${params.toString()}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`pharmacies search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: PharmacySearchHit[] };
      return data.results ?? [];
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="pharmacies-list-page">
      <div data-testid="freshness-wrapper">
        <FreshnessChip sourceKey="ncpdp" lastRunAt={ncpdp_last_run_at ?? null} />
      </div>
      <div>
        <input
          type="search"
          aria-label="Search pharmacies"
          placeholder="Search NPI, name, city, state..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="pharmacies-search-input"
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      <ul data-testid="pharmacies-list">
        {pharmacies.map((p) => (
          <li key={p.npi} data-testid="pharmacy-row">
            <button onClick={() => onNavigate?.(`/directories/pharmacies/${p.npi}`)}>
              {p.name} — NPI: {p.npi}
              {p.city && p.state && ` — ${p.city}, ${p.state}`}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
