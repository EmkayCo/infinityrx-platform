// src/quality/DismissAlertAction.tsx
// Dismiss button for an ingestion alert (SP-2 Plan D).
// Calls POST /api/directories/quality/dismiss/{source}.
// On success: calls onDismissed() which invalidates the dir:quality TanStack cache.
// On failure: renders an error message.
"use client";

import React, { useState } from "react";

export interface DismissAlertActionProps {
  source: string;
  qualityBaseUrl?: string;
  /** Called after a successful dismiss — caller should invalidate dir:quality query. */
  onDismissed: () => void;
}

type DismissState = "idle" | "loading" | "error";

export function DismissAlertAction({
  source,
  qualityBaseUrl = "",
  onDismissed,
}: DismissAlertActionProps) {
  const [state, setState] = useState<DismissState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleDismiss() {
    setState("loading");
    setErrorMessage(null);
    try {
      const res = await fetch(
        `${qualityBaseUrl}/api/directories/quality/dismiss/${encodeURIComponent(source)}`,
        { method: "POST" },
      );
      if (res.status === 204) {
        setState("idle");
        onDismissed();
      } else if (res.status === 404) {
        setState("error");
        setErrorMessage(`Source '${source}' is not dismissible`);
      } else {
        setState("error");
        setErrorMessage(`Dismiss failed (status ${res.status})`);
      }
    } catch {
      setState("error");
      setErrorMessage("Network error — please try again");
    }
  }

  if (state === "error" && errorMessage) {
    return (
      <span
        className="dismiss-alert-action__error"
        role="alert"
        aria-live="assertive"
      >
        {errorMessage}
      </span>
    );
  }

  return (
    <button
      type="button"
      className="dismiss-alert-action__button"
      onClick={handleDismiss}
      disabled={state === "loading"}
      aria-label={`Dismiss alert for ${source}`}
    >
      {state === "loading" ? "Dismissing…" : "Dismiss"}
    </button>
  );
}
