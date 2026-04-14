/**
 * In-memory server-side cache for InfinityRx claims data.
 * Lazy-loads on first call; lives for the process lifetime.
 * Import ONLY from server-side code (API routes, Server Components).
 *
 * @serverOnly — this module must not be imported by client components.
 */

import * as fs from "fs";
import * as path from "path";
import type { ParsedClaim, Aggregations } from "./types";
import { parseFile } from "./parser";
import ExcelJS from "exceljs";

// ── Paths ─────────────────────────────────────────────────────────────────────
const DATA_DIR = path.join(process.cwd(), "public", "data");
const AGG_DIR = path.join(DATA_DIR, "aggregated");

// ── Module-level cache ────────────────────────────────────────────────────────
let _claims: ParsedClaim[] | null = null;
let _aggregations: Aggregations | null = null;
let _loadPromise: Promise<void> | null = null;

async function buildGroupMap(): Promise<Map<string, string>> {
  const map = new Map<string, string>();
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(path.join(DATA_DIR, "client to groupid mappings.xlsx"));
  const ws = wb.worksheets[0];
  ws.eachRow((row, rowIndex) => {
    if (rowIndex === 1) return;
    const vals = row.values as (string | number | null)[];
    const company = vals[1];
    const groupId = vals[2];
    if (company && groupId) {
      map.set(String(groupId).trim(), String(company).trim());
    }
  });
  return map;
}

async function loadData(): Promise<void> {
  const groupMap = await buildGroupMap();

  const FILES = [
    {
      name: "InfinityRX_20260401_1618.txt",
      cycleId: "BC-2026-SM-08",
      hasHeader: true,
    },
    {
      name: "InfinityRX_20260401_0815.txt",
      cycleId: "BC-2026-SM-07",
      hasHeader: false,
    },
    {
      name: "InfinityRX_20260316_0815.txt",
      cycleId: "BC-2026-SM-06",
      hasHeader: false,
    },
  ];

  const all: ParsedClaim[] = [];
  for (const f of FILES) {
    const text = await fs.promises.readFile(path.join(DATA_DIR, f.name), "utf-8");
    const claims = parseFile(text, {
      hasHeader: f.hasHeader,
      headers: [],
      groupMap,
      cycleId: f.cycleId,
    });
    all.push(...claims);
  }

  _claims = all;
  _aggregations = loadAggregations();
}

function loadAggregations(): Aggregations {
  function readJson<T>(name: string): T {
    return JSON.parse(fs.readFileSync(path.join(AGG_DIR, name), "utf-8")) as T;
  }

  return {
    overview: readJson("overview.json"),
    cycles: readJson("cycles.json"),
    by_client: readJson("by-client.json"),
    by_nrid: readJson("by-nrid.json"),
    by_chain: readJson("by-chain.json"),
    by_pharmacy: readJson("by-pharmacy.json"),
    by_ndc: readJson("by-ndc.json"),
    by_prescriber: readJson("by-prescriber.json"),
    by_member: readJson("by-member.json"),
    top_pharmacies: readJson("top-pharmacies.json"),
    top_ndcs: readJson("top-ndcs.json"),
    top_clients: readJson("top-clients.json"),
    daily_volume: readJson("daily-volume.json"),
    nrid_distribution: readJson("nrid-distribution.json"),
    reversal_rate: readJson("reversal-rate.json"),
    activity_feed: readJson("activity-feed.json"),
    investigations: readJson("investigations.json"),
    manifest: readJson("manifest.json"),
  };
}

async function ensureLoaded(): Promise<void> {
  if (_claims && _aggregations) return;
  if (_loadPromise) {
    await _loadPromise;
    return;
  }
  _loadPromise = loadData();
  await _loadPromise;
}

export async function getClaims(): Promise<ParsedClaim[]> {
  await ensureLoaded();
  return _claims!;
}

export async function getAggregations(): Promise<Aggregations> {
  // Aggregations are read from pre-built JSON files — fast path.
  if (_aggregations) return _aggregations;
  await ensureLoaded();
  return _aggregations!;
}
