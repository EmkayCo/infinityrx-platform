import { describe, it, expect, beforeEach } from "vitest";

// nanostores runs in happy-dom without issue (no browser-specific API).
import { $inspectorEntries, addEntry, clearEntries } from "../qa/inspector/inspector-store.js";
import type { InspectorEntry } from "../qa/inspector/types.js";

function makeEntry(id: string): InspectorEntry {
  return { id, method: "GET", url: "https://x.test/", status: 200, latencyMs: 10, isMock: false, cacheHit: false, timestamp: new Date().toISOString() };
}

describe("inspector-store", () => {
  beforeEach(() => clearEntries());

  it("addEntry prepends new entry to the list", () => {
    addEntry(makeEntry("e1"));
    addEntry(makeEntry("e2"));
    expect($inspectorEntries.get()[0]!.id).toBe("e2");
    expect($inspectorEntries.get()).toHaveLength(2);
  });

  it("clearEntries resets the list to empty", () => {
    addEntry(makeEntry("e1"));
    clearEntries();
    expect($inspectorEntries.get()).toHaveLength(0);
  });

  it("evicts oldest entries beyond MAX_ENTRIES (100)", () => {
    for (let i = 0; i < 105; i++) addEntry(makeEntry(`e${i}`));
    expect($inspectorEntries.get()).toHaveLength(100);
    // Most recent entry is first
    expect($inspectorEntries.get()[0]!.id).toBe("e104");
  });
});
