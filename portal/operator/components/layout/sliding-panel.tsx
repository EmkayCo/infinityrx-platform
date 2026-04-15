"use client";

import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "@shared/lib/format";

interface SlidingPanelProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * 400px sliding panel that overlays the main content from the right edge.
 * Clicking outside the panel closes it. ESC key also closes.
 */
export function SlidingPanel({
  open,
  onClose,
  title,
  children,
  className,
}: SlidingPanelProps) {
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-ifx-navy-dark/20"
        onClick={onClose}
        aria-hidden="true"
      />
      {/* Panel */}
      <aside
        className={cn(
          "fixed right-0 top-0 z-50 flex h-full w-full max-w-md flex-col bg-white shadow-2xl slide-in-right",
          className,
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sliding-panel-title"
      >
        <div className="flex h-14 items-center justify-between border-b border-ifx-gray-100 px-4 shrink-0">
          <h2 id="sliding-panel-title" className="text-base font-semibold text-ifx-gray-900">
            {title}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close panel"
            className="rounded-md p-1.5 text-ifx-gray-400 hover:bg-ifx-gray-50 hover:text-ifx-gray-700 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </aside>
    </>
  );
}
