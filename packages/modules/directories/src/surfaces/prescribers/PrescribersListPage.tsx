// src/surfaces/prescribers/PrescribersListPage.tsx
// Prescriber directory list page — migrated from portal/operator/app/directories/prescribers/page.tsx.
// Retains all existing behaviour (NPI shortcut, search, data table) and adds
// useDirectoriesSearch integration for the Cmd+K search spine (Plan A).
"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
export interface PrescribersListPageProps {
  /** Injected router.push — avoids next/navigation import at module level. */
  onNavigate?: (href: string) => void;
}

const NPI_PATTERN = /^\d{10}$/;

interface BackendSearchHit {
  npi: string;
  display_name: string;
  primary_specialty?: string | null;
  dea_status?: string | null;
  status: string;
}

interface BackendSearchResponse {
  results: BackendSearchHit[];
  total: number;
  page: number;
  page_size: number;
}

export function PrescribersListPage({ onNavigate }: PrescribersListPageProps) {
  const [search, setSearch] = useState("");
  const trimmed = search.trim();
  const isNpi = NPI_PATTERN.test(trimmed);

  // NPI shortcut: jump to detail page when user enters a full 10-digit NPI.
  useEffect(() => {
    if (isNpi && onNavigate) {
      onNavigate(`/directories/prescribers/${trimmed}`);
    }
  }, [isNpi, trimmed, onNavigate]);

  const prescriberDirectoryUrl =
    typeof window !== "undefined"
      ? (window as Window & { __env?: Record<string, string> }).__env?.NEXT_PUBLIC_PRESCRIBER_DIR_URL ?? "http://localhost:8010"
      : "http://localhost:8010";

  const { data: results = [], isLoading } = useQuery<BackendSearchHit[]>({
    queryKey: ["prescribers", trimmed],
    enabled: trimmed.length >= 2 && !isNpi,
    queryFn: async () => {
      const url = `${prescriberDirectoryUrl}/api/v1/prescribers/search?name=${encodeURIComponent(trimmed)}&page_size=50`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`prescribers search failed: ${resp.status}`);
      const data = (await resp.json()) as BackendSearchResponse;
      return data.results;
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="prescribers-list-page">
      <div data-testid="search-input-wrapper">
        <input
          type="search"
          aria-label="Search prescribers"
          placeholder="Enter NPI (10 digits) or name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="prescribers-search-input"
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      <ul data-testid="prescribers-list">
        {results.map((r) => (
          <li key={r.npi} data-testid="prescriber-row">
            <button
              onClick={() => onNavigate?.(`/directories/prescribers/${r.npi}`)}
            >
              {r.display_name} — NPI: {r.npi}
              {r.primary_specialty && ` — ${r.primary_specialty}`}
            </button>
          </li>
        ))}
      </ul>
      {trimmed.length === 0 && (
        <p data-testid="empty-hint">
          Type an NPI to jump to a record, or 2+ letters to search.
        </p>
      )}
    </div>
  );
}
