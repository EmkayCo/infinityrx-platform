// src/components/ProvenanceBadge.tsx
// Displays ingestion run provenance: source, load date, record count, run link.
import React from "react";

export interface ProvenanceBadgeProps {
  sourceKey: string;
  runId: string | null;
  sourceDate: string | null;
  recordCount?: number;
}

export function ProvenanceBadge({ sourceKey, runId, sourceDate, recordCount }: ProvenanceBadgeProps) {
  return (
    <span className="provenance-badge" data-testid="provenance-badge">
      <span className="provenance-badge__source">{"Source: "}{sourceKey}</span>
      {sourceDate && (
        <span className="provenance-badge__date">{" | Loaded: "}{sourceDate}</span>
      )}
      {recordCount !== undefined && (
        <span className="provenance-badge__count">
          {" | Records: "}{recordCount.toLocaleString()}
        </span>
      )}
      {runId && (
        <span className="provenance-badge__run">{" | Run: "}{runId}</span>
      )}
    </span>
  );
}
