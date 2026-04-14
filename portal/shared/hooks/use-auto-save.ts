"use client";

import { useState, useEffect, useCallback, useRef } from "react";

export interface UseAutoSaveOptions<T> {
  /** Unique key for localStorage (include userId to scope per user) */
  storageKey: string;
  /** Initial data */
  initialData?: T;
}

export interface UseAutoSaveReturn<T> {
  draft: T | null;
  save: (data: T) => void;
  clear: () => void;
  hasDraft: boolean;
  lastSavedAt: Date | null;
}

export function useAutoSave<T>(options: UseAutoSaveOptions<T>): UseAutoSaveReturn<T> {
  const { storageKey, initialData } = options;
  const [draft, setDraft] = useState<T | null>(null);
  const [hasDraft, setHasDraft] = useState(false);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const isInitialized = useRef(false);

  // Load draft from localStorage on mount
  useEffect(() => {
    if (isInitialized.current) return;
    isInitialized.current = true;

    try {
      const stored = localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as { data: T; savedAt: string };
        setDraft(parsed.data);
        setHasDraft(true);
        setLastSavedAt(new Date(parsed.savedAt));
      } else if (initialData !== undefined) {
        setDraft(initialData);
      }
    } catch {
      // Corrupt storage — start fresh
      localStorage.removeItem(storageKey);
    }
  }, [storageKey, initialData]);

  const save = useCallback(
    (data: T) => {
      try {
        const savedAt = new Date().toISOString();
        localStorage.setItem(storageKey, JSON.stringify({ data, savedAt }));
        setDraft(data);
        setHasDraft(true);
        setLastSavedAt(new Date(savedAt));
      } catch {
        // localStorage might be full — ignore silently (non-critical)
      }
    },
    [storageKey]
  );

  const clear = useCallback(() => {
    localStorage.removeItem(storageKey);
    setDraft(null);
    setHasDraft(false);
    setLastSavedAt(null);
  }, [storageKey]);

  return { draft, save, clear, hasDraft, lastSavedAt };
}
