// src/surfaces/prescribers/PrescribersListPage.tsx
// Prescriber directory list page - shows search results as a readable table.
// Calls portal BFF /api/directories/prescribers/search which adds server-side JWT.
// Fields: npi, display_name, primary_specialty, practice_city, practice_state, status
"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

export interface PrescribersListPageProps {
  /** Injected router.push - avoids next/navigation import at module level. */
  onNavigate?: (href: string) => void;
}

const NPI_PATTERN = /^\d{10}$/;

interface BackendSearchHit {
  npi: string;
  display_name: string;
  primary_specialty?: string | null;
  practice_city?: string | null;
  practice_state?: string | null;
  dea_status?: string | null;
  status: string;
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

  const { data: results = [], isLoading, error } = useQuery<BackendSearchHit[]>({
    queryKey: ["prescribers", trimmed],
    enabled: trimmed.length >= 2 && !isNpi,
    queryFn: async () => {
      // Route through portal BFF which adds server-side JWT auth for the backend.
      const url = `/api/directories/prescribers/search?name=${encodeURIComponent(trimmed)}&page_size=50`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`prescribers search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: BackendSearchHit[] };
      return data.results ?? [];
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="prescribers-list-page" style={{ padding: "16px" }}>
      <div style={{ marginBottom: "12px" }}>
        <input
          type="search"
          aria-label="Search prescribers"
          placeholder="Enter NPI (10 digits) or name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="prescribers-search-input"
          style={{ width: "100%", maxWidth: "480px", padding: "8px 12px", fontSize: "14px", border: "1px solid #d1d5db", borderRadius: "6px" }}
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      {error && <p style={{ color: "#dc2626" }}>Error loading prescribers.</p>}
      {!isLoading && !error && results.length === 0 && trimmed.length >= 2 && !isNpi && (
        <p data-testid="no-results">No prescribers found for &quot;{trimmed}&quot;.</p>
      )}
      {trimmed.length < 2 && (
        <p data-testid="empty-hint" style={{ color: "#6b7280", fontSize: "14px" }}>
          Type an NPI to jump to a record, or 2+ letters to search.
        </p>
      )}
      {results.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="prescribers-list"
            style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", backgroundColor: "#f9fafb" }}>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Name</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>NPI</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Specialty</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>City</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>State</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r, idx) => (
                <tr
                  key={r.npi}
                  data-testid="prescriber-row"
                  onClick={() => onNavigate?.(`/directories/prescribers/${r.npi}`)}
                  style={{
                    borderBottom: "1px solid #f3f4f6",
                    cursor: onNavigate ? "pointer" : "default",
                    backgroundColor: idx % 2 === 0 ? "#ffffff" : "#f9fafb",
                  }}
                >
                  <td style={{ padding: "8px 12px", fontWeight: 500 }}>{r.display_name}</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "13px" }}>{r.npi}</td>
                  <td style={{ padding: "8px 12px", color: "#6b7280" }}>{r.primary_specialty ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>{r.practice_city ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>{r.practice_state ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: "9999px",
                      fontSize: "12px",
                      fontWeight: 500,
                      backgroundColor: r.status === "active" ? "#dcfce7" : "#f3f4f6",
                      color: r.status === "active" ? "#166534" : "#6b7280",
                    }}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: "8px", fontSize: "12px", color: "#6b7280" }}>
            {results.length} result{results.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}
    </div>
  );
}
