"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[route-error]", error);
  }, [error]);

  return (
    <div
      role="alert"
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-6 text-center"
    >
      <AlertTriangle className="h-10 w-10 text-red-400" />
      <div>
        <h2 className="text-lg font-semibold text-white">
          Something went wrong loading this page
        </h2>
        <p className="mt-1 max-w-md text-sm text-slate-400 line-clamp-3">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="mt-2 font-mono text-xs text-slate-500">
            Digest: {error.digest}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <button
          onClick={reset}
          className="flex items-center gap-1.5 rounded-lg bg-teal-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-teal-500"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
        <a
          href="/"
          className="flex items-center gap-1.5 rounded-lg border border-ifx-border-dark px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-ifx-surface-dark"
        >
          Go home
        </a>
      </div>
    </div>
  );
}
