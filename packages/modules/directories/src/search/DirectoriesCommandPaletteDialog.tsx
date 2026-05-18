// src/search/DirectoriesCommandPaletteDialog.tsx
// Open/close manager for DirectoriesCommandPalette.
// Listens for Cmd+K (Mac) / Ctrl+K (Windows/Linux) to toggle the palette.
"use client";

import React, { useState, useEffect } from "react";
import { DirectoriesCommandPalette } from "./DirectoriesCommandPalette.js";

export interface DirectoriesCommandPaletteDialogProps {
  /** Called when user selects a result — receives the navigation href */
  onNavigate: (href: string) => void;
  /** Override default keyboard shortcut (Cmd+K / Ctrl+K) for testing */
  keyboardShortcutEnabled?: boolean;
}

export function DirectoriesCommandPaletteDialog({
  onNavigate,
  keyboardShortcutEnabled = true,
}: DirectoriesCommandPaletteDialogProps) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!keyboardShortcutEnabled) return;

    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape" && open) {
        setOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, keyboardShortcutEnabled]);

  return (
    <div data-testid="directories-command-palette-dialog">
      <DirectoriesCommandPalette
        open={open}
        onOpenChange={setOpen}
        onNavigate={onNavigate}
      />
    </div>
  );
}
