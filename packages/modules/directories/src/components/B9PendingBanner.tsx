// src/components/B9PendingBanner.tsx
// Informational banner shown when FDB-sourced data is displayed as mock data
// pending the B9 ingestion track completion.
import React from "react";

export interface B9PendingBannerProps {
  dataType: "interactions" | "formulary" | "clinical";
}

const DATA_TYPE_LABELS: Record<B9PendingBannerProps["dataType"], string> = {
  interactions: "drug interaction",
  formulary: "formulary",
  clinical: "clinical",
};

export function B9PendingBanner({ dataType }: B9PendingBannerProps) {
  const label = DATA_TYPE_LABELS[dataType];
  return (
    <div
      className="b9-pending-banner"
      role="status"
      aria-live="polite"
    >
      <span className="b9-pending-banner__icon" aria-hidden="true">⏳</span>
      <span className="b9-pending-banner__text">
        {`This ${label} data requires FDB B9 ingestion which is in progress on a parallel track. Showing mock data.`}
      </span>
    </div>
  );
}
