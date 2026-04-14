"use client";

import { useEffect, useCallback, useRef } from "react";

export interface KeyboardShortcut {
  id: string;
  label: string;
  /** e.g. "cmd+k", "g d", "?" */
  keys: string;
  handler: () => void;
  /** Scope for the shortcut — 'global' fires everywhere, others fire only when scope is active */
  scope?: string;
  /** Category for display in shortcuts overlay */
  category?: string;
}

interface ShortcutRegistry {
  shortcuts: Map<string, KeyboardShortcut>;
  register: (shortcut: KeyboardShortcut) => void;
  unregister: (id: string) => void;
  getAll: () => KeyboardShortcut[];
}

// Global registry (module-level singleton)
const registry: ShortcutRegistry = {
  shortcuts: new Map(),
  register(shortcut) {
    registry.shortcuts.set(shortcut.id, shortcut);
  },
  unregister(id) {
    registry.shortcuts.delete(id);
  },
  getAll() {
    return Array.from(registry.shortcuts.values());
  },
};

export function getShortcutRegistry(): ShortcutRegistry {
  return registry;
}

function normalizeKey(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.metaKey || e.ctrlKey) parts.push("cmd");
  if (e.altKey) parts.push("alt");
  if (e.shiftKey) parts.push("shift");
  const key = e.key.toLowerCase();
  if (key !== "meta" && key !== "control" && key !== "alt" && key !== "shift") {
    parts.push(key);
  }
  return parts.join("+");
}

export function useKeyboardShortcut(shortcut: KeyboardShortcut): void {
  const handlerRef = useRef(shortcut.handler);
  handlerRef.current = shortcut.handler;

  useEffect(() => {
    const entry: KeyboardShortcut = {
      ...shortcut,
      handler: () => handlerRef.current(),
    };
    registry.register(entry);
    return () => {
      registry.unregister(shortcut.id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shortcut.id, shortcut.keys, shortcut.scope]);
}

/** Two-key chord state tracking */
let pendingChordKey: string | null = null;
let chordTimeout: ReturnType<typeof setTimeout> | null = null;

function resetChord() {
  pendingChordKey = null;
  if (chordTimeout) {
    clearTimeout(chordTimeout);
    chordTimeout = null;
  }
}

/**
 * Mount the global keyboard shortcut listener.
 * Call this once at the root of the app (layout.tsx).
 */
export function useGlobalKeyboardShortcuts(): void {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    const target = e.target as HTMLElement;
    const isInputFocused =
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable;

    const pressedKey = normalizeKey(e);

    // Handle two-key chords (e.g. "g d")
    const allShortcuts = registry.getAll();

    if (pendingChordKey) {
      const chordCombo = `${pendingChordKey} ${pressedKey}`;
      const chordMatch = allShortcuts.find((s) => s.keys === chordCombo);
      resetChord();
      if (chordMatch) {
        e.preventDefault();
        chordMatch.handler();
        return;
      }
    }

    // Check for single-key shortcuts
    for (const shortcut of allShortcuts) {
      if (shortcut.keys === pressedKey) {
        // Skip single-char shortcuts when input is focused
        if (isInputFocused && !pressedKey.includes("cmd") && !pressedKey.includes("alt")) {
          continue;
        }
        e.preventDefault();
        shortcut.handler();
        return;
      }
    }

    // Check if this could be the start of a chord (single char like 'g')
    if (!pressedKey.includes("+") && pressedKey.length === 1 && !isInputFocused) {
      const couldBeChord = allShortcuts.some((s) => s.keys.startsWith(`${pressedKey} `));
      if (couldBeChord) {
        pendingChordKey = pressedKey;
        chordTimeout = setTimeout(resetChord, 1000);
      }
    }
  }, []);

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);
}
