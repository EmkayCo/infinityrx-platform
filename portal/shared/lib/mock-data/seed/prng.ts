/**
 * Tiny seeded PRNG (mulberry32) — produces deterministic pseudo-random numbers
 * so reloads always show identical data.
 */
export function mulberry32(seed: number): () => number {
  let s = seed;
  return function () {
    s |= 0;
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Shared RNG instance — call reset() to get a fresh sequence */
let _rng = mulberry32(0xdeadbeef);

export function rng(): number {
  return _rng();
}

export function rngInt(min: number, max: number): number {
  return Math.floor(rng() * (max - min + 1)) + min;
}

export function rngPick<T>(arr: readonly T[]): T {
  return arr[Math.floor(rng() * arr.length)];
}

export function rngPickN<T>(arr: readonly T[], n: number): T[] {
  const copy = [...arr];
  const result: T[] = [];
  for (let i = 0; i < n && copy.length > 0; i++) {
    const idx = Math.floor(rng() * copy.length);
    result.push(copy.splice(idx, 1)[0]);
  }
  return result;
}

/** Decimal-safe money string with 2 decimal places */
export function money(dollars: number): string {
  return dollars.toFixed(2);
}

/** ISO UTC date string offset from base date */
export function isoDate(offsetDays: number): string {
  const base = new Date("2026-04-14T00:00:00Z");
  base.setUTCDate(base.getUTCDate() + offsetDays);
  return base.toISOString();
}

/** ISO UTC date string at a specific time */
export function isoDateTime(offsetDays: number, hour = 0, minute = 0): string {
  const base = new Date("2026-04-14T00:00:00Z");
  base.setUTCDate(base.getUTCDate() + offsetDays);
  base.setUTCHours(hour, minute, 0, 0);
  return base.toISOString();
}

const UUID_POOL: string[] = [
  "00000000-0000-0000-0000-000000000001",
  "00000000-0000-0000-0000-000000000002",
  "00000000-0000-0000-0000-000000000003",
  "00000000-0000-0000-0000-000000000004",
  "00000000-0000-0000-0000-000000000005",
  "00000000-0000-0000-0000-000000000006",
  "00000000-0000-0000-0000-000000000007",
  "00000000-0000-0000-0000-000000000008",
  "00000000-0000-0000-0000-000000000009",
  "00000000-0000-0000-0000-000000000010",
];

export function makeId(prefix: string, index: number): string {
  return `${prefix}-${String(index).padStart(4, "0")}`;
}

export function makeUUID(index: number): string {
  const hex = index.toString(16).padStart(12, "0");
  return `a1b2c3d4-e5f6-7890-abcd-${hex}`;
}

export const TENANT_IDS = [
  "t0000000-0000-0000-0000-000000000001",
  "t0000000-0000-0000-0000-000000000002",
  "t0000000-0000-0000-0000-000000000003",
  "t0000000-0000-0000-0000-000000000004",
];

export const PRIMARY_TENANT = TENANT_IDS[0];
