// src/search/rankResults.ts
// Pure ranking function — exact-id first, then prefix, then substring, then secondary.
// Unit-tested in isolation (no BFF or backend dependency).
import type { SearchResultRecord } from "./schemas.js";

/** 0=exact-id, 1=display-prefix, 2=display-substring, 3=secondary-substring, 4=none */
type RankTier = 0 | 1 | 2 | 3 | 4;

function scoreTier(record: SearchResultRecord, ql: string): RankTier {
  if (record.id.toLowerCase() === ql) return 0;
  if (record.display.toLowerCase().startsWith(ql)) return 1;
  if (record.display.toLowerCase().includes(ql)) return 2;
  if (record.secondary.toLowerCase().includes(ql)) return 3;
  return 4;
}

export function rankResults(
  results: SearchResultRecord[],
  query: string,
): SearchResultRecord[] {
  if (!query.trim()) return results;
  const ql = query.toLowerCase();
  return [...results].sort((a, b) => {
    const ta = scoreTier(a, ql);
    const tb = scoreTier(b, ql);
    if (ta !== tb) return ta - tb;
    return a.display.localeCompare(b.display);
  });
}
