// src/audit/AuditLogPage.tsx
// Read-only viewer of ingestion-related audit events from core-platform (SP-2 Plan D).
// Fetches via BFF: GET /api/directories/audit?limit=50&offset=0
// Shows empty state if no events (correct behavior — see Plan D §key architectural decision).
// Handles 403 gracefully: user may lack audit:read permission in core-platform.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";

interface AuditEntry {
  id: number;
  action: string;
  module: string;
  entity_type: string | null;
  entity_id: string | null;
  user_id: string | null;
  timestamp: string;
  correlation_id: string | null;
}

interface AuditPage {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuditLogPageProps {
  auditBaseUrl?: string;
  /** Called when a run_id link is clicked — opens RunHistoryDrawer */
  onRunIdClick?: (runId: string, source: string) => void;
  /**
   * Fetch function — inject a token-bearing GET client so the BFF auth gate
   * is satisfied. Defaults to the global fetch for test compatibility.
   */
  fetchFn?: (url: string) => Promise<Response>;
}

const PAGE_SIZE = 50;

async function fetchAuditPage(
  auditBaseUrl: string,
  offset: number,
  fetchFn: (url: string) => Promise<Response>,
): Promise<{ data: AuditPage | null; status: number }> {
  const path = `${auditBaseUrl}/api/directories/audit?limit=${PAGE_SIZE}&offset=${offset}`;
  const res = await fetchFn(path);
  if (res.status === 403) {
    return { data: null, status: 403 };
  }
  if (!res.ok) {
    throw new Error(`Audit fetch failed: ${res.status}`);
  }
  return { data: await res.json(), status: 200 };
}

export function AuditLogPage({
  auditBaseUrl = "",
  onRunIdClick,
  fetchFn = (url) => fetch(url),
}: AuditLogPageProps) {
  const [offset, setOffset] = useState(0);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["dir:audit", offset],
    queryFn: () => fetchAuditPage(auditBaseUrl, offset, fetchFn),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="audit-log-page audit-log-page--loading">
        <p>Loading audit events…</p>
      </div>
    );
  }

  // 403 from core-platform: user lacks audit:read permission.
  // Check this BEFORE isError and before the empty-state check.
  if (data?.status === 403) {
    return (
      <div className="audit-log-page audit-log-page--no-access">
        <p>You do not have permission to view audit events.</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="audit-log-page audit-log-page--error">
        <p>Unable to load audit events. Try refreshing.</p>
      </div>
    );
  }

  const page = data?.data;

  // Empty state is correct behavior — no ingestion runs have been triggered yet.
  if (!page || page.items.length === 0) {
    return (
      <div className="audit-log-page audit-log-page--empty">
        <p className="audit-log-page__empty-text">
          No ingestion audit events yet — trigger an ingestion run to see events
          appear here.
        </p>
      </div>
    );
  }

  const hasPrev = offset > 0;
  const hasNext = offset + PAGE_SIZE < page.total;

  return (
    <div className="audit-log-page">
      <table className="audit-log-page__table" data-testid="audit-log-table" aria-label="Ingestion audit log">
        <thead>
          <tr>
            <th scope="col">Timestamp</th>
            <th scope="col">Action</th>
            <th scope="col">Source</th>
            <th scope="col">Actor</th>
            <th scope="col">Run ID</th>
          </tr>
        </thead>
        <tbody>
          {page.items.map((entry) => (
            <tr key={entry.id} data-audit-id={entry.id}>
              <td>{new Date(entry.timestamp).toLocaleString()}</td>
              <td>{entry.action}</td>
              <td>{entry.entity_id ?? "—"}</td>
              <td>{entry.user_id ?? "—"}</td>
              <td>
                {entry.correlation_id ? (
                  <button
                    type="button"
                    className="audit-log-page__run-link"
                    onClick={() =>
                      onRunIdClick?.(
                        entry.correlation_id!,
                        entry.entity_id ?? "",
                      )
                    }
                    aria-label={`Open run details for ${entry.correlation_id}`}
                  >
                    {entry.correlation_id.slice(0, 8)}…
                  </button>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <nav className="audit-log-page__pagination" aria-label="Audit log pagination">
        <button
          type="button"
          disabled={!hasPrev}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="audit-log-page__pagination-btn"
        >
          Previous
        </button>
        <span className="audit-log-page__pagination-info">
          {offset + 1}–{Math.min(offset + PAGE_SIZE, page.total)} of {page.total}
        </span>
        <button
          type="button"
          disabled={!hasNext}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className="audit-log-page__pagination-btn"
        >
          Next
        </button>
      </nav>
    </div>
  );
}
