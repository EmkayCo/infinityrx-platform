"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { cn } from "@shared/lib/format";
import { getShortcutRegistry } from "@shared/hooks/use-keyboard-shortcuts";

const DEFAULT_SHORTCUTS = [
  { category: "Navigation", keys: "Cmd+K", action: "Open command palette" },
  { category: "Navigation", keys: "?", action: "Show shortcuts reference" },
  { category: "Navigation", keys: "G then D", action: "Go to Dashboard" },
  { category: "Navigation", keys: "G then B", action: "Go to Billing" },
  { category: "Navigation", keys: "G then R", action: "Go to ReclaimRx" },
  { category: "Navigation", keys: "G then P", action: "Go to Payments" },
  { category: "Forms", keys: "Cmd+S", action: "Save current form / draft" },
  { category: "Forms", keys: "Cmd+Enter", action: "Submit / approve wizard step" },
  { category: "Forms", keys: "Esc", action: "Close modal / cancel action" },
  { category: "Tables", keys: "↑↓", action: "Navigate table rows" },
  { category: "Tables", keys: "Enter", action: "Open selected row detail" },
  { category: "Tables", keys: "Space", action: "Toggle row selection" },
  { category: "Tables", keys: "Shift+Click", action: "Multi-select range" },
  { category: "Tables", keys: "Cmd+A", action: "Select all visible rows" },
  { category: "Tables", keys: "Cmd+E", action: "Export selected" },
  { category: "Actions", keys: "N", action: "New / Create (context-dependent)" },
  { category: "Actions", keys: "F", action: "Focus filter/search" },
];

interface ShortcutsOverlayProps {
  open: boolean;
  onClose: () => void;
}

export function ShortcutsOverlay({ open, onClose }: ShortcutsOverlayProps) {
  const [registeredShortcuts, setRegisteredShortcuts] = useState<
    { category: string; keys: string; action: string }[]
  >([]);

  useEffect(() => {
    if (open) {
      const all = getShortcutRegistry().getAll();
      const extra = all
        .filter((s) => s.category)
        .map((s) => ({
          category: s.category ?? "Other",
          keys: s.keys,
          action: s.label,
        }));
      setRegisteredShortcuts(extra);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const allShortcuts = [...DEFAULT_SHORTCUTS, ...registeredShortcuts];
  const categories = Array.from(new Set(allShortcuts.map((s) => s.category)));

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
    >
      <div className="relative max-h-[80vh] w-full max-w-2xl overflow-y-auto rounded-lg border bg-popover shadow-xl">
        <div className="flex items-center justify-between border-b px-6 py-4">
          <h2 className="font-semibold text-lg">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            aria-label="Close shortcuts"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-1 gap-6 p-6 sm:grid-cols-2">
          {categories.map((category) => (
            <div key={category}>
              <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {category}
              </h3>
              <div className="space-y-1.5">
                {allShortcuts
                  .filter((s) => s.category === category)
                  .map((shortcut) => (
                    <div
                      key={`${shortcut.category}-${shortcut.keys}`}
                      className="flex items-center justify-between gap-4"
                    >
                      <span className="text-sm text-muted-foreground">{shortcut.action}</span>
                      <div className="flex shrink-0 items-center gap-1">
                        {shortcut.keys.split("+").map((key, i, arr) => (
                          <span key={key} className="flex items-center gap-1">
                            <kbd
                              className={cn(
                                "rounded border px-1.5 py-0.5 text-xs font-mono",
                                "bg-muted text-muted-foreground"
                              )}
                            >
                              {key}
                            </kbd>
                            {i < arr.length - 1 && (
                              <span className="text-xs text-muted-foreground">+</span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
