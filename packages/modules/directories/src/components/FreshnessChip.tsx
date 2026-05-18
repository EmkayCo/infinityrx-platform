// src/components/FreshnessChip.tsx
// Color-coded freshness indicator for a reference data source.
// Green: < 7 days, Yellow: 7–14 days, Red: > 14 days or never loaded.
import React from "react";

export interface FreshnessChipProps {
  sourceKey: string;
  lastRunAt: string | null; // ISO date string (YYYY-MM-DD or ISO-8601)
  className?: string;
}

type FreshnessColor = "green" | "yellow" | "red";

function computeColor(lastRunAt: string | null): { color: FreshnessColor; daysAgo: number | null } {
  if (!lastRunAt) return { color: "red", daysAgo: null };
  const then = new Date(lastRunAt);
  const now = new Date();
  const diffMs = now.getTime() - then.getTime();
  const daysAgo = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (daysAgo < 7) return { color: "green", daysAgo };
  if (daysAgo <= 14) return { color: "yellow", daysAgo };
  return { color: "red", daysAgo };
}

const COLOR_CLASSES: Record<FreshnessColor, string> = {
  green: "freshness-chip freshness-chip--green",
  yellow: "freshness-chip freshness-chip--yellow",
  red: "freshness-chip freshness-chip--red",
};

export function FreshnessChip({ sourceKey, lastRunAt, className }: FreshnessChipProps) {
  const { color, daysAgo } = computeColor(lastRunAt);
  const ageLabel = daysAgo === null ? "Never loaded" : `${daysAgo} day${daysAgo === 1 ? "" : "s"} ago`;
  const chipClass = [COLOR_CLASSES[color], className].filter(Boolean).join(" ");

  return (
    <span className={chipClass} title={`${sourceKey}: last loaded ${ageLabel}`}>
      <span className="freshness-chip__dot" aria-hidden="true" />
      <span className="freshness-chip__source">{sourceKey}</span>
      {lastRunAt && (
        <span className="freshness-chip__date">{" — "}{lastRunAt}</span>
      )}
      <span className="freshness-chip__age">{" ("}{ageLabel}{")"}</span>
    </span>
  );
}
