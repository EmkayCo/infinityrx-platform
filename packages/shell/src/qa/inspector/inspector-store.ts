"use client";
/**
 * Client-side nanostores atom for InspectorEntry list.
 * The slide-out panel subscribes to this atom.
 * wrapFetch calls addEntry() to populate it.
 *
 * Max 100 entries to cap memory usage.
 */
import { atom } from "nanostores";
import type { InspectorEntry } from "./types.js";

const MAX_ENTRIES = 100;

/** The reactive list of captured request/response entries. */
export const $inspectorEntries = atom<InspectorEntry[]>([]);

/** Add a new entry; evicts oldest if MAX_ENTRIES is exceeded. */
export function addEntry(entry: InspectorEntry): void {
  const current = $inspectorEntries.get();
  const next = [entry, ...current].slice(0, MAX_ENTRIES);
  $inspectorEntries.set(next);
}

/** Clear all captured entries. */
export function clearEntries(): void {
  $inspectorEntries.set([]);
}
